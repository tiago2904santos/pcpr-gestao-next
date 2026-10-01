"""Cálculo de diárias de viagem — domínio puro.

Reimplementação (sem código da referência) das regras levantadas contra os
demonstrativos do sistema oficial de solicitação de diárias. Especificação
completa e casos em docs/product/diarias.md; testes em
gestao/viagens/tests/test_dominio_diarias.py.

Regras
------
1. **Períodos por destino.** O período de um destino vai da *chegada* nele até
   a *chegada* no destino seguinte. O primeiro destino começa na *saída da
   sede*. O último termina na *chegada de volta à sede*. Assim o tempo de
   estrada entre destinos é cobrado na faixa de onde o servidor partiu.
2. **Passar pela sede** no meio do roteiro não gera diária (o servidor está em
   casa); a volta final à sede prolonga o último destino.
3. **Trecho tarifário** = períodos consecutivos da mesma faixa (Interior,
   Capital, Brasília). Cada trecho é decomposto em dias inteiros + resto.
4. **Escada do resto** (por duração, não por calendário):
   resto ≤ 6h → 0% · > 6h e ≤ 8h → 15% · > 8h e ≤ 12h → 30% · > 12h → 100%.
5. **Valores**: diária de 24h da tabela vigente na data (local) da primeira
   saída; 15% e 30% = percentual do valor de 24h arredondado ao centavo
   (meio para cima). Subtotal = (24h × dias + parcial) × servidores.
6. **Sem vigência cadastrada → erro visível** (nunca um valor embutido no código).

Os instantes devem chegar no fuso local da sede (o serviço converte).
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from .extenso import reais_por_extenso

CENTAVO = Decimal("0.01")
HORA = 3600
DIA = 24 * HORA


class Faixa(StrEnum):
    INTERIOR = "interior"
    CAPITAL = "capital"
    BRASILIA = "brasilia"

    @property
    def rotulo(self) -> str:
        return {"interior": "Interior", "capital": "Capital", "brasilia": "Brasília"}[self.value]


CAPITAIS: dict[str, str] = {
    "AC": "RIO BRANCO", "AL": "MACEIO", "AP": "MACAPA", "AM": "MANAUS", "BA": "SALVADOR",
    "CE": "FORTALEZA", "DF": "BRASILIA", "ES": "VITORIA", "GO": "GOIANIA", "MA": "SAO LUIS",
    "MT": "CUIABA", "MS": "CAMPO GRANDE", "MG": "BELO HORIZONTE", "PA": "BELEM",
    "PB": "JOAO PESSOA", "PR": "CURITIBA", "PE": "RECIFE", "PI": "TERESINA",
    "RJ": "RIO DE JANEIRO", "RN": "NATAL", "RS": "PORTO ALEGRE", "RO": "PORTO VELHO",
    "RR": "BOA VISTA", "SC": "FLORIANOPOLIS", "SP": "SAO PAULO", "SE": "ARACAJU", "TO": "PALMAS",
}


class SemTabelaDeDiarias(Exception):
    """Não há valor de diária vigente para alguma faixa na data do roteiro."""

    def __init__(self, data_referencia: date, faixas: Sequence[Faixa]):
        self.data_referencia = data_referencia
        self.faixas = list(faixas)
        nomes = ", ".join(f.rotulo for f in self.faixas)
        super().__init__(
            f"Não há valor de diária vigente em {data_referencia:%d/%m/%Y} para: {nomes}. "
            "Cadastre a vigência na Tabela de diárias antes de calcular."
        )


class RoteiroIncalculavel(ValueError):
    """Faltam datas/horas, ou elas estão fora de ordem."""


def _normalizar(texto: str) -> str:
    base = unicodedata.normalize("NFKD", (texto or "").strip().upper())
    return "".join(c for c in base if not unicodedata.combining(c))


def faixa_do_destino(cidade: str, uf: str) -> Faixa:
    uf_n, cidade_n = (uf or "").strip().upper(), _normalizar(cidade)
    if uf_n == "DF" and cidade_n == "BRASILIA":
        return Faixa.BRASILIA
    if uf_n and CAPITAIS.get(uf_n) == cidade_n:
        return Faixa.CAPITAL
    return Faixa.INTERIOR


def mesmo_lugar(cidade_a: str, uf_a: str, cidade_b: str, uf_b: str) -> bool:
    return (_normalizar(cidade_a) == _normalizar(cidade_b)
            and (uf_a or "").strip().upper() == (uf_b or "").strip().upper())


def valor_percentual(valor_24h: Decimal, percentual: int) -> Decimal:
    """15% e 30% do valor de 24h, ao centavo (meio para cima). 100% = o próprio valor."""
    if percentual == 100:
        return Decimal(valor_24h)
    bruto = Decimal(valor_24h) * Decimal(percentual) / Decimal(100)
    return bruto.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def percentual_do_resto(segundos_resto: float) -> int:
    if segundos_resto <= 6 * HORA:
        return 0
    if segundos_resto <= 8 * HORA:
        return 15
    if segundos_resto <= 12 * HORA:
        return 30
    return 100


@dataclass(frozen=True)
class Decomposicao:
    dias: int
    percentual: int
    resto: timedelta
    duracao: timedelta


def decompor(inicio: datetime, fim: datetime) -> Decomposicao:
    segundos = (fim - inicio).total_seconds()
    if segundos <= 0:
        raise RoteiroIncalculavel("Período inválido: a chegada precisa ser depois da saída.")
    dias = int(segundos // DIA)
    resto = segundos - dias * DIA
    return Decomposicao(dias, percentual_do_resto(resto), timedelta(seconds=resto),
                        timedelta(seconds=segundos))


@dataclass(frozen=True)
class Destino:
    """Um destino do roteiro: saída rumo a ele e chegada nele."""

    cidade: str
    uf: str
    saida: datetime
    chegada: datetime | None = None

    @property
    def instante_chegada(self) -> datetime:
        return self.chegada or self.saida


@dataclass(frozen=True)
class ValorVigente:
    faixa: Faixa
    valor_24h: Decimal
    vigente_desde: date
    referencia: str = ""  # identificador da linha da tabela (auditoria)


@dataclass(frozen=True)
class TrechoTarifario:
    faixa: Faixa
    inicio: datetime
    fim: datetime
    dias: int
    percentual: int
    resto: timedelta
    valor_24h: Decimal
    valor_parcial: Decimal
    subtotal: Decimal


@dataclass(frozen=True)
class Parcela:
    """Linha da memória de cálculo ("Como foi calculado")."""

    faixa: Faixa
    inicio: datetime
    fim: datetime
    percentual: int
    quantidade: int
    valor_unitario: Decimal
    subtotal: Decimal
    vigente_desde: date
    referencia: str


@dataclass(frozen=True)
class CalculoDiarias:
    trechos: tuple[TrechoTarifario, ...]
    parcelas: tuple[Parcela, ...]
    servidores: int
    total: Decimal
    por_servidor: Decimal
    data_referencia: date
    resumo: str = field(default="")

    @property
    def extenso(self) -> str:
        return reais_por_extenso(self.total)

    @property
    def faixas(self) -> tuple[Faixa, ...]:
        vistas: list[Faixa] = []
        for t in self.trechos:
            if t.faixa not in vistas:
                vistas.append(t.faixa)
        return tuple(vistas)

    @property
    def tipo_destino(self) -> str:
        return " + ".join(f.rotulo.upper() for f in self.faixas)

    def como_dict(self) -> dict[str, object]:
        """Instantâneo serializável (JSON) para gravar junto do ofício/documento."""
        return {
            "total": str(self.total),
            "por_servidor": str(self.por_servidor),
            "servidores": self.servidores,
            "resumo": self.resumo,
            "extenso": self.extenso,
            "tipo_destino": self.tipo_destino,
            "data_referencia": self.data_referencia.isoformat(),
            "parcelas": [
                {
                    "faixa": p.faixa.value, "inicio": p.inicio.isoformat(),
                    "fim": p.fim.isoformat(), "percentual": p.percentual,
                    "quantidade": p.quantidade, "valor_unitario": str(p.valor_unitario),
                    "subtotal": str(p.subtotal), "vigente_desde": p.vigente_desde.isoformat(),
                    "referencia": p.referencia,
                }
                for p in self.parcelas
            ],
        }


BuscarTabelas = Callable[[date], Mapping[Faixa, ValorVigente]]


def _resumo(trechos: Sequence[TrechoTarifario]) -> str:
    inteiras = sum(t.dias for t in trechos) + sum(1 for t in trechos if t.percentual == 100)
    p15 = sum(1 for t in trechos if t.percentual == 15)
    p30 = sum(1 for t in trechos if t.percentual == 30)
    partes = []
    if inteiras:
        partes.append(f"{inteiras} x 100%")
    if p15:
        partes.append(f"{p15} x 15%")
    if p30:
        partes.append(f"{p30} x 30%")
    return " + ".join(partes) or "Sem diárias"


def calcular(
    destinos: Sequence[Destino],
    chegada_na_sede: datetime | None,
    *,
    buscar_tabelas: BuscarTabelas,
    servidores: int,
    sede: tuple[str, str],
) -> CalculoDiarias:
    if not destinos or chegada_na_sede is None:
        raise RoteiroIncalculavel("Preencha as datas e horas dos trechos para calcular.")
    ordenados = sorted(destinos, key=lambda d: d.saida)
    data_referencia = ordenados[0].saida.date()
    tabelas = buscar_tabelas(data_referencia)
    faltando = [f for f in Faixa if f not in tabelas]
    if faltando:
        raise SemTabelaDeDiarias(data_referencia, faltando)
    servidores = max(0, int(servidores))

    # 1–2. Períodos por destino.
    periodos: list[tuple[Faixa, datetime, datetime, bool]] = []
    ultimo = len(ordenados) - 1
    for i, destino in enumerate(ordenados):
        inicio = destino.saida if i == 0 else destino.instante_chegada
        fim = ordenados[i + 1].instante_chegada if i < ultimo else chegada_na_sede
        if fim < inicio:
            raise RoteiroIncalculavel(
                "As datas estão fora de ordem: confira saídas e chegadas dos trechos."
            )
        if fim == inicio:
            continue  # parada instantânea: sem permanência
        volta_sede = mesmo_lugar(destino.cidade, destino.uf, *sede)
        if volta_sede and i != ultimo:
            continue  # em casa no meio do roteiro
        periodos.append((faixa_do_destino(destino.cidade, destino.uf), inicio, fim,
                         volta_sede and i == ultimo))
    if not periodos:
        raise RoteiroIncalculavel("O roteiro não tem permanência fora da sede.")

    # 3. Trechos tarifários (mesma faixa contígua; volta à sede prolonga o anterior).
    agrupados: list[list] = []
    for faixa, inicio, fim, eh_volta in periodos:
        anterior = agrupados[-1] if agrupados else None
        if anterior is not None and anterior[2] == inicio and (eh_volta or anterior[0] == faixa):
            anterior[2] = fim
            continue
        agrupados.append([faixa, inicio, fim])

    # 4–5. Decomposição e valores.
    trechos: list[TrechoTarifario] = []
    parcelas: list[Parcela] = []
    for faixa, inicio, fim in agrupados:
        d = decompor(inicio, fim)
        vigente = tabelas[faixa]
        parcial = valor_percentual(vigente.valor_24h, d.percentual) if d.percentual else Decimal(
            "0.00")
        subtotal = (vigente.valor_24h * d.dias + parcial) * servidores
        trechos.append(TrechoTarifario(faixa, inicio, fim, d.dias, d.percentual, d.resto,
                                       vigente.valor_24h, parcial, subtotal))
        if d.dias:
            parcelas.append(Parcela(faixa, inicio, fim, 100, d.dias, vigente.valor_24h,
                                    vigente.valor_24h * d.dias * servidores,
                                    vigente.vigente_desde, vigente.referencia))
        if d.percentual:
            parcelas.append(Parcela(faixa, inicio, fim, d.percentual, 1, parcial,
                                    parcial * servidores, vigente.vigente_desde,
                                    vigente.referencia))

    total = sum((t.subtotal for t in trechos), Decimal("0.00"))
    por_servidor = (total / servidores).quantize(CENTAVO) if servidores else Decimal("0.00")
    return CalculoDiarias(tuple(trechos), tuple(parcelas), servidores, total, por_servidor,
                          data_referencia, _resumo(trechos))
