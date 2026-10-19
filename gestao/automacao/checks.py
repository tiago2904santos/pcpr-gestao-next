"""Checks que impedem o canal real de subir onde não pode (ADR 0046)."""

from __future__ import annotations

from django.conf import settings
from django.core import checks


@checks.register(checks.Tags.security)
def verificar_canal(app_configs, **kwargs):
    erros = []
    modo = str((getattr(settings, "WHATSAPP", {}) or {}).get("modo") or "").strip().lower()
    if settings.APP_ENV == "preview" and modo == "cloud_api":
        erros.append(checks.Error(
            "WHATSAPP_MODO=cloud_api no PREVIEW: a demonstração pública é sempre simulada.",
            hint="Use o LAB dedicado para a Cloud API; no PREVIEW deixe WHATSAPP_MODO vazio.",
            id="automacao.E001"))
    if getattr(settings, "DEMO_MODE", False) and modo == "cloud_api":
        erros.append(checks.Error("DEMO_MODE com WhatsApp real: nunca.", id="automacao.E002"))
    if modo == "cloud_api" and settings.APP_ENV not in ("dev", "test", "preview"):
        from gestao.integracoes.whatsapp import config

        faltam = config.carregar().faltantes()
        if faltam:
            erros.append(checks.Error(
                f"WHATSAPP_MODO=cloud_api sem {', '.join(faltam)}: o canal ficaria simulado "
                "sem ninguém perceber.", hint="Complete as variáveis WHATSAPP_* ou volte ao "
                "simulado (WHATSAPP_MODO vazio).", id="automacao.E003"))
    return erros
