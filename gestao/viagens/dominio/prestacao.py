"""Regras da prestação de contas em Python puro (paridade com `prazos.py` e
`core/feriados.py` da referência).

- Prazo para prestar contas = prazo limite de saque + 3 dias úteis (conta a partir do fim
  do saque, não do retorno).
- Dia útil: nem sábado, nem domingo, nem feriado nacional (fixos e móveis pela Páscoa) nem
  feriado extra informado (o cadastro de feriados da unidade é decisão pendente).
- Selos de saque e de prestação, com os textos da referência.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

DIAS_UTEIS_PARA_PRESTAR = 3
DIAS_AVISO_SAQUE = 3

FIXOS = ((1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25))


def pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher, calendário gregoriano)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    mes = (h + m - 7 * n + 114) // 31
    dia = (h + m - 7 * n + 114) % 31 + 1
    return date(ano, mes, dia)


def feriados_nacionais(ano: int) -> set[date]:
    p = pascoa(ano)
    moveis = {p - timedelta(days=48), p - timedelta(days=47),  # Carnaval (seg. e ter.)
              p - timedelta(days=2),  # Sexta-feira Santa
              p + timedelta(days=60)}  # Corpus Christi
    return {date(ano, m, d) for m, d in FIXOS} | moveis


def dia_util(dia: date, extras: Iterable[date] = ()) -> bool:
    return (dia.weekday() < 5 and dia not in feriados_nacionais(dia.year)
            and dia not in set(extras))


def somar_dias_uteis(inicio: date, n: int, extras: Iterable[date] = ()) -> date:
    extras = set(extras)
    dia, contados = inicio, 0
    while contados < n:
        dia += timedelta(days=1)
        if dia_util(dia, extras):
            contados += 1
    return dia


def dias_uteis_entre(inicio: date, fim: date, extras: Iterable[date] = ()) -> int:
    """Dias úteis no intervalo (inicio, fim]."""
    extras = set(extras)
    return sum(1 for i in range(1, (fim - inicio).days + 1)
               if dia_util(inicio + timedelta(days=i), extras))


def prazo_para_prestar(prazo_saque: date | None, extras: Iterable[date] = ()) -> date | None:
    return somar_dias_uteis(prazo_saque, DIAS_UTEIS_PARA_PRESTAR, extras) if prazo_saque else None


@dataclass
class Selo:
    texto: str
    tom: str  # "vencido" | "alerta" | "ok"
    detalhe: str = ""


def _plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


def selo_do_saque(prazo_saque: date | None, *, finalizada: bool, tem_comprovante: bool,
                  hoje: date) -> Selo | None:
    if finalizada or tem_comprovante or prazo_saque is None:
        return None
    if prazo_saque < hoje:
        return Selo("Prazo de saque vencido", "vencido",
                    f"Venceu em {prazo_saque:%d/%m/%Y}, sem comprovante.")
    if prazo_saque == hoje:
        return Selo("Saque vence hoje", "alerta", "Sem comprovante anexado.")
    faltam = (prazo_saque - hoje).days
    if faltam <= DIAS_AVISO_SAQUE:
        return Selo(f"Saque vence em {_plural(faltam, 'dia', 'dias')}", "alerta",
                    f"Prazo: {prazo_saque:%d/%m/%Y}.")
    return None


def selo_da_prestacao(prazo_saque: date | None, *, finalizada: bool, hoje: date,
                      extras: Iterable[date] = ()) -> Selo | None:
    limite = prazo_para_prestar(prazo_saque, extras)
    if finalizada or limite is None:
        return None
    if limite < hoje:
        n = dias_uteis_entre(limite, hoje, extras)
        return Selo(f"Prestação vencida em {limite:%d/%m}", "vencido",
                    f"Há {_plural(n, 'dia útil', 'dias úteis')}.")
    if limite == hoje:
        return Selo(f"Prestar contas hoje ({limite:%d/%m})", "alerta")
    n = dias_uteis_entre(hoje, limite, extras)
    falta = "falta" if n == 1 else "faltam"
    return Selo(f"Prestar contas até {limite:%d/%m} — {falta} "
                f"{_plural(n, 'dia útil', 'dias úteis')}", "alerta" if n <= 1 else "ok")
