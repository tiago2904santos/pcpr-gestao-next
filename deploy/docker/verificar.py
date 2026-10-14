"""`check --deploy` da implantação (falha em ERROR; avisos são exibidos).

Única exceção, explícita: sem SMTP autorizado e com NOTIFICACOES_POR_EMAIL desligado, o
backend de e-mail "console" é intencional (nada sai da máquina — gestao/plataforma/
notificacoes.py), então mail.E001 do Django 6.1 não bloqueia. Com SMTP ou notificações
ligadas, o check volta a valer integralmente.
"""

from __future__ import annotations

import os
import sys

import django

sys.path.insert(0, os.environ.get("PCPR_APP_DIR", "/app"))
django.setup()

from django.conf import settings  # noqa: E402
from django.core.management import call_command  # noqa: E402

silenciar = [c for c in os.environ.get("PCPR_CHECK_SILENCIAR", "").split(",") if c.strip()]
if not getattr(settings, "NOTIFICACOES_POR_EMAIL", False) and not getattr(
        settings, "EMAIL_HOST_SMTP", ""):
    silenciar.append("mail.E001")
settings.SILENCED_SYSTEM_CHECKS = [*settings.SILENCED_SYSTEM_CHECKS, *silenciar]
if silenciar:
    sys.stdout.write(f"check --deploy: ignorando {', '.join(silenciar)} (ver verificar.py)\n")
call_command("check", deploy=True, fail_level=os.environ.get("PCPR_CHECK_NIVEL", "ERROR"))
