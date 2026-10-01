"""Endurecimento comum a STAGING e PRODUCTION."""

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)  # noqa: F405
DATABASES["default"]["PASSWORD"] = env("POSTGRES_PASSWORD", required=True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")  # noqa: F405
# Preload de HSTS é decisão do domínio institucional (afeta subdomínios fora deste
# sistema); fica a cargo da equipe de infraestrutura — docs/ops/deploy.md.
SILENCED_SYSTEM_CHECKS = ["security.W021"]
