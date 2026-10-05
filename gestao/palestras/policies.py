"""Autorização das palestras e eventos (fonte única; views e menus usam estas funções).

Na referência, a palestra é vista pelos setores de quem a registrou; aqui não há setores
(decisão do agente, a confirmar): quem tem o papel vê e edita todas, como nos outros
submódulos da ASCOM. Os cadastros de apoio (temas, palestrantes, respostas padrão) ficam
com o próprio papel, como na referência (lá, com quem tem o módulo). Matriz em
docs/product/permissions.md.
"""

from __future__ import annotations


def pode_acessar(usuario) -> bool:
    return bool(getattr(usuario, "is_authenticated", False)
                and usuario.has_perm("palestras.view_palestra"))


def pode_criar(usuario) -> bool:
    return pode_acessar(usuario) and usuario.has_perm("palestras.add_palestra")


def pode_editar(usuario) -> bool:
    return pode_acessar(usuario) and usuario.has_perm("palestras.change_palestra")


def pode_gerir_cadastros(usuario) -> bool:
    return pode_acessar(usuario) and all(
        usuario.has_perm(f"palestras.change_{m}") for m in ("tema", "palestrante",
                                                            "respostapadrao"))
