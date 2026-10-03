"""Autorização dos cadastros de apoio (fonte única; views e menus usam estas funções)."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied


def exigir(condicao: bool, mensagem: str = "Você não tem permissão para esta ação.") -> None:
    if not condicao:
        raise PermissionDenied(mensagem)


# ---------------------------------------------------------------- textos prontos
def pode_ver_textos(usuario) -> bool:
    return usuario.has_perm("cadastros.view_modelotexto")


def pode_gerir_textos(usuario) -> bool:
    """Criar textos e alterar/desativar os comuns (catálogo compartilhado pela equipe)."""
    return usuario.has_perm("cadastros.add_modelotexto") and usuario.has_perm(
        "cadastros.change_modelotexto")


def pode_definir_padrao(usuario) -> bool:
    """O padrão entra em todo ofício novo de todas as unidades: só o gestor escolhe."""
    return usuario.has_perm("cadastros.gerir_padrao_texto")


def pode_alterar_texto(usuario, modelo) -> bool:
    """Alterar ou desativar: o padrão e os do sistema são do gestor; os demais, da equipe."""
    if modelo.padrao or modelo.padrao_sistema:
        return pode_definir_padrao(usuario)
    return pode_gerir_textos(usuario)


def pode_excluir_texto(usuario, modelo) -> bool:
    """Excluir de vez: só o gestor, e nunca o texto que vem com o sistema."""
    return usuario.has_perm("cadastros.delete_modelotexto") and not modelo.padrao_sistema
