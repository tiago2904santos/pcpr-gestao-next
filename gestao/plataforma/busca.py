"""Busca global (paleta de comandos, Ctrl+K): cada contexto registra as suas fontes
(`registrar_fonte`, no `ready` do app), com a permissão dela — quem não vê o módulo pelas
telas não acha nada dele aqui. A plataforma só junta os resultados, sem conhecer os
contextos (mesmo desenho da agenda e do menu).

Cada fonte devolve no máximo `limite` resultados já ordenados por relevância; a paleta
mostra os grupos na ordem das fontes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

MINIMO = 2  # caracteres para buscar
LIMITE_POR_FONTE = 6


@dataclass(frozen=True)
class Resultado:
    titulo: str
    url: str
    meta: str = ""
    icone: str = ""

    def como_json(self, grupo: str) -> dict[str, str]:
        return {"titulo": self.titulo, "meta": self.meta, "url": self.url, "grupo": grupo,
                "icone": self.icone}


@dataclass(frozen=True)
class Fonte:
    slug: str
    grupo: str  # rótulo do grupo na paleta ("Ofícios", "Atendimentos à imprensa"…)
    pode: Callable[[object], bool]
    buscar: Callable[[object, str, int], list[Resultado]]
    ordem: int = 100


_FONTES: list[Fonte] = []


def registrar_fonte(fonte: Fonte) -> None:
    if all(f.slug != fonte.slug for f in _FONTES):
        _FONTES.append(fonte)
        _FONTES.sort(key=lambda f: (f.ordem, f.grupo))


def fontes_de(usuario) -> list[Fonte]:
    return [f for f in _FONTES if f.pode(usuario)]


def buscar(usuario, termo: str, limite: int = LIMITE_POR_FONTE) -> list[dict[str, str]]:
    """Os resultados de todas as fontes visíveis, agrupados, para a paleta (JSON)."""
    termo = " ".join((termo or "").split())[:100]
    if len(termo) < MINIMO:
        return []
    saida: list[dict[str, str]] = []
    for fonte in fontes_de(usuario):
        resultados = fonte.buscar(usuario, termo, limite)[:limite]
        saida.extend(r.como_json(fonte.grupo) for r in resultados)
    return saida
