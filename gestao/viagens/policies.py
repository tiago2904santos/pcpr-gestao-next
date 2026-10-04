"""Autorização do módulo Viagens (fonte única; views e menus usam estas funções).

Matriz completa em docs/product/permissions.md.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet

from gestao.cadastros import policies as politicas_cadastros
from gestao.cadastros.models import Lotacao, Unidade

from .models import Oficio, OrdemServico, Roteiro, TermoAutorizacao


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


def pode_gerir_numeracao(usuario) -> bool:
    """Piso da numeração anual (número inicial do ano): só o gestor."""
    return usuario.has_perm("viagens.gerir_numeracao")


def pode_editar(usuario, oficio: Oficio) -> bool:
    return oficio.editavel and usuario.has_perm("viagens.change_oficio") and pode_ver(
        usuario, oficio)


def pode_emitir(usuario, oficio: Oficio) -> bool:
    return pode_editar(usuario, oficio) and usuario.has_perm("viagens.emitir_oficio")


def pode_reabrir(usuario, oficio: Oficio) -> bool:
    return (oficio.situacao == Oficio.Situacao.EMITIDO and not oficio.arquivado
            and usuario.has_perm("viagens.reabrir_oficio") and pode_ver(usuario, oficio))


def pode_retificar(usuario, oficio: Oficio) -> bool:
    """Editar um ofício já emitido: ele volta a rascunho como RETIFICADO. É a retificação
    do mundo real — quem edita ofícios pode fazer, e tudo fica no histórico. A reabertura
    formal (com motivo registrado) continua sendo do gestor."""
    return (oficio.situacao == Oficio.Situacao.EMITIDO and not oficio.arquivado
            and usuario.has_perm("viagens.change_oficio") and pode_ver(usuario, oficio))


def pode_cancelar(usuario, oficio: Oficio) -> bool:
    return (oficio.situacao != Oficio.Situacao.CANCELADO and not oficio.arquivado
            and usuario.has_perm("viagens.cancelar_oficio") and pode_ver(usuario, oficio))


def pode_reativar(usuario, oficio: Oficio) -> bool:
    """D2: só o gestor reativa um cancelado (e com justificativa — regra do serviço)."""
    return (oficio.situacao == Oficio.Situacao.CANCELADO and not oficio.arquivado
            and usuario.has_perm("viagens.reativar_oficio") and pode_ver(usuario, oficio))


def pode_arquivar(usuario, oficio: Oficio) -> bool:
    """D1: arquivar tira das abas de trabalho, sem apagar (a referência pede só operador)."""
    return (not oficio.arquivado and usuario.has_perm("viagens.arquivar_oficio")
            and pode_ver(usuario, oficio))


def pode_desarquivar(usuario, oficio: Oficio) -> bool:
    return (oficio.arquivado and usuario.has_perm("viagens.arquivar_oficio")
            and pode_ver(usuario, oficio))


def acoes_do_oficio(usuario, oficio: Oficio, *, com_exclusao: bool = False) -> dict[str, bool]:
    """O que o menu de um ofício oferece (lista e janela de resumo). Sem consulta ao banco,
    a não ser a da exclusão (pede `com_exclusao`, só na janela de um ofício)."""
    acoes = {
        "cancelar": pode_cancelar(usuario, oficio),
        "reativar": pode_reativar(usuario, oficio),
        "arquivar": pode_arquivar(usuario, oficio),
        "desarquivar": pode_desarquivar(usuario, oficio),
    }
    if com_exclusao:
        acoes["excluir"] = pode_excluir(usuario, oficio)
    acoes["alguma"] = any(acoes.values())
    return acoes


def pode_excluir(usuario, oficio: Oficio) -> bool:
    """Só rascunho sem nenhum documento emitido pode ser excluído (libera o número)."""
    if oficio.arquivado or oficio.situacao != Oficio.Situacao.RASCUNHO:
        return False  # arquivado não se mexe (desarquive antes); só rascunho se exclui
    # A lista anota `tem_documentos` (uma subconsulta para a página toda); senão, consulta.
    tem_documentos = getattr(oficio, "tem_documentos", None)
    if tem_documentos is None:
        tem_documentos = oficio.documentos.exists()
    return (oficio.situacao == Oficio.Situacao.RASCUNHO and not tem_documentos
            and usuario.has_perm("viagens.delete_oficio") and pode_ver(usuario, oficio))


# ---------------------------------------------------------------- texto dos documentos (ADR 0018)
def pode_editar_texto(usuario, oficio: Oficio) -> bool:
    """Quem edita o ofício edita o texto dos seus documentos — e só enquanto é rascunho."""
    return pode_editar(usuario, oficio)


def pode_gerir_textos_prontos(usuario) -> bool:
    return politicas_cadastros.pode_gerir_textos(usuario)  # uma regra só (cadastros)


# ---------------------------------------------------------------- roteiros
def roteiros_visiveis(usuario) -> QuerySet[Roteiro]:
    if not usuario.has_perm("viagens.view_roteiro"):
        return Roteiro.objects.none()
    if ve_todas_unidades(usuario):
        return Roteiro.objects.all()
    unidade = unidade_do_usuario(usuario)
    return Roteiro.objects.filter(unidade=unidade) if unidade else Roteiro.objects.none()


def pode_ver_roteiro(usuario, roteiro: Roteiro) -> bool:
    if not usuario.has_perm("viagens.view_roteiro"):
        return False
    return ve_todas_unidades(usuario) or roteiro.unidade_id == getattr(
        unidade_do_usuario(usuario), "pk", None)


def pode_criar_roteiro(usuario) -> bool:
    return usuario.has_perm("viagens.add_roteiro") and unidade_do_usuario(usuario) is not None


def pode_editar_roteiro(usuario, roteiro: Roteiro) -> bool:
    return (roteiro.editavel and usuario.has_perm("viagens.change_roteiro")
            and pode_ver_roteiro(usuario, roteiro))


def pode_cancelar_roteiro(usuario, roteiro: Roteiro) -> bool:
    """Cancelar e reativar: quem edita roteiros da unidade."""
    return usuario.has_perm("viagens.change_roteiro") and pode_ver_roteiro(usuario, roteiro)


def pode_excluir_roteiro(usuario, roteiro: Roteiro) -> bool:
    return usuario.has_perm("viagens.delete_roteiro") and pode_ver_roteiro(usuario, roteiro)


# ---------------------------------------------------------------- termos de autorização
def termos_visiveis(usuario) -> QuerySet[TermoAutorizacao]:
    """Mesmo escopo dos ofícios: a unidade da lotação, ou todas para quem vê todas."""
    if not usuario.has_perm("viagens.view_termoautorizacao"):
        return TermoAutorizacao.objects.none()
    if ve_todas_unidades(usuario):
        return TermoAutorizacao.objects.all()
    unidade = unidade_do_usuario(usuario)
    return (TermoAutorizacao.objects.filter(unidade=unidade) if unidade
            else TermoAutorizacao.objects.none())


def pode_ver_termo(usuario, termo: TermoAutorizacao) -> bool:
    if not usuario.has_perm("viagens.view_termoautorizacao"):
        return False
    return ve_todas_unidades(usuario) or termo.unidade_id == getattr(
        unidade_do_usuario(usuario), "pk", None)


def pode_criar_termo(usuario) -> bool:
    return (usuario.has_perm("viagens.add_termoautorizacao")
            and unidade_do_usuario(usuario) is not None)


def pode_editar_termo(usuario, termo: TermoAutorizacao) -> bool:
    """Editar e gerar documentos: termo ativo, quem altera termos e o vê."""
    return (not termo.cancelado and usuario.has_perm("viagens.change_termoautorizacao")
            and pode_ver_termo(usuario, termo))


def pode_cancelar_termo(usuario, termo: TermoAutorizacao) -> bool:
    """Cancelar e reativar: quem altera termos (a referência não restringe mais que isso)."""
    return usuario.has_perm("viagens.change_termoautorizacao") and pode_ver_termo(usuario,
                                                                                  termo)


def pode_excluir_termo(usuario, termo: TermoAutorizacao) -> bool:
    return usuario.has_perm("viagens.delete_termoautorizacao") and pode_ver_termo(usuario,
                                                                                  termo)


# ---------------------------------------------------------------- ordens de serviço
def ordens_visiveis(usuario) -> QuerySet[OrdemServico]:
    if not usuario.has_perm("viagens.view_ordemservico"):
        return OrdemServico.objects.none()
    if ve_todas_unidades(usuario):
        return OrdemServico.objects.all()
    unidade = unidade_do_usuario(usuario)
    return (OrdemServico.objects.filter(unidade=unidade) if unidade
            else OrdemServico.objects.none())


def pode_ver_ordem(usuario, ordem: OrdemServico) -> bool:
    if not usuario.has_perm("viagens.view_ordemservico"):
        return False
    return ve_todas_unidades(usuario) or ordem.unidade_id == getattr(
        unidade_do_usuario(usuario), "pk", None)


def pode_criar_ordem(usuario) -> bool:
    return (usuario.has_perm("viagens.add_ordemservico")
            and unidade_do_usuario(usuario) is not None)


def pode_editar_ordem(usuario, ordem: OrdemServico) -> bool:
    """Editar e gerar documentos: OS ativa, quem altera OS e a vê."""
    return (not ordem.cancelada and usuario.has_perm("viagens.change_ordemservico")
            and pode_ver_ordem(usuario, ordem))


def pode_cancelar_ordem(usuario, ordem: OrdemServico) -> bool:
    return usuario.has_perm("viagens.change_ordemservico") and pode_ver_ordem(usuario, ordem)


def pode_excluir_ordem(usuario, ordem: OrdemServico) -> bool:
    """Excluir libera o número: só enquanto o documento nunca foi gerado (depois, cancelar)."""
    return (ordem.documento_gerado_em is None
            and usuario.has_perm("viagens.delete_ordemservico") and pode_ver_ordem(usuario, ordem))


def pode_criar_ordem_do_oficio(usuario, oficio: Oficio) -> bool:
    """A OS nasce na unidade de quem cria: o ofício precisa ser dela (e não cancelado)."""
    unidade = unidade_do_usuario(usuario)
    return (pode_criar_ordem(usuario) and oficio.situacao != Oficio.Situacao.CANCELADO
            and unidade is not None and oficio.unidade_id == unidade.pk)


def exigir(condicao: bool, mensagem: str = "Você não tem permissão para esta ação.") -> None:
    if not condicao:
        raise PermissionDenied(mensagem)
