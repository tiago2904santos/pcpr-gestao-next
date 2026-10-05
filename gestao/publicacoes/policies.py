"""Autorização do controle de publicações (fonte única; views e menus usam estas funções).

Como na referência, o relatório é centralizado na assessoria: quem tem o módulo vê e edita
todas as pautas; os cadastros de apoio (equipe e unidades) ficam com quem administra.
Matriz em docs/product/permissions.md.
"""

from __future__ import annotations


def pode_acessar(usuario) -> bool:
    return bool(getattr(usuario, "is_authenticated", False)
                and usuario.has_perm("publicacoes.view_publicacao"))


def pode_criar(usuario) -> bool:
    return pode_acessar(usuario) and usuario.has_perm("publicacoes.add_publicacao")


def pode_editar(usuario) -> bool:
    return pode_acessar(usuario) and usuario.has_perm("publicacoes.change_publicacao")


def pode_gerir_cadastros(usuario) -> bool:
    return bool(getattr(usuario, "is_authenticated", False)
                and usuario.has_perm("publicacoes.change_integrante")
                and usuario.has_perm("publicacoes.change_unidaderesponsavel"))
