"""Quem pode o quê no Coffee Break (paridade com `coffee_break/permissions.py`): quem tem o
módulo vê tudo (sem isolamento por setor ou autor); os cadastros contratuais são do
administrador do módulo (o módulo + o perfil ADMINISTRADOR)."""

from __future__ import annotations


def pode_acessar(usuario) -> bool:
    return bool(getattr(usuario, "is_authenticated", False)
                and usuario.has_perm("coffee.acessar_coffee"))


def pode_gerir_cadastros(usuario) -> bool:
    return pode_acessar(usuario) and usuario.has_perm("coffee.change_fornecedor")
