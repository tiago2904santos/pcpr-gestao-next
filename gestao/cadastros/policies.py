"""Autorização dos cadastros de apoio (fonte única; views e menus usam estas funções).

Como na referência: quem mantém os cadastros (servidores, viaturas, unidades, cargos,
combustíveis) é a equipe de viagens — gestor e operador; a tabela de diárias e a
configuração institucional são só do gestor (dinheiro e dados oficiais). Quem só consulta
vê, sem escrever. A matriz está em docs/product/permissions.md.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet


def exigir(condicao: bool, mensagem: str = "Você não tem permissão para esta ação.") -> None:
    if not condicao:
        raise PermissionDenied(mensagem)


def _nome(modelo) -> str:
    return modelo._meta.model_name


# ---------------------------------------------------------------- cadastros (CRUD)
def pode_ver_cadastro(usuario, modelo) -> bool:
    return usuario.has_perm(f"cadastros.view_{_nome(modelo)}")


def pode_criar_cadastro(usuario, modelo) -> bool:
    return usuario.has_perm(f"cadastros.add_{_nome(modelo)}")


def pode_alterar_cadastro(usuario, modelo) -> bool:
    """Editar, desativar/reativar e escolher o padrão (cargo, combustível)."""
    return usuario.has_perm(f"cadastros.change_{_nome(modelo)}")


def pode_excluir_cadastro(usuario, modelo) -> bool:
    """Excluir de vez — o serviço ainda recusa quando há vínculos (ofícios, servidores…)."""
    return usuario.has_perm(f"cadastros.delete_{_nome(modelo)}")


def acoes_do_cadastro(usuario, modelo) -> dict[str, bool]:
    """O que a lista de um cadastro oferece (sem consulta ao banco)."""
    acoes = {"criar": pode_criar_cadastro(usuario, modelo),
             "alterar": pode_alterar_cadastro(usuario, modelo),
             "excluir": pode_excluir_cadastro(usuario, modelo)}
    acoes["alguma"] = acoes["alterar"] or acoes["excluir"]
    return acoes


# ---------------------------------------------------------------- configuração da unidade
def pode_ver_configuracao(usuario) -> bool:
    return usuario.has_perm("cadastros.view_configuracaoinstitucional")


def pode_alterar_configuracao(usuario, unidade=None) -> bool:
    """Alterar a configuração (dados oficiais dos documentos): só o gestor; de outra unidade
    que não a da lotação, só quem vê todas as unidades. Sem `unidade`: "altera alguma"."""
    if not usuario.has_perm("cadastros.change_configuracaoinstitucional"):
        return False
    if unidade is None or usuario.has_perm("viagens.ver_todas_unidades"):
        return True
    return unidade.pk == _pk_da_lotacao(usuario)


def unidades_configuraveis(usuario) -> QuerySet:
    """Unidades cuja configuração o usuário pode escolher na tela (o seletor)."""
    from .models import Unidade
    if not pode_alterar_configuracao(usuario):
        return Unidade.objects.none()
    if usuario.has_perm("viagens.ver_todas_unidades"):
        return Unidade.objects.filter(ativo=True)
    pk = _pk_da_lotacao(usuario)
    return Unidade.objects.filter(pk=pk) if pk is not None else Unidade.objects.none()


def _pk_da_lotacao(usuario) -> int | None:
    from .models import Lotacao
    try:
        return usuario.lotacao.unidade_id
    except (Lotacao.DoesNotExist, AttributeError):
        return None


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
