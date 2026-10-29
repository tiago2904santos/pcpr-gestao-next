"""Leitura de texto livre por regra (Python puro): datas, horários e a conferência de que o
que uma leitura (por regra ou por IA) apontou está MESMO no texto.

A IA pode reorganizar o que o texto diz; nunca acrescentar. Uma data só vale se o dia e o mês
aparecem no texto ("21/11", "21 de novembro"); um horário, se a hora aparece ("8h", "08:00");
um trecho citado, se é um pedaço do texto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .validacao import normalizar

MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
         "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11,
         "dezembro": 12}
_DATA_NUM = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?(?!\d)")
_DATA_EXT = re.compile(r"(?<!\d)(\d{1,2})\s+de\s+(" + "|".join(MESES) + r")(?:\s+de\s+(\d{4}))?")
_HORA = re.compile(r"(?<!\d)([01]?\d|2[0-3])\s*(?::|h)\s*([0-5]\d)?(?!\d)")


@dataclass(frozen=True)
class Achado:
    linha: int
    valor: str      # "2026-11-21" ou "08:00"
    trecho: str


def _ano(bruto: str | None, ano_base: int) -> int:
    if not bruto:
        return ano_base
    ano = int(bruto)
    return ano + 2000 if ano < 100 else ano


def datas(texto: str, ano_base: int) -> list[Achado]:
    saida = []
    for i, linha in enumerate((texto or "").splitlines()):
        norm = normalizar(linha)
        for m in _DATA_NUM.finditer(norm):
            try:
                d = date(_ano(m.group(3), ano_base), int(m.group(2)), int(m.group(1)))
            except ValueError:
                continue
            saida.append(Achado(i, d.isoformat(), m.group(0)))
        for m in _DATA_EXT.finditer(norm):
            try:
                d = date(_ano(m.group(3), ano_base), MESES[m.group(2)], int(m.group(1)))
            except ValueError:
                continue
            saida.append(Achado(i, d.isoformat(), m.group(0)))
    return saida


def horas(texto: str) -> list[Achado]:
    saida = []
    for i, linha in enumerate((texto or "").splitlines()):
        for m in _HORA.finditer(normalizar(linha)):
            if ":" not in m.group(0) and "h" not in m.group(0):
                continue
            saida.append(Achado(i, f"{int(m.group(1)):02d}:{m.group(2) or '00'}", m.group(0)))
    return saida


def data_no_texto(valor: str, texto: str) -> bool:
    try:
        d = date.fromisoformat(valor)
    except ValueError:
        return False
    # Sem ano no texto ("21/11"), vale o ano da data proposta (é o `ano_base`); com ano
    # explícito ("21/11/2026"), a data inteira tem de bater — outro ano não passa.
    return any(a.valor == valor for a in datas(texto, d.year))


def hora_no_texto(valor: str, texto: str) -> bool:
    return any(a.valor == valor for a in horas(texto))


def trecho_no_texto(trecho: str, texto: str) -> bool:
    t = normalizar(trecho)
    return bool(t) and t in normalizar(texto)


def termo_no_texto(termo: str, texto: str) -> bool:
    t = normalizar(termo)
    return bool(t) and re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])",
                                 normalizar(texto)) is not None
