"""Autorização de Eventos Sociais (fonte única; views e menus usam estas funções).

Como na referência: os catálogos ficam com quem administra (papel ADMINISTRADOR); os
textos prontos do despacho também com a Diretoria-Geral (GESTOR_DG). Matriz em
docs/product/permissions.md.
"""

from __future__ import annotations

MODELOS = {"tipos-evento": "tipoevento", "servicos": "servico", "equipes": "equipe",
           "orgaos": "orgaoresponsavel", "unidades-moveis": "unidademovel",
           "textos-despacho": "textodespacho"}


def _autenticado(usuario) -> bool:
    return bool(getattr(usuario, "is_authenticated", False))


def pode_gerir_catalogo(usuario, slug: str) -> bool:
    modelo = MODELOS.get(slug)
    return bool(modelo) and _autenticado(usuario) and usuario.has_perm(f"eventos.change_{modelo}")


def catalogos_visiveis(usuario) -> list[str]:
    return [slug for slug in MODELOS if pode_gerir_catalogo(usuario, slug)]
