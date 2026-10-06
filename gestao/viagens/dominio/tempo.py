"""Selo de tempo das listas: quanto falta para a viagem, numa expressão só.

Regra única (decisão D3 do plano da lista de ofícios) para Ofícios, Roteiros e Termos —
e depois Ordens, Planos e Viagens. Antes cada lista tinha um vocabulário ("faltam N dias /
há N dias", "faltam N dias / em andamento", "Previsto / Em andamento / Realizado"), e a de
ofícios dizia "há 1 dia" para uma viagem em curso.

- sem data de início → sem selo (a linha já mostra "Sem período");
- começa depois de amanhã → "faltam N dias" (aviso quando N ≤ prazo, padrão 10 dias — o
  mesmo prazo da justificativa: dentro dele a viagem já pede providência);
- começa amanhã → "amanhã"; começa hoje → "hoje" (viagem de um dia) ou "começa hoje"
  (de vários dias) — os três pedem atenção;
- já começou e volta depois de hoje → "em andamento · até dd/mm";
- já começou e volta hoje → "volta hoje";
- terminou → sem selo: o passado não pede ação, e a data já está na linha.

Datas são as locais (quem chama converte o instante da saída para a data do fuso).
Sem data de volta, a viagem conta como de um dia; volta anterior à saída (dado
incoerente) também — nunca se inventa um "em andamento".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

PRAZO_PADRAO = 10


class Momento(StrEnum):
    FUTURO = "futuro"              # faltam N dias
    IMINENTE = "iminente"          # amanhã, hoje, começa hoje
    EM_ANDAMENTO = "em_andamento"  # em andamento · até dd/mm, volta hoje


@dataclass(frozen=True)
class SeloTempo:
    texto: str
    momento: Momento
    aviso: bool  # pede atenção (tom de aviso na tela)
    dias: int    # dias da data de hoje até o início (negativo: já começou)


def selo_tempo(inicio: date | None, fim: date | None, hoje: date,
               prazo_dias: int = PRAZO_PADRAO) -> SeloTempo | None:
    if inicio is None:
        return None
    if fim is None or fim < inicio:
        fim = inicio
    dias = (inicio - hoje).days
    if dias > 1:
        return SeloTempo(f"faltam {dias} dias", Momento.FUTURO, dias <= prazo_dias, dias)
    if dias == 1:
        return SeloTempo("amanhã", Momento.IMINENTE, True, dias)
    if dias == 0:
        texto = "hoje" if fim == inicio else "começa hoje"
        return SeloTempo(texto, Momento.IMINENTE, True, dias)
    if fim > hoje:
        return SeloTempo(f"em andamento · até {fim:%d/%m}", Momento.EM_ANDAMENTO, False, dias)
    if fim == hoje:
        return SeloTempo("volta hoje", Momento.EM_ANDAMENTO, False, dias)
    return None
