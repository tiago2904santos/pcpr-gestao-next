"""Autorização do atendimento à imprensa (fonte única; views e menus usam estas funções).

Como na referência, quem tem o módulo vê e edita todos os atendimentos (não há escopo por
unidade: a equipe da ASCOM é uma só); os cadastros de apoio (equipe e veículos) ficam com
quem administra. Matriz em docs/product/permissions.md.
"""

from __future__ import annotations


def pode_acessar(usuario) -> bool:
    return bool(getattr(usuario, "is_authenticated", False)
                and usuario.has_perm("imprensa.view_atendimento"))


def pode_criar(usuario) -> bool:
    return pode_acessar(usuario) and usuario.has_perm("imprensa.add_atendimento")


def pode_editar(usuario) -> bool:
    return pode_acessar(usuario) and usuario.has_perm("imprensa.change_atendimento")


def pode_gerir_cadastros(usuario) -> bool:
    return bool(getattr(usuario, "is_authenticated", False)
                and usuario.has_perm("imprensa.change_veiculo")
                and usuario.has_perm("imprensa.change_integrante"))
