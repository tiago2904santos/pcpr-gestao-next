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
from dataclasses import dataclass


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


@dataclass(frozen=True)
class ExplicacaoDoProximo:
    """O próximo número de um ano e de onde ele vem — a página Numeração (LP-32) mostra isto
    ao gestor antes e depois de mudar o piso.

    - `origem`: "lacuna" (a menor liberada por exclusão, ≥ piso), "piso" (o ano começa nele
      ou o piso passou do último ocupado) ou "sequencia" (último ocupado + 1);
    - `lacunas_validas`: na ordem em que serão usadas; `lacunas_abaixo`: abaixo do piso,
      nunca reaproveitadas;
    - `piso_sem_efeito`: o piso é menor ou igual ao último ocupado — guardá-lo não muda nada
      agora (só se a sequência um dia passar por ele, o que não acontece: ela só cresce).
    """

    proximo: int
    origem: str
    lacunas_validas: list[int]
    lacunas_abaixo: list[int]
    piso_sem_efeito: bool


def explicar_proximo(maior: int | None, piso: int = 1,
                     lacunas: Iterable[int] = ()) -> ExplicacaoDoProximo:
    livres = sorted(set(lacunas))
    validas = [n for n in livres if n >= piso]
    abaixo = [n for n in livres if n < piso]
    proximo = proximo_numero([maior] if maior else [], piso, livres)
    if validas and proximo == validas[0]:
        origem = "lacuna"
    elif maior is None or proximo == piso:
        origem = "piso"
    else:
        origem = "sequencia"
    return ExplicacaoDoProximo(proximo, origem, validas, abaixo,
                               maior is not None and piso <= maior)
