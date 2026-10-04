"""Quem gerencia usuários (paridade com `pode_gerenciar_usuarios` da referência, com a
régua do sistema novo: só o ADMINISTRADOR — docs/product/permissions.md — e superusuário).

Melhorias sobre a referência (que não tinha hierarquia): ninguém se desativa; quem não é
superusuário não edita nem desativa um superusuário.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied


def exigir(condicao: bool, mensagem: str = "Você não tem permissão para esta ação.") -> None:
    if not condicao:
        raise PermissionDenied(mensagem)


def pode_ver_usuarios(usuario) -> bool:
    return usuario.has_perm("identidade.view_usuario")


def pode_criar_usuario(usuario) -> bool:
    return usuario.has_perm("identidade.add_usuario")


def pode_editar_usuario(usuario, alvo) -> bool:
    return (usuario.has_perm("identidade.change_usuario")
            and (not alvo.is_superuser or usuario.is_superuser))


def pode_alternar_ativo(usuario, alvo) -> bool:
    return pode_editar_usuario(usuario, alvo) and alvo.pk != usuario.pk
