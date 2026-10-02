"""DEV — máquina do desenvolvedor. Dados fictícios, DEBUG ligado."""

from .base import *  # noqa: F403

APP_ENV = "dev"
DEBUG = True
INTERNAL_IPS = ["127.0.0.1"]

# Acesso de fora da maquina (celular na rede local, tunnel HTTPS): os hosts vêm de
# DJANGO_ALLOWED_HOSTS (base) e as origens de POST precisam ser declaradas aqui, senão o
# CSRF recusa. Com um tunnel que termina o TLS, DJANGO_ATRAS_DE_PROXY=true faz o Django
# reconhecer o esquema https. `scripts/tunnel.ps1` define as três — ver docs/ops/tunnel.md.
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")  # noqa: F405
if env_bool("DJANGO_ATRAS_DE_PROXY", False):  # noqa: F405
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}

# Serve estáticos direto das pastas de origem (sem collectstatic em teste/dev).
WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True

# Rotas reais na demonstração/desenvolvimento: servidor público do OSRM (sem chave; uso leve).
# Produção configura o próprio (ROTAS_PROVEDOR/ROTAS_URL) — ver docs/ops/rotas.md.
ROTAS_PROVEDOR = env("ROTAS_PROVEDOR", "osrm")  # noqa: F405
ROTAS_URL = env("ROTAS_URL", "https://router.project-osrm.org")  # noqa: F405
