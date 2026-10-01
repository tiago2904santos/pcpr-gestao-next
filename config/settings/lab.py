"""LAB — ambiente descartável para auditorias destrutivas e testes de carga.

Único ambiente onde ferramentas do agente podem apagar/recriar dados
(ver gestao/plataforma/ambiente.py e docs/adr/0010-ambientes-e-segredos.md).
"""

from .base import *  # noqa: F403

APP_ENV = "lab"
DEBUG = env_bool("DJANGO_DEBUG", True)  # noqa: F405
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}
