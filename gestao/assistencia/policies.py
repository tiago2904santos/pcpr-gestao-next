"""Autorização da assistência por IA (fonte única; views e serviços usam estas funções).

- **administrar**: ligar/desligar usos, modo, limites e tetos de orçamento
  (`assistencia.administrar_ia`);
- **ver o painel**: uso, tokens e custo estimado, sem o texto das sugestões
  (`assistencia.ver_painel_ia`, ou quem administra);
- **pedir, ver e decidir uma sugestão**: a política do CONTEXTO dono do registro (o gancho do
  uso: quem edita o RT decide a sugestão do RT). Fora do escopo é 404 na tela;
- **Central de ajuda**: qualquer pessoa autenticada.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied

from . import ganchos


def exigir(condicao: bool, mensagem: str = "Você não tem permissão para esta ação.") -> None:
    if not condicao:
        raise PermissionDenied(mensagem)


def _autenticado(usuario) -> bool:
    return bool(getattr(usuario, "is_authenticated", False) and usuario.is_active)


def pode_administrar(usuario) -> bool:
    return _autenticado(usuario) and usuario.has_perm("assistencia.administrar_ia")


def pode_ver_painel(usuario) -> bool:
    return _autenticado(usuario) and (usuario.has_perm("assistencia.ver_painel_ia")
                                      or pode_administrar(usuario))


def pode_usar_central(usuario) -> bool:
    return _autenticado(usuario)


def pode_pedir(usuario, uso: ganchos.UsoIA, recurso_id: str) -> bool:
    if not _autenticado(usuario):
        return False
    try:
        return bool(uso.pode_pedir(usuario, recurso_id))
    except ganchos.RecursoInexistente:
        return False


def pode_ver(usuario, uso: ganchos.UsoIA | None, recurso_id: str) -> bool:
    if uso is None or not _autenticado(usuario):
        return False
    try:
        return bool(uso.pode_ver(usuario, recurso_id))
    except ganchos.RecursoInexistente:
        return False


def pode_decidir(usuario, uso: ganchos.UsoIA | None, recurso_id: str) -> bool:
    return uso is not None and pode_pedir(usuario, uso, recurso_id)
