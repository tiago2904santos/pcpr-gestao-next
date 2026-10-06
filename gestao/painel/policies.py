"""Quem pode o quê nas telas que juntam os módulos (agenda, relatórios)."""

from __future__ import annotations

from gestao.plataforma import agenda


def pode_assinar_agenda(usuario) -> bool:
    """O link ICS é de quem vê alguma fonte da agenda."""
    return bool(getattr(usuario, "is_authenticated", False) and agenda.fontes_de(usuario))
