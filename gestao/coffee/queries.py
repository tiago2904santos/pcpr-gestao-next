"""Leituras do Coffee Break: saldo dos lotes, candidatos para a escolha do lote pelo
município, filtros da situação financeira (derivada) e o próximo número da OS."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from django.db.models import Count, Q, QuerySet, Sum
from django.db.models.functions import Coalesce

from . import dominio_pedido
from .models import Lote, Solicitacao

# Situação financeira (derivada) como filtro do banco, na ordem dos marcos.
_ABERTA = Q(cancelada=False)
FILTROS_SITUACAO: dict[str, Q] = {
    "cancelada": Q(cancelada=True),
    "concluida": _ABERTA & Q(envio_empresa_em__isnull=False),
    "aguardando_envio": _ABERTA & Q(envio_empresa_em__isnull=True,
                                    ordem_bancaria_em__isnull=False),
    "aguardando_ob": _ABERTA & Q(envio_empresa_em__isnull=True, ordem_bancaria_em__isnull=True,
                                 atesto_em__isnull=False),
    "aguardando_atesto": _ABERTA & Q(envio_empresa_em__isnull=True,
                                     ordem_bancaria_em__isnull=True, atesto_em__isnull=True)
    & ~Q(protocolo_pagamento=""),
    "aguardando_protocolo": _ABERTA & Q(envio_empresa_em__isnull=True,
                                        ordem_bancaria_em__isnull=True, atesto_em__isnull=True,
                                        protocolo_pagamento="") & ~Q(nota_fiscal=""),
    "aguardando_nota": _ABERTA & Q(envio_empresa_em__isnull=True,
                                   ordem_bancaria_em__isnull=True, atesto_em__isnull=True,
                                   protocolo_pagamento="", nota_fiscal=""),
}
PENDENTES = _ABERTA & Q(envio_empresa_em__isnull=True)  # pendências financeiras


def consumido_por_lote(lotes: list[int] | None = None, *,
                       exceto: int | None = None) -> dict[int, int]:
    """Σ quantidade efetiva (faturada, senão pedida) das não canceladas, por lote."""
    qs = Solicitacao.objects.filter(cancelada=False)
    if lotes is not None:
        qs = qs.filter(lote__in=lotes)
    if exceto:
        qs = qs.exclude(pk=exceto)
    return dict(qs.values_list("lote").annotate(
        n=Sum(Coalesce("quantidade_faturada", "quantidade"))).order_by())


@dataclass
class Saldo:
    total: int
    consumido: int

    @property
    def restante(self) -> int:
        return self.total - self.consumido

    @property
    def percentual(self) -> int:
        return dominio_pedido.percentual_consumido(self.consumido, self.total)

    @property
    def tom(self) -> str:
        return dominio_pedido.tom_do_consumo(self.percentual)


def saldo(lote: Lote, *, exceto: int | None = None) -> Saldo:
    return Saldo(lote.quantidade_total,
                 consumido_por_lote([lote.pk], exceto=exceto).get(lote.pk, 0))


def saldos(lotes: list[Lote]) -> dict[int, Saldo]:
    consumo = consumido_por_lote([lote.pk for lote in lotes])
    return {lote.pk: Saldo(lote.quantidade_total, consumo.get(lote.pk, 0)) for lote in lotes}


@dataclass
class InfoLote:
    """O que a tela mostra do lote que o município recebe."""

    lote: Lote
    saldo: Saldo
    fim: date | None
    proximidade: str = ""
    vencido: bool = False
    avisos: list[str] = field(default_factory=list)


def lotes_ativos() -> list[Lote]:
    return list(Lote.objects.filter(ativo=True)
                .select_related("contrato__fornecedor")
                .prefetch_related("municipios", "contrato__aditivos").order_by("pk"))


def candidatos(lotes: list[Lote]) -> list[dominio_pedido.LoteCandidato]:
    sal = saldos(lotes)
    return [dominio_pedido.LoteCandidato(
        lote.pk, str(lote), lote.exercicio, frozenset(m.pk for m in lote.municipios.all()),
        lote.contrato.fim_efetivo(), sal[lote.pk].restante,
        tuple((m.pk, m.nome, float(m.latitude) if m.latitude is not None else None,
               float(m.longitude) if m.longitude is not None else None)
              for m in lote.municipios.all())) for lote in lotes]


def lote_para(municipio, data: date) -> InfoLote | None:
    lotes = lotes_ativos()
    escolha = dominio_pedido.escolher_lote(
        municipio.pk, float(municipio.latitude) if municipio.latitude is not None else None,
        float(municipio.longitude) if municipio.longitude is not None else None, data,
        candidatos(lotes))
    if escolha is None:
        return None
    lote = next(lote for lote in lotes if lote.pk == escolha.lote_id)
    fim = lote.contrato.fim_efetivo()
    return InfoLote(lote, saldo(lote), fim, escolha.cidade, bool(fim and data > fim))


def proximo_numero(ano: int) -> str:
    """Próxima OS do ano: a maior sequência usada + 1 (numeração própria do módulo por ora —
    a conjunta com Viagens depende de decisão; ver decisoes.md)."""
    usadas = [s for n in Solicitacao.objects.filter(numero__endswith=f"/{ano}")
              .values_list("numero", flat=True) if (s := dominio_pedido.sequencia(n))]
    return f"{max((seq for _a, seq in usadas), default=0) + 1}/{ano}"


def filtrar(qs: QuerySet[Solicitacao], *, q: str = "", lote: int | None = None,
            fornecedor: int | None = None, de: date | None = None, ate: date | None = None,
            situacao: str = "", pendentes: bool = False) -> QuerySet[Solicitacao]:
    if q:
        qs = qs.filter(Q(descricao__unaccent__icontains=q) | Q(numero__icontains=q)
                       | Q(nota_fiscal__icontains=q) | Q(local_entrega__unaccent__icontains=q)
                       | Q(protocolo_pagamento__icontains=q))
    if lote:
        qs = qs.filter(lote_id=lote)
    if fornecedor:
        qs = qs.filter(lote__contrato__fornecedor_id=fornecedor)
    if de:
        qs = qs.filter(data_evento__gte=de)
    if ate:
        qs = qs.filter(data_evento__lte=ate)
    if situacao in FILTROS_SITUACAO:
        qs = qs.filter(FILTROS_SITUACAO[situacao])
    if pendentes:
        qs = qs.filter(PENDENTES)
    return qs


def contagens_por_situacao(qs: QuerySet[Solicitacao]) -> dict[str, int]:
    # Prefixo: o nome do agregado não pode ser o de um campo ("cancelada").
    n = qs.aggregate(**{f"n_{c}": Count("pk", filter=f) for c, f in FILTROS_SITUACAO.items()},
                     n_total=Count("pk"))
    return {chave[2:]: valor for chave, valor in n.items()}
