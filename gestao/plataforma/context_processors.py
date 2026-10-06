from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest
from django.utils.functional import SimpleLazyObject

from . import ambiente
from .navegacao import navegacao_para, pagina_anterior


def plataforma(request: HttpRequest) -> dict[str, Any]:
    return {
        "papel_principal": _papel(request),
        "instituicao": settings.INSTITUICAO,
        "app_env": ambiente.atual(),
        "demo_ativo": ambiente.demo_ativo(),
        "navegacao": navegacao_para(request),
        # Botão "Voltar para …" quando se entra numa área vindo de outra.
        "pagina_anterior": pagina_anterior(request),
        # O ponto do sino: uma contagem (índice usuario+lida), só quando o cabeçalho a lê.
        "notificacoes_nao_lidas": SimpleLazyObject(
            lambda: _nao_lidas(getattr(request, "user", None))),
    }


def _nao_lidas(usuario) -> int:
    from .notificacoes import nao_lidas
    return nao_lidas(usuario)


ROTULOS_PAPEIS = {
    "OPERADOR_VIAGENS": "Operador de viagens",
    "GESTOR_VIAGENS": "Gestor de viagens",
    "CONSULTA": "Consulta",
    "ADMINISTRADOR": "Administrador",
}


def _papel(request: HttpRequest) -> str:
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return ""
    if usuario.is_superuser:
        return "Administrador do sistema"
    nomes = [g.name for g in usuario.groups.all()]
    for chave in ("GESTOR_VIAGENS", "ADMINISTRADOR", "OPERADOR_VIAGENS", "CONSULTA"):
        if chave in nomes:
            return ROTULOS_PAPEIS[chave]
    return "Usuário"
