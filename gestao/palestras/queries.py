"""Leituras das palestras e eventos: filtros da lista (status e tipo de evento como abas),
indicadores do painel e a linha da lista (paridade com `views.py`/`presenters.py` da
referência)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from django.db.models import Count, Prefetch, Q, QuerySet, Sum

from . import dominio
from .models import Palestra, Palestrante, Tema

MESES = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro")


def base() -> QuerySet[Palestra]:
    return Palestra.objects.select_related("municipio").prefetch_related(
        Prefetch("temas", queryset=Tema.objects.order_by("nome")),
        Prefetch("palestrantes", queryset=Palestrante.objects.order_by("nome")))


@dataclass
class Filtros:
    q: str = ""
    status: str = ""
    evento: str = ""
    tema: int | None = None
    inicio: date | None = None
    fim: date | None = None

    @property
    def ativos(self) -> int:
        return sum(1 for v in (self.tema, self.inicio, self.fim) if v)


def _data(texto: str | None) -> date | None:
    texto = (texto or "").strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def ler_filtros(get) -> Filtros:
    status = get.get("status") or ""
    evento = get.get("evento") or ""
    tema = get.get("tema") or ""
    return Filtros(q=dominio.uma_linha(get.get("q"))[:100],
                   status=status if status in dominio.ROTULOS else "",
                   evento=evento if evento in dict(dominio.TIPOS_EVENTO) else "",
                   tema=int(tema) if tema.isdigit() else None,
                   inicio=_data(get.get("inicio")), fim=_data(get.get("fim")))


def filtrar(f: Filtros, *, com_status: bool = True) -> QuerySet[Palestra]:
    qs = base()
    if f.q:
        ids = Palestra.objects.filter(
            Q(solicitante__icontains=f.q) | Q(descricao__icontains=f.q)
            | Q(pedido_contato__icontains=f.q) | Q(assunto_email__icontains=f.q)
            | Q(palestrantes__nome__icontains=f.q) | Q(protocolo__icontains=f.q)
            | Q(telefone__icontains=f.q) | Q(email__icontains=f.q)
            | Q(municipio__nome__icontains=f.q) | Q(temas__nome__icontains=f.q)
            | Q(local__icontains=f.q)).values("pk")
        qs = qs.filter(pk__in=ids)
    if com_status and f.status:
        qs = qs.filter(status=f.status)
    if f.evento:
        qs = qs.filter(evento=f.evento)
    if f.tema:
        qs = qs.filter(temas__id=f.tema)
    if f.inicio:
        qs = qs.filter(data_solicitacao__gte=f.inicio)
    if f.fim:
        qs = qs.filter(data_solicitacao__lte=f.fim)
    return qs


def contagens_por_status(qs: QuerySet[Palestra]) -> dict[str, int]:
    por = dict(qs.order_by().values_list("status").annotate(n=Count("pk")))
    por[""] = sum(por.values())
    return por


@dataclass
class Linha:
    palestra: Palestra
    quando: dominio.SeloQuando | None
    fatos: list[tuple[str, str, str, bool]] = field(default_factory=list)


def _fato(icone: str, rotulo: str, texto: str, vazio: str) -> tuple[str, str, str, bool]:
    return (icone, rotulo, texto or vazio, not texto)


def linha(p: Palestra, hoje: date) -> Linha:
    temas = ", ".join(t.nome for t in p.temas.all())
    palestrantes = ", ".join(x.nome for x in p.palestrantes.all())
    publico = f"{p.quantidade_publico} pessoas" if p.quantidade_publico else ""
    return Linha(p, dominio.quando(p.data_inicio_evento, p.data_fim_evento, hoje), [
        _fato("calendar", "Data do evento e hora", p.periodo, "Data à definir"),
        _fato("user-round", "Solicitante", p.solicitante, "Sem solicitante"),
        _fato("list-checks", "Tema", temas, "Sem tema"),
        _fato("users", "Palestrantes", palestrantes, "Sem palestrante"),
        _fato("activity", "Público", publico, "Público não informado"),
        _fato("clock", "Solicitação", f"Pedida em {p.data_solicitacao:%d/%m/%Y}", ""),
    ])


# ------------------------------------------------------------------ painel
def indicadores(hoje: date) -> dict[str, int]:
    return Palestra.objects.aggregate(
        abertas=Count("pk", filter=Q(status__in=dominio.ABERTOS)),
        agendadas=Count("pk", filter=Q(status=dominio.AGENDADA)),
        aguardando=Count("pk", filter=Q(status=dominio.AGUARDANDO)),
        # Pelo ano do evento; sem data do evento, pelo da solicitação (o "Mês" da planilha).
        atendidas_ano=Count("pk", filter=Q(status=dominio.ATENDIDA) & (
            Q(data_inicio_evento__year=hoje.year)
            | Q(data_inicio_evento__isnull=True, data_solicitacao__year=hoje.year))))


def publico_do_ano(hoje: date) -> int:
    return Palestra.objects.filter(status=dominio.ATENDIDA, data_inicio_evento__year=hoje.year
                                   ).aggregate(t=Sum("quantidade_publico"))["t"] or 0


def proximas(hoje: date, limite: int = 8) -> list[Palestra]:
    return list(base().filter(data_inicio_evento__gte=hoje)
                .exclude(status=dominio.CANCELADA)
                .order_by("data_inicio_evento", "hora_inicio")[:limite])


def por_tema(hoje: date, limite: int = 8) -> list[Any]:
    return list(Tema.objects.filter(palestras__data_solicitacao__year=hoje.year)
                .annotate(total=Count("palestras")).order_by("-total", "nome")
                .values("pk", "nome", "total")[:limite])


def mes_de_referencia(p: Palestra) -> str:
    """O "Mês" da planilha: o do evento, senão o da solicitação."""
    return MESES[(p.data_inicio_evento or p.data_solicitacao).month - 1]
