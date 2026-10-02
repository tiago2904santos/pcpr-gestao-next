"""TEST — suíte automatizada (pytest). Banco PostgreSQL real, nunca SQLite."""

from .base import *  # noqa: F403

APP_ENV = "test"
DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}
MEDIA_ROOT = BASE_DIR / "var" / "test-media"  # noqa: F405

# Serve estáticos direto das pastas de origem (sem collectstatic em teste/dev).
WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True

# Testes não dependem de rede: rotas por estimativa e mapa sem mosaico externo.
ROTAS_PROVEDOR = "estimativa"
MAPA_TILES_URL = ""
_SEM_MOSAICO = [v for v in SECURE_CSP["img-src"] if not v.startswith("http")]  # noqa: F405
SECURE_CSP = {**SECURE_CSP, "img-src": _SEM_MOSAICO}  # noqa: F405
