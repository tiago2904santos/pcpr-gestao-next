"""Conflitos de agenda: a mesma pessoa ou viatura em dois lugares (paridade com
`core/conflitos.py` da referência).

Três regras valem para todas as fontes:

- **todas as unidades**: a pergunta é "esse recurso está livre?", não "está livre na
  minha unidade?" — nenhuma fonte filtra por unidade;
- **horário, não só data**: um recurso ocupa [início, fim) e só há conflito quando dois
  intervalos se sobrepõem de fato (encostar não conta). O que só tem data ocupa o dia
  inteiro, de 00:00 do primeiro dia a 00:00 do dia seguinte ao último;
- **aviso, não bloqueio**: o serviço só descreve; quem chama mostra e deixa seguir.
  Cancelados não contam, e o registro em edição sai pela `Consulta.excluir`.

Cada contexto registra as suas fontes (`registrar_fonte`, no `ready` do app); a
plataforma não conhece os módulos.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from django.utils import timezone


@dataclass(frozen=True)
class Consulta:
    """O que se procura: recursos, período e o que não conta.

    `servidores` são ids do cadastro de servidores (equipe e motorista são a mesma
    pessoa); `palestrantes` são ids de palestrantes; `municipios` + `pedido` procura pedido
    repetido; `excluir` é {"oficio": {pk}, "palestra": {pk}, ...}."""

    inicio: datetime
    fim: datetime
    servidores: frozenset[int] = frozenset()
    viaturas: frozenset[int] = frozenset()
    palestrantes: frozenset[int] = frozenset()
    unidades_moveis: frozenset[int] = frozenset()
    municipios: frozenset[int] = frozenset()
    pedido: str = ""
    excluir: dict[str, set[int]] = field(default_factory=dict)

    def excluidos(self, fonte: str) -> set[int]:
        return set(self.excluir.get(fonte) or ())

    @property
    def vazia(self) -> bool:
        return not (self.servidores or self.viaturas or self.palestrantes
                    or self.unidades_moveis or (self.municipios and self.pedido))

    def datas(self) -> tuple[date, date]:
        """O período em datas locais (para pré-filtrar campos de data)."""
        fim = _local(self.fim)
        ultimo = (fim - timedelta(microseconds=1)).date() if self.fim > self.inicio else fim.date()
        return _local(self.inicio).date(), ultimo


@dataclass(frozen=True)
class Conflito:
    tipo: str  # servidor | viatura | palestrante | unidade_movel | pedido
    recurso: str  # "FULANO", "Viatura ABC1D23"
    no_documento: str  # "no Ofício 12/2026", "na Palestra #45"
    documento: str
    inicio: datetime
    fim: datetime
    local: str = ""
    url: str = ""
    chave: tuple = ()
    papel: str = ""  # " como motorista"
    dia_inteiro: bool = False

    @property
    def periodo(self) -> str:
        return formatar_periodo(self.inicio, self.fim, dia_inteiro=self.dia_inteiro)

    @property
    def mensagem(self) -> str:
        local = f" ({self.local})" if self.local else ""
        if self.tipo == "pedido":
            return (f"Já existe pedido {self.no_documento} para "
                    f"{self.local or 'o mesmo município'} {self.periodo}")
        return f"{self.recurso} já está {self.no_documento}{self.papel} {self.periodo}{local}"


# ---------------------------------------------------------------- período
def _aware(valor: datetime) -> datetime:
    return timezone.make_aware(valor) if timezone.is_naive(valor) else valor


def _local(valor: datetime) -> datetime:
    return timezone.localtime(valor) if timezone.is_aware(valor) else valor


def periodo_de_datas(inicio: date | None, fim: date | None = None, *,
                     hora_inicio: time | None = None,
                     hora_fim: time | None = None) -> tuple[datetime | None, datetime | None]:
    """(início, fim) de um compromisso com data e, talvez, horário. Sem horário de fim,
    vai até o começo do dia seguinte ao último. Sem data inicial, (None, None)."""
    if not inicio:
        return None, None
    fim = fim or inicio
    comeco = _aware(datetime.combine(inicio, hora_inicio or time.min))
    if hora_fim is not None:
        termino = _aware(datetime.combine(fim, hora_fim))
    else:
        termino = _aware(datetime.combine(fim + timedelta(days=1), time.min))
    return comeco, max(comeco, termino)


def sobrepoe(inicio_a: datetime, fim_a: datetime, inicio_b: datetime, fim_b: datetime) -> bool:
    """Intervalos semiabertos que se sobrepõem de fato (encostar não conta)."""
    return inicio_a < fim_b and inicio_b < fim_a


def formatar_periodo(inicio: datetime, fim: datetime, *, dia_inteiro: bool = False) -> str:
    inicio, fim = _local(inicio), _local(fim)
    if dia_inteiro:
        ultimo = (fim - timedelta(microseconds=1)).date() if fim > inicio else inicio.date()
        if ultimo == inicio.date():
            return f"em {inicio:%d/%m/%Y}"
        return f"de {inicio:%d/%m} a {ultimo:%d/%m/%Y}"
    return f"de {inicio:%d/%m %H:%M} a {fim:%d/%m %H:%M}"


# ---------------------------------------------------------------- registro e busca
Fonte = Callable[[Consulta], Iterable[Conflito]]
_FONTES: dict[str, Fonte] = {}
# Quem amplia a consulta antes da busca (ex.: palestrante ligado a um servidor ocupa a
# pessoa) — registrado pelo contexto dono do dado.
_AMPLIADORES: list[Callable[[Consulta], Consulta]] = []


def registrar_fonte(nome: str, fonte: Fonte) -> None:
    _FONTES[nome] = fonte


def registrar_ampliador(funcao: Callable[[Consulta], Consulta]) -> None:
    if funcao not in _AMPLIADORES:
        _AMPLIADORES.append(funcao)


def _ids(valores: Iterable[object]) -> frozenset[int]:
    saida = set()
    for v in valores or ():
        v = getattr(v, "pk", v)
        if v not in (None, "") and str(v).isdigit():
            saida.add(int(str(v)))
    return frozenset(saida)


def consulta(inicio: datetime | None, fim: datetime | None, *, servidores: Iterable = (),
             viaturas: Iterable = (), palestrantes: Iterable = (), unidades_moveis: Iterable = (),
             municipios: Iterable = (), pedido: str = "",
             excluir: dict[str, set[int]] | None = None) -> Consulta | None:
    """Monta a Consulta limpando os ids (aceita instâncias, textos e None)."""
    if not (inicio and fim):
        return None
    c = Consulta(inicio=_aware(inicio), fim=_aware(fim), servidores=_ids(servidores),
                 viaturas=_ids(viaturas), palestrantes=_ids(palestrantes),
                 unidades_moveis=_ids(unidades_moveis), municipios=_ids(municipios),
                 pedido=pedido, excluir=dict(excluir or {}))
    for ampliar in _AMPLIADORES:
        c = ampliar(c)
    return c


def conflitos(c: Consulta | None) -> list[Conflito]:
    """Todos os conflitos da consulta, em ordem de início, sem repetição."""
    if c is None or c.vazia:
        return []
    vistos: set[tuple] = set()
    achados = []
    for fonte in _FONTES.values():
        for conflito in fonte(c) or ():
            if not sobrepoe(c.inicio, c.fim, conflito.inicio, conflito.fim):
                continue
            chave = (conflito.chave, conflito.tipo, conflito.recurso)
            if chave in vistos:
                continue
            vistos.add(chave)
            achados.append(conflito)
    achados.sort(key=lambda x: (x.inicio, x.documento, x.recurso))
    return achados
