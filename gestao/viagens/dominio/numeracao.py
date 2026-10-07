"""Numeração anual de ofícios.

Regras (decisões D2 e D5 do dono do produto, 01/10/2026, iguais à referência):
- O próximo número é a **menor lacuna registrada** ≥ piso; lacuna só nasce quando um
  rascunho é **excluído**. Sem lacuna, é max(ocupados, piso − 1) + 1.
- Buracos que não vieram de exclusão (dados migrados, saltos manuais) **não** são
  reaproveitados: não há lacuna implícita.
- Números de ofícios cancelados continuam ocupados (rastreabilidade do protocolo).
- O piso (número inicial do ano) não renumera ofícios existentes.
- Formato impresso: dois dígitos no mínimo — "05/2026", "131/2026".
"""

from __future__ import annotations

from collections.abc import Iterable


def proximo_numero(ocupados: Iterable[int], piso: int = 1,
                   lacunas: Iterable[int] = ()) -> int:
    usados = set(ocupados)
    livres = sorted(n for n in lacunas if n >= piso and n not in usados)
    if livres:
        return livres[0]
    return max([piso - 1, *usados]) + 1


def formatar_numero(numero: int | None, ano: int | None) -> str:
    if not numero or not ano:
        return "Sem número"
    return f"{numero:02d}/{ano}"
