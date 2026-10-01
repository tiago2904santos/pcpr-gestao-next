"""Autorização do módulo Viagens (fonte única; views e menus usam estas funções).

Matriz completa em docs/product/permissions.md.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet

from gestao.cadastros.models import Lotacao, Unidade

from .models import Oficio


def unidade_do_usuario(usuario) -> Unidade | None:
    if not getattr(usuario, "is_authenticated", False):
        return None
    try:
        return usuario.lotacao.unidade
    except Lotacao.DoesNotExist:
        return None


def ve_todas_unidades(usuario) -> bool:
    return usuario.has_perm("viagens.ver_todas_unidades")


def oficios_visiveis(usuario) -> QuerySet[Oficio]:
    if not usuario.has_perm("viagens.view_oficio"):
        return Oficio.objects.none()
    qs = Oficio.objects.all()
    if ve_todas_unidades(usuario):
        return qs
    unidade = unidade_do_usuario(usuario)
    return qs.filter(unidade=unidade) if unidade else qs.none()


def pode_ver(usuario, oficio: Oficio) -> bool:
    if not usuario.has_perm("viagens.view_oficio"):
        return False
    return ve_todas_unidades(usuario) or oficio.unidade_id == getattr(
        unidade_do_usuario(usuario), "pk", None)


def pode_listar(usuario) -> bool:
    return usuario.has_perm("viagens.view_oficio")


def edita_oficios(usuario) -> bool:
    """Perfil com permissão de editar (para oferecer ações de edição nas listas)."""
    return usuario.has_perm("viagens.change_oficio")


def pode_buscar_servidores(usuario) -> bool:
    return usuario.has_perm("cadastros.view_servidor")


def pode_criar(usuario) -> bool:
    return usuario.has_perm("viagens.add_oficio") and unidade_do_usuario(usuario) is not None


def pode_editar(usuario, oficio: Oficio) -> bool:
    return oficio.editavel and usuario.has_perm("viagens.change_oficio") and pode_ver(
        usuario, oficio)


def pode_emitir(usuario, oficio: Oficio) -> bool:
    return pode_editar(usuario, oficio) and usuario.has_perm("viagens.emitir_oficio")


def pode_reabrir(usuario, oficio: Oficio) -> bool:
    return (oficio.situacao == Oficio.Situacao.EMITIDO
            and usuario.has_perm("viagens.reabrir_oficio") and pode_ver(usuario, oficio))


def pode_cancelar(usuario, oficio: Oficio) -> bool:
    return (oficio.situacao != Oficio.Situacao.CANCELADO
            and usuario.has_perm("viagens.cancelar_oficio") and pode_ver(usuario, oficio))


def pode_excluir(usuario, oficio: Oficio) -> bool:
    """Só rascunho sem nenhum documento emitido pode ser excluído (libera o número)."""
    return (oficio.situacao == Oficio.Situacao.RASCUNHO and not oficio.documentos.exists()
            and usuario.has_perm("viagens.delete_oficio") and pode_ver(usuario, oficio))


def exigir(condicao: bool, mensagem: str = "Você não tem permissão para esta ação.") -> None:
    if not condicao:
        raise PermissionDenied(mensagem)
