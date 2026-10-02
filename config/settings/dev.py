"""DEV — máquina do desenvolvedor. Dados fictícios, DEBUG ligado."""

from .base import *  # noqa: F403

APP_ENV = "dev"
DEBUG = True
INTERNAL_IPS = ["127.0.0.1"]
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
