"""Leituras do atendimento à imprensa: filtros da lista, indicadores do painel e a linha da
lista (paridade com `services.py`/`presenters.py` da referência)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Count, F, Q, QuerySet

from . import dominio
from .models import Atendimento

NOMES_DOS_MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                   "agosto", "setembro", "outubro", "novembro", "dezembro")
ABREVIADOS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov",
              "dez")


def base() -> QuerySet[Atendimento]:
    return Atendimento.objects.select_related("veiculo", "responsavel", "responsavel_resposta")


def em_aberto() -> QuerySet[Atendimento]:
    return Atendimento.objects.filter(situacao__in=dominio.ABERTAS)


@dataclass
class Filtros:
    q: str = ""
    fila: str = ""
    situacao: str = ""
    veiculo: int | None = None
    responsavel: int | None = None
    inicio: date | None = None
    fim: date | None = None
    vencidos: bool = False

    @property
    def ativos(self) -> int:
        return sum(1 for v in (self.situacao, self.veiculo, self.responsavel, self.inicio,
                               self.fim, self.vencidos) if v)


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
    situacao = get.get("situacao") or ""
    return Filtros(
        q=dominio.uma_linha(get.get("q"))[:100],
        fila=fila if any(fila == chave for chave, _r, _s in dominio.FILAS) else "",
        situacao=situacao if situacao in dominio.ROTULOS else "",
        veiculo=_inteiro(get.get("veiculo")), responsavel=_inteiro(get.get("responsavel")),
        inicio=_data(get.get("inicio")), fim=_data(get.get("fim")),
        vencidos=get.get("vencidos") == "1")


def filtrar(f: Filtros, hoje: date, *, com_fila: bool = True) -> QuerySet[Atendimento]:
    qs = base()
    if com_fila and f.fila:
        qs = qs.filter(situacao__in=next(s for c, _r, s in dominio.FILAS if c == f.fila))
    if f.q:
        qs = qs.filter(Q(jornalista__icontains=f.q) | Q(pedido__icontains=f.q)
                       | Q(contato__icontains=f.q) | Q(fonte__icontains=f.q)
                       | Q(resposta__icontains=f.q) | Q(veiculo__nome__icontains=f.q))
    if f.situacao:
        qs = qs.filter(situacao=f.situacao)
    if f.veiculo:
        qs = qs.filter(veiculo_id=f.veiculo)
    if f.responsavel:
        qs = qs.filter(Q(responsavel_id=f.responsavel) | Q(responsavel_resposta_id=f.responsavel))
    if f.inicio:
        qs = qs.filter(data__gte=f.inicio)
    if f.fim:
        qs = qs.filter(data__lte=f.fim)
    if f.vencidos:
        qs = qs.filter(situacao__in=dominio.ABERTAS, deadline__lt=hoje).order_by(
            "deadline", "data", "horario")
    return qs


def contagens_das_filas(qs: QuerySet[Atendimento]) -> dict[str, int]:
    por_situacao = dict(qs.order_by().values_list("situacao").annotate(n=Count("pk")))
    contagens = {chave: sum(por_situacao.get(s, 0) for s in situacoes)
                 for chave, _r, situacoes in dominio.FILAS}
    contagens[""] = sum(por_situacao.values())
    return contagens


@dataclass
class Linha:
    atendimento: Atendimento
    prazo: dominio.SeloPrazo | None
    # (ícone, rótulo, texto, ausente)
    fatos: list[tuple[str, str, str, bool]] = field(default_factory=list)


def linha(a: Atendimento, hoje: date) -> Linha:
    entrada = f"{a.data:%d/%m/%Y}" + (f" às {a.horario:%H:%M}" if a.horario else "")
    responsavel = a.responsavel.nome if a.responsavel_id and a.responsavel else ""
    fatos = [("calendar", "Entrada do pedido", entrada, False),
             ("user-round", "Responsável", responsavel or "Sem responsável", not responsavel)]
    if a.contato:
        fatos.append(("phone", "Contato", a.contato, False))
    return Linha(a, dominio.selo_do_deadline(a.deadline, a.situacao, hoje), fatos)


# ------------------------------------------------------------------ painel
def inicio_do_mes(hoje: date) -> date:
    return hoje.replace(day=1)


def resumo_do_mes(hoje: date) -> dict[str, int]:
    return Atendimento.objects.filter(data__gte=inicio_do_mes(hoje)).aggregate(
        total=Count("pk"),
        atendidos=Count("pk", filter=Q(situacao=dominio.ATENDIDO)),
        abertos=Count("pk", filter=Q(situacao__in=dominio.ABERTAS)))


def por_veiculo(inicio: date, limite: int = 8) -> list[Any]:
    return list(Atendimento.objects.filter(data__gte=inicio, veiculo__isnull=False)
                .values(nome=F("veiculo__nome"), chave=F("veiculo_id"))
                .annotate(total=Count("pk")).order_by("-total", "nome")[:limite])


def por_responsavel(inicio: date, limite: int = 8) -> list[Any]:
    return list(Atendimento.objects.filter(data__gte=inicio, responsavel__isnull=False)
                .values(nome=F("responsavel__nome"), chave=F("responsavel_id"))
                .annotate(total=Count("pk"),
                          atendidos=Count("pk", filter=Q(situacao=dominio.ATENDIDO)))
                .order_by("-total", "nome")[:limite])


def serie_mensal(hoje: date, meses: int = 6) -> list[dict[str, Any]]:
    marcos: list[date] = []
    primeiro = hoje.replace(day=1)
    for _ in range(meses):
        marcos.append(primeiro)
        primeiro = (primeiro - timedelta(days=1)).replace(day=1)
    marcos.reverse()
    contagens = {(ano, mes): n for ano, mes, n in
                 Atendimento.objects.filter(data__gte=marcos[0])
                 .values_list(F("data__year"), F("data__month")).annotate(n=Count("pk"))}
    barras = [{"rotulo": f"{ABREVIADOS[m.month - 1]}/{m:%y}",
               "titulo": f"{NOMES_DOS_MESES[m.month - 1]} de {m.year}",
               "valor": contagens.get((m.year, m.month), 0)} for m in marcos]
    maximo = max((b["valor"] for b in barras), default=0) or 1
    for b in barras:
        b["altura"] = round(b["valor"] * 100 / maximo)
        b["topo"] = 100 - b["altura"]  # y da barra no SVG (viewBox de 100 de altura)
    return barras
