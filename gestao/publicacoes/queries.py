"""Leituras do controle de publicações: filtros da lista, indicadores do painel e a linha
da lista (paridade com `services.py`/`presenters.py` da referência)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Count, F, Q, QuerySet

from . import dominio
from .models import Publicacao

NOMES_DOS_MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                   "agosto", "setembro", "outubro", "novembro", "dezembro")
ABREVIADOS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov",
              "dez")


def base() -> QuerySet[Publicacao]:
    return Publicacao.objects.select_related("jornalista", "unidade", "revisao",
                                             "galeria_fotos")


def em_aberto() -> QuerySet[Publicacao]:
    return Publicacao.objects.filter(status__in=dominio.ABERTOS)


@dataclass
class Filtros:
    q: str = ""
    fila: str = ""
    status: str = ""
    jornalista: int | None = None
    unidade: int | None = None
    inicio: date | None = None
    fim: date | None = None

    @property
    def ativos(self) -> int:
        return sum(1 for v in (self.status, self.jornalista, self.unidade, self.inicio,
                               self.fim) if v)


def _data(texto: str | None) -> date | None:
    """dd/mm/aaaa (o campo da tela) ou aaaa-mm-dd (links do painel); inválido é ignorado."""
    texto = (texto or "").strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def _inteiro(texto: str | None) -> int | None:
    return int(texto) if texto and texto.isdigit() else None


def ler_filtros(get) -> Filtros:
    fila = get.get("fila") or ""
    status = get.get("status") or ""
    return Filtros(
        q=dominio.uma_linha(get.get("q"))[:100],
        fila=fila if any(fila == c for c, _r, _s in dominio.FILAS) else "",
        status=status if status in dominio.ROTULOS else "",
        jornalista=_inteiro(get.get("jornalista")), unidade=_inteiro(get.get("unidade")),
        inicio=_data(get.get("inicio")), fim=_data(get.get("fim")))


def filtrar(f: Filtros, *, com_fila: bool = True) -> QuerySet[Publicacao]:
    qs = base()
    if com_fila and f.fila:
        qs = qs.filter(status__in=next(s for c, _r, s in dominio.FILAS if c == f.fila))
    if f.q:
        qs = qs.filter(Q(titulo__icontains=f.q) | Q(fonte__icontains=f.q)
                       | Q(unidade__nome__icontains=f.q) | Q(andamento__icontains=f.q)
                       | Q(link_site__icontains=f.q))
    if f.status:
        qs = qs.filter(status=f.status)
    if f.jornalista:
        qs = qs.filter(jornalista_id=f.jornalista)
    if f.unidade:
        qs = qs.filter(unidade_id=f.unidade)
    if f.inicio:
        qs = qs.filter(data__gte=f.inicio)
    if f.fim:
        qs = qs.filter(data__lte=f.fim)
    return qs


def contagens_das_filas(qs: QuerySet[Publicacao]) -> dict[str, int]:
    por_status = dict(qs.order_by().values_list("status").annotate(n=Count("pk")))
    contagens = {chave: sum(por_status.get(s, 0) for s in situacoes)
                 for chave, _r, situacoes in dominio.FILAS}
    contagens[""] = sum(por_status.values())
    return contagens


@dataclass
class Linha:
    pauta: Publicacao
    fatos: list[dominio.Fato] = field(default_factory=list)


def linha(p: Publicacao) -> Linha:
    entrada = f"{p.data:%d/%m/%Y}" + (f" às {p.inicio_pauta:%H:%M}" if p.inicio_pauta else "")
    unidade = p.unidade.nome if p.unidade_id and p.unidade else ""
    fatos = [dominio.Fato("calendar", "Entrada da pauta", entrada),
             dominio.Fato("landmark", "Unidade", unidade or "Sem unidade", not unidade),
             dominio.Fato("user-round", "Jornalista", p.jornalista.nome)]
    if p.fonte:
        fatos.append(dominio.Fato("info", "Fonte", p.fonte))
    if p.andamento and p.aberta:
        fatos.append(dominio.Fato("activity", "Andamento", dominio.uma_linha(p.andamento)))
    return Linha(p, fatos)


# ------------------------------------------------------------------ painel
def inicio_do_mes(hoje: date) -> date:
    return hoje.replace(day=1)


def resumo_do_mes(hoje: date) -> dict[str, int]:
    return Publicacao.objects.filter(data__gte=inicio_do_mes(hoje)).aggregate(
        total=Count("pk"),
        publicadas=Count("pk", filter=Q(status=dominio.PUBLICADA)),
        abertas=Count("pk", filter=Q(status__in=dominio.ABERTOS)),
        sesp=Count("pk", filter=Q(enviado_sesp=True)),
        aen=Count("pk", filter=Q(publicado_aen=True)))


def tempo_medio(hoje: date) -> tuple[str, int]:
    """Média do início da pauta à publicação, nas publicadas do mês com os horários."""
    deltas = [d for p in Publicacao.objects.filter(
        data__gte=inicio_do_mes(hoje), status=dominio.PUBLICADA, inicio_pauta__isnull=False,
        data_publicacao__isnull=False, horario_publicacao__isnull=False,
    ).only("data", "inicio_pauta", "data_publicacao", "horario_publicacao")
        if (d := p.tempo_ate_publicar) is not None]
    media = dominio.media(deltas)
    return (dominio.formatar_duracao(media) if media else "—"), len(deltas)


def por_jornalista(inicio: date, limite: int = 8) -> list[Any]:
    return list(Publicacao.objects.filter(data__gte=inicio)
                .values(nome=F("jornalista__nome"), chave=F("jornalista_id"))
                .annotate(total=Count("pk"),
                          publicadas=Count("pk", filter=Q(status=dominio.PUBLICADA)))
                .order_by("-total", "nome")[:limite])


def por_unidade(inicio: date, limite: int = 8) -> list[Any]:
    return list(Publicacao.objects.filter(data__gte=inicio, unidade__isnull=False)
                .values(nome=F("unidade__nome"), chave=F("unidade_id"))
                .annotate(total=Count("pk")).order_by("-total", "nome")[:limite])


def serie_mensal(hoje: date, meses: int = 6) -> list[dict[str, Any]]:
    marcos: list[date] = []
    primeiro = hoje.replace(day=1)
    for _ in range(meses):
        marcos.append(primeiro)
        primeiro = (primeiro - timedelta(days=1)).replace(day=1)
    marcos.reverse()
    contagens = {(ano, mes): n for ano, mes, n in
                 Publicacao.objects.filter(data__gte=marcos[0])
                 .values_list(F("data__year"), F("data__month")).annotate(n=Count("pk"))}
    barras = [{"rotulo": f"{ABREVIADOS[m.month - 1]}/{m:%y}",
               "titulo": f"{NOMES_DOS_MESES[m.month - 1]} de {m.year}",
               "valor": contagens.get((m.year, m.month), 0)} for m in marcos]
    maximo = max((b["valor"] for b in barras), default=0) or 1
    for b in barras:
        b["altura"] = round(b["valor"] * 100 / maximo)
        b["topo"] = 100 - b["altura"]  # y da barra no SVG (viewBox de 100 de altura)
    return barras
