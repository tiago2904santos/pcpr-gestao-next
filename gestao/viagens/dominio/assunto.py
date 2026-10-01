"""Natureza do pedido (Autorização × Convalidação) e assunto do documento.

Regra levantada na referência (viagens_oficios/assunto_oficio.py):
- **Autorização** quando a data do ofício é ANTERIOR à data (local) da primeira
  saída; caso contrário (mesmo dia ou depois) é **Convalidação**. Sem saída
  conhecida, assume-se Autorização.
- Marcadores opcionais, mutuamente exclusivos:
  - **Retificado**: só vale se a natureza for Autorização (ignorado na Convalidação);
  - **Complementar**: vale sempre.
  Eles mudam apenas o rótulo entre parênteses; a frase do ofício continua
  "solicito autorização…" ou "solicito convalidação…".
- O assunto nunca é texto livre (evita textos de teste/demonstração no documento).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Marcador(StrEnum):
    NENHUM = ""
    RETIFICADO = "retificado"
    COMPLEMENTAR = "complementar"


@dataclass(frozen=True)
class Assunto:
    autorizacao: bool
    rotulo: str   # "(Autorização)", "(Convalidação)", "(Retificado)", "(Complementar)"
    termo: str    # "autorização" | "convalidação" — usado na frase do ofício
    linha: str    # "Solicitação de autorização e concessão de diárias."


def resolver_assunto(data_oficio: date, primeira_saida: date | None,
                     marcador: Marcador | str = Marcador.NENHUM) -> Assunto:
    autorizacao = primeira_saida is None or data_oficio < primeira_saida
    termo = "autorização" if autorizacao else "convalidação"
    linha = f"Solicitação de {termo} e concessão de diárias."
    marcador = Marcador(marcador or "")
    if marcador is Marcador.COMPLEMENTAR:
        rotulo = "(Complementar)"
    elif marcador is Marcador.RETIFICADO and autorizacao:
        rotulo = "(Retificado)"
    else:
        rotulo = "(Autorização)" if autorizacao else "(Convalidação)"
    return Assunto(autorizacao, rotulo, termo, linha)
