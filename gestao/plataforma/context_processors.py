from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest

from . import ambiente
from .navegacao import navegacao_para


def plataforma(request: HttpRequest) -> dict[str, Any]:
    return {
        "instituicao": settings.INSTITUICAO,
        "app_env": ambiente.atual(),
        "navegacao": navegacao_para(request),
    }
