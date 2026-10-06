"""Relatório do contrato (CB6b; paridade com `coffee_break/relatorio_contrato.py`, §8.3): o
que justifica um aditivo, um reforço de empenho ou as quantidades da próxima licitação —
consumo por mês e por município, lotes, capacidade e saldo dos vigentes, ritmo dos 3 meses
completos, quando o saldo acaba e a sobra (falta) no fim da vigência, gasto, pago,
empenhado, saldo do empenho, prazo médio nota → ordem bancária e o resumo das entregas.
Conta as OS não canceladas no mês do evento (ou do pedido, sem data de evento)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from . import dominio_painel as regras
from . import entregas, queries
from .models import Contrato, Lote, Solicitacao

MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


@dataclass
class Mes:
    rotulo: str
    os: int = 0
    quantidade: int = 0
    valor: Decimal = Decimal("0.00")
    barra: int = 0  # % do maior mês

    @property
    def topo(self) -> int:
        return 100 - self.barra


@dataclass
class Municipio:
    nome: str
    os: int = 0
    quantidade: int = 0


@dataclass
class LinhaLote:
    lote: Lote
    saldo: queries.Saldo


@dataclass
class Relatorio:
    contrato: Contrato
    hoje: date
    fim: date | None
    meses: list[Mes]
    municipios: list[Municipio]
    lotes: list[LinhaLote]
    capacidade: int
    restante: int
    total_os: int
    total_quantidade: int
    ritmo: float
    acaba_em: date | None
    sobra: int | None
    gasto: Decimal
    pago: Decimal
    empenhado: Decimal | None
    saldo_empenho: Decimal | None
    prazo_medio: int | None
    pagamentos_medidos: int
    entregas: entregas.Resumo = field(default_factory=entregas.Resumo)

    @property
    def consumido(self) -> int:
        return self.capacidade - self.restante

    @property
    def media_por_mes(self) -> float:
        return round(self.total_quantidade / len(self.meses), 1) if self.meses else 0

    @property
    def falta(self) -> int:
        return -self.sobra if self.sobra is not None and self.sobra < 0 else 0

    @property
    def acaba_antes(self) -> bool:
        return bool(self.acaba_em and self.fim and self.acaba_em < self.fim)


def _mes_de(s: Solicitacao) -> date:
    return s.data_evento or s.data_solicitacao


def montar(contrato: Contrato, hoje: date) -> Relatorio:
    oss = list(Solicitacao.objects.filter(lote__contrato=contrato, cancelada=False)
               .select_related("municipio").order_by("data_evento", "data_solicitacao", "pk"))
    lotes = list(contrato.lotes.order_by("-exercicio", "numero", "pk"))
    sal = queries.saldos(lotes)
    ativos = {lote.pk for lote in lotes if lote.ativo}

    meses: dict[tuple[int, int], Mes] = {}
    municipios: dict[str, Municipio] = {}
    consumo_ativos: dict[tuple[int, int], int] = {}
    for s in sorted(oss, key=_mes_de):
        dia = _mes_de(s)
        chave = (dia.year, dia.month)
        m = meses.setdefault(chave, Mes(f"{MESES[dia.month - 1]}/{dia.year}"))
        m.os += 1
        m.quantidade += s.quantidade_efetiva
        m.valor += s.valor or Decimal("0.00")
        mu = municipios.setdefault(s.municipio.nome, Municipio(s.municipio.nome))
        mu.os += 1
        mu.quantidade += s.quantidade_efetiva
        if s.lote_id in ativos:
            consumo_ativos[chave] = consumo_ativos.get(chave, 0) + s.quantidade_efetiva
    maior = max((m.quantidade for m in meses.values()), default=0)
    for m in meses.values():
        m.barra = round(m.quantidade * 100 / maior) if maior else 0

    capacidade = sum(sal[pk].total for pk in ativos)
    restante = sum(sal[pk].restante for pk in ativos)
    ritmo = regras.ritmo(consumo_ativos, hoje)
    fim = contrato.fim_efetivo()
    acaba_em = (hoje + timedelta(days=round(max(restante, 0) / ritmo * regras.DIAS_POR_MES))
                if ritmo > 0 else None)
    sobra = regras.sobra_no_fim(restante, ritmo, fim, hoje)

    gasto = sum((s.valor or Decimal("0.00") for s in oss), Decimal("0.00"))
    pago = sum((s.valor or Decimal("0.00") for s in oss if s.ordem_bancaria_em),
               Decimal("0.00"))
    empenhos = [lote.valor_empenho for lote in lotes
                if lote.pk in ativos and lote.valor_empenho is not None]
    empenhado = sum(empenhos, Decimal("0.00")) if empenhos else None
    comprometido = sum((s.valor or Decimal("0.00") for s in oss if s.lote_id in ativos),
                       Decimal("0.00"))
    prazos = [(s.ordem_bancaria_em - inicio).days for s in oss
              if (inicio := s.nota_emissao or s.data_oficio) and s.ordem_bancaria_em
              and s.ordem_bancaria_em >= inicio]
    return Relatorio(
        contrato=contrato, hoje=hoje, fim=fim, meses=list(meses.values()),
        municipios=sorted(municipios.values(), key=lambda i: (-i.quantidade, i.nome)),
        lotes=[LinhaLote(lote, sal[lote.pk]) for lote in lotes], capacidade=capacidade,
        restante=restante, total_os=len(oss),
        total_quantidade=sum(s.quantidade_efetiva for s in oss), ritmo=round(ritmo, 1),
        acaba_em=acaba_em, sobra=round(sobra) if sobra is not None else None, gasto=gasto,
        pago=pago, empenhado=empenhado,
        saldo_empenho=empenhado - comprometido if empenhado is not None else None,
        prazo_medio=round(sum(prazos) / len(prazos)) if prazos else None,
        pagamentos_medidos=len(prazos), entregas=entregas.resumo_do_contrato(contrato.pk))


def _reais(v: Decimal | None) -> str:
    return "" if v is None else f"{v:.2f}".replace(".", ",")


def _data(d: date | None) -> str:
    return f"{d:%d/%m/%Y}" if d else ""


def linhas_csv(r: Relatorio) -> Iterator[list]:
    """A planilha: um bloco por seção, separados por uma linha vazia."""
    c = r.contrato
    yield ["Relatório do contrato", c.numero, c.fornecedor.razao_social]
    yield ["Gerado em", _data(r.hoje)]
    yield ["Fim da vigência", _data(r.fim)]
    yield ["Capacidade dos lotes vigentes", r.capacidade]
    yield ["Saldo restante", r.restante]
    yield ["Ritmo (média dos últimos 3 meses)", f"{r.ritmo:.1f}".replace(".", ",")]
    yield ["Saldo acaba em", _data(r.acaba_em)]
    yield ["Sobra (falta) no fim da vigência", "" if r.sobra is None else r.sobra]
    yield ["Valor gasto", _reais(r.gasto)]
    yield ["Valor pago", _reais(r.pago)]
    yield ["Empenhado (lotes vigentes)", _reais(r.empenhado)]
    yield ["Saldo do empenho", _reais(r.saldo_empenho)]
    yield ["Prazo médio nota → ordem bancária (dias)",
           "" if r.prazo_medio is None else r.prazo_medio]
    yield ["Entregas", r.entregas.texto]
    yield []
    yield ["Mês", "OS", "Quantidade", "Valor"]
    for m in r.meses:
        yield [m.rotulo, m.os, m.quantidade, _reais(m.valor)]
    yield []
    yield ["Município", "OS", "Quantidade"]
    for mu in r.municipios:
        yield [mu.nome, mu.os, mu.quantidade]
    yield []
    yield ["Lote", "Exercício", "Vigente", "Capacidade", "Consumido", "Restante", "Empenho",
           "Valor do empenho"]
    for linha in r.lotes:
        lote = linha.lote
        yield [lote.numero, lote.exercicio, "Sim" if lote.ativo else "Não",
               linha.saldo.total, linha.saldo.consumido, linha.saldo.restante, lote.empenho,
               _reais(lote.valor_empenho)]

