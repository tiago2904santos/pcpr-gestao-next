"""System checks que impedem configurações perigosas de subir."""

from __future__ import annotations

from django.conf import settings
from django.core import checks

from .ambiente import AMBIENTES


@checks.register(checks.Tags.security, deploy=True)
def verificar_ambiente(app_configs, **kwargs):
    erros = []
    if settings.APP_ENV not in AMBIENTES:
        erros.append(checks.Error(f"APP_ENV inválido: {settings.APP_ENV}", id="plataforma.E001"))
    if settings.APP_ENV in {"staging", "production"}:
        if settings.DEBUG:
            erros.append(checks.Error("DEBUG ligado fora de DEV/LAB.", id="plataforma.E002"))
        if "insecure" in settings.SECRET_KEY:
            erros.append(
                checks.Error("SECRET_KEY de desenvolvimento em uso.", id="plataforma.E003")
            )
    return erros
