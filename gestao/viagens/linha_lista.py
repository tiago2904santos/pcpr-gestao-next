"""O "agora" de uma linha de lista, igual em todas as listas de Viagens.

- urgência: o documento ainda não saiu (rascunho, não gerado) e a viagem começa de hoje a
  `DIAS_DE_URGENCIA` dias — "perigo" com 2 dias ou menos, "aviso" até 7;
- progresso: a viagem está acontecendo agora — quanto do período já passou, em passos de
  10% (a estrada da linha usa o número como classe; CSP sem estilo inline).

Datas puras (OS, termo, plano, viagem) valem o dia inteiro: da 0h do início ao fim do dia
do fim.
"""

from __future__ import annotations

from datetime import date, datetime, time

from django.utils import timezone

DIAS_DE_URGENCIA = 7
PASSO_DO_PROGRESSO = 10


def _instante(valor: date | datetime | None, fim: bool = False) -> datetime | None:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor
    return timezone.make_aware(datetime.combine(valor, time.max if fim else time.min))


def estado_temporal(inicio: date | datetime | None, fim: date | datetime | None,
                    agora: datetime | None = None, *, pendente: bool = False) -> dict:
    """{"urgencia": "" | "aviso" | "perigo", "dias": int | None, "progresso": int | None}."""
    agora = agora or timezone.now()
    estado: dict = {"urgencia": "", "dias": None, "progresso": None}
    comeco, final = _instante(inicio), _instante(fim or inicio, fim=True)
    if comeco is None:
        return estado
    if pendente:
        dias = (timezone.localdate(comeco) - timezone.localdate(agora)).days
        if 0 <= dias <= DIAS_DE_URGENCIA:
            estado["urgencia"] = "perigo" if dias <= 2 else "aviso"
            estado["dias"] = dias
    if final is not None and comeco <= agora <= final and final > comeco:
        fracao = (agora - comeco) / (final - comeco) * 100
        estado["progresso"] = round(fracao / PASSO_DO_PROGRESSO) * PASSO_DO_PROGRESSO
    return estado
