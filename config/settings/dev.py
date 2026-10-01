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
