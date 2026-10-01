"""TEST — suíte automatizada (pytest). Banco PostgreSQL real, nunca SQLite."""

from .base import *  # noqa: F403

APP_ENV = "test"
DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}
MEDIA_ROOT = BASE_DIR / "var" / "test-media"  # noqa: F405
