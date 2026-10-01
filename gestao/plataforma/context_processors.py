from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest

from . import ambiente
from .navegacao import navegacao_para


def plataforma(request: HttpRequest) -> dict[str, Any]:
    return {
        "papel_principal": _papel(request),
        "instituicao": settings.INSTITUICAO,
        "app_env": ambiente.atual(),
        "navegacao": navegacao_para(request),
    }


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
