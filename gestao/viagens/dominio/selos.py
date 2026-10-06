"""Orçamento de selos da linha de uma lista de documentos (decisão D4).

No título de cada linha: a situação do documento e, no máximo, UM alerta — o mais grave:

1. **Justificativa pendente** (a viagem está dentro do prazo e o texto não foi escrito:
   impede emitir);
2. **prazo** — o selo de tempo quando ele mesmo é aviso ("faltam 4 dias", "amanhã", "hoje");
3. **tempo** — o selo de tempo comum ("faltam 30 dias", "em andamento · até 15/10").

"Justificativa preenchida" não é alerta (é o estado normal): sai da linha e fica no resumo.
O tipo do ofício (Convalidação, Retificado, Complementar) não conta aqui: só aparece quando
foge do comum e não compete com o alerta (dominio/assunto.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .tempo import SeloTempo


class TipoAlerta(StrEnum):
    JUSTIFICATIVA = "justificativa"
    PRAZO = "prazo"
    TEMPO = "tempo"


@dataclass(frozen=True)
class Alerta:
    tipo: TipoAlerta
    tempo: SeloTempo | None = None


def alerta_da_linha(*, justificativa_pendente: bool, tempo: SeloTempo | None) -> Alerta | None:
    if justificativa_pendente:
        return Alerta(TipoAlerta.JUSTIFICATIVA)
    if tempo is None:
        return None
    return Alerta(TipoAlerta.PRAZO if tempo.aviso else TipoAlerta.TEMPO, tempo)
