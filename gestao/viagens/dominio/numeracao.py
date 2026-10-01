"""Numeração anual de ofícios.

Comportamento da referência (tela "Numeração de ofícios"): a sequência é
calculada pelo maior número ocupado e pelas lacunas liberadas; um piso
(número inicial do ano) pode ser configurado e não renumera ofícios existentes.

Aqui: o próximo número é a **menor lacuna** ≥ piso entre os números ocupados;
sem lacuna, é max(ocupados, piso − 1) + 1. Números de ofícios cancelados
continuam ocupados (não voltam a ser usados — rastreabilidade do protocolo);
só a exclusão de um rascunho libera o número.
"""

from __future__ import annotations

from collections.abc import Iterable


def proximo_numero(ocupados: Iterable[int], piso: int = 1) -> int:
    usados = {n for n in ocupados if n >= piso}
    candidato = piso
    while candidato in usados:
        candidato += 1
    return candidato


def formatar_numero(numero: int | None, ano: int | None) -> str:
    if not numero or not ano:
        return "Sem número"
    return f"{numero:03d}/{ano}"
