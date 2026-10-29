"""Autorização da automação (fonte única; views e serviços usam estas funções).

- **ver**: histórico de comunicações e recebimentos da sua unidade (`view_comunicacao`);
- **operar**: contatos e opt-in, aprovar/cancelar envios, tratar exceções (`operar_automacao`);
- **administrar**: chaves de liga/desliga, canal e lista de testadores (`administrar_automacao`).

Escopo por unidade, como em Viagens: o que tem unidade só aparece para quem é lotado nela
(ou tem `ver_todas_unidades_automacao`); fora do escopo é 404 na tela.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db.models import Q, QuerySet


def exigir(condicao: bool, mensagem: str = "Você não tem permissão para esta ação.") -> None:
    if not condicao:
        raise PermissionDenied(mensagem)


def _autenticado(usuario) -> bool:
    return bool(getattr(usuario, "is_authenticated", False) and usuario.is_active)


def pode_ver(usuario) -> bool:
    return _autenticado(usuario) and usuario.has_perm("automacao.view_comunicacao")


def pode_operar(usuario) -> bool:
    return pode_ver(usuario) and usuario.has_perm("automacao.operar_automacao")


def pode_administrar(usuario) -> bool:
    return pode_ver(usuario) and usuario.has_perm("automacao.administrar_automacao")


def ve_todas_unidades(usuario) -> bool:
    return pode_ver(usuario) and usuario.has_perm("automacao.ver_todas_unidades_automacao")


def unidade_do_usuario(usuario) -> int | None:
    lotacao = getattr(usuario, "lotacao", None) if _autenticado(usuario) else None
    return getattr(lotacao, "unidade_id", None)


def filtrar_por_unidade(usuario, qs: QuerySet, campo: str = "unidade") -> QuerySet:
    """O recorte da unidade. Sem unidade (ex.: mensagem de número desconhecido) só vê quem
    administra ou vê todas as unidades."""
    if not pode_ver(usuario):
        return qs.none()
    if ve_todas_unidades(usuario) or pode_administrar(usuario):
        return qs
    unidade = unidade_do_usuario(usuario)
    if unidade is None:
        return qs.none()
    return qs.filter(Q(**{f"{campo}_id": unidade}))


def pode_ver_objeto(usuario, obj) -> bool:
    if not pode_ver(usuario):
        return False
    if ve_todas_unidades(usuario) or pode_administrar(usuario):
        return True
    unidade = getattr(obj, "unidade_id", None)
    return unidade is not None and unidade == unidade_do_usuario(usuario)


def pode_operar_objeto(usuario, obj) -> bool:
    return pode_operar(usuario) and pode_ver_objeto(usuario, obj)


def pode_cuidar_do_contato(usuario, contato_ou_servidor) -> bool:
    """Contato é do servidor: a equipe da unidade dele (ou quem vê todas) cuida."""
    if not pode_operar(usuario):
        return False
    if ve_todas_unidades(usuario) or pode_administrar(usuario):
        return True
    servidor = getattr(contato_ou_servidor, "servidor", contato_ou_servidor)
    unidade = getattr(servidor, "unidade_id", None)
    return unidade is None or unidade == unidade_do_usuario(usuario)
