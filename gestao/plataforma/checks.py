"""System checks que impedem configurações perigosas de subir."""

from __future__ import annotations

from django.conf import settings
from django.core import checks

from .ambiente import AMBIENTES


@checks.register(checks.Tags.security)
def verificar_ambiente(app_configs, **kwargs):
    erros = []
    if settings.APP_ENV not in AMBIENTES:
        erros.append(checks.Error(f"APP_ENV inválido: {settings.APP_ENV}", id="plataforma.E001"))
    if getattr(settings, "DEMO_MODE", False) and settings.APP_ENV != "preview":
        erros.append(checks.Error(
            "DEMO_MODE=true só é permitido com APP_ENV=preview (entrada sem senha).",
            hint="Desligue DEMO_MODE ou use config.settings.preview com banco de demonstração.",
            id="plataforma.E004"))
    if settings.APP_ENV == "preview":
        nome = nome_do_banco().lower()
        if "preview" not in nome and "demo" not in nome:
            erros.append(checks.Error(
                f"PREVIEW usando o banco '{nome}': o nome precisa indicar preview/demo, para "
                "nunca apontar para um banco real.", id="plataforma.E005"))
    if settings.APP_ENV in {"preview", "staging", "production"}:
        if settings.DEBUG:
            erros.append(checks.Error("DEBUG ligado fora de DEV/LAB.", id="plataforma.E002"))
        if "insecure" in settings.SECRET_KEY:
            erros.append(
                checks.Error("SECRET_KEY de desenvolvimento em uso.", id="plataforma.E003")
            )
    return erros


def nome_do_banco() -> str:
    return str(settings.DATABASES["default"]["NAME"])
