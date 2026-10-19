"""Endurecimento comum a STAGING e PRODUCTION."""

from .base import *  # noqa: F403

if DEMO_MODE:  # noqa: F405
    raise ImproperlyConfigured(  # noqa: F405
        "DEMO_MODE=true é proibido em STAGING/PRODUCTION: a entrada sem senha existe só no "
        "ambiente PREVIEW (docs/adr/0011-ambiente-preview-demo.md)."
    )

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)  # noqa: F405
DATABASES["default"]["PASSWORD"] = env("POSTGRES_PASSWORD", required=True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Caminhos chamados só pela rede interna do Docker, em HTTP (ex.: "^api/automacao/" para o n8n
# atrás do Traefik do template da Hostinger — deploy/hostinger/). O proxy público nunca os expõe.
SECURE_REDIRECT_EXEMPT = env_list("DJANGO_SSL_REDIRECT_EXEMPT")  # noqa: F405
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")  # noqa: F405
# Preload de HSTS é decisão do domínio institucional (afeta subdomínios fora deste
# sistema); fica a cargo da equipe de infraestrutura — docs/ops/deploy.md.
SILENCED_SYSTEM_CHECKS = ["security.W021"]
# Sem SMTP e sem notificações por e-mail, o backend "console" é intencional (nada sai da
# máquina — gestao/plataforma/notificacoes.py); com SMTP ou notificações, o check vale.
if not EMAIL_HOST_SMTP and not NOTIFICACOES_POR_EMAIL:  # noqa: F405
    SILENCED_SYSTEM_CHECKS = [*SILENCED_SYSTEM_CHECKS, "mail.E001"]
