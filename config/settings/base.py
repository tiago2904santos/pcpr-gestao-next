"""Configuração comum a todos os ambientes.

Os ambientes (LAB, DEV, STAGING, PRODUCTION, TEST) herdam deste módulo e só
sobrescrevem o que for estritamente necessário. Segredos vêm exclusivamente de
variáveis de ambiente — nunca do Git (ver docs/adr/0010-ambientes-e-segredos.md).
"""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _carregar_dotenv(caminho: Path) -> None:
    """Carrega KEY=VALUE de um .env local sem sobrescrever o ambiente real.

    Conveniência de DEV/LAB; em STAGING/PRODUCTION as variáveis vêm do
    gerenciador de serviços (systemd/contêiner) e não existe .env.
    """
    if not caminho.is_file():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.split(" #", 1)[0].strip())


_carregar_dotenv(BASE_DIR / ".env")

# Ambiente lógico. Controla salvaguardas (ver gestao/plataforma/ambiente.py).
APP_ENV = os.environ.get("APP_ENV", "dev").lower()


def env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        raise ImproperlyConfigured(f"Variável de ambiente obrigatória ausente: {name}")
    return value or ""


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "sim"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# Entrada de demonstração (sem senha) — só tem efeito com APP_ENV=preview; em qualquer outro
# ambiente a combinação é recusada (production_base, check plataforma.E004 e
# ambiente.demo_ativo()). Ver docs/adr/0011-ambiente-preview-demo.md.
DEMO_MODE = env_bool("DEMO_MODE", False)

SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-key-somente-local")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django_htmx",
    # Plataforma (núcleo técnico compartilhado)
    "gestao.plataforma",
    # Contextos de negócio
    "gestao.identidade",
    "gestao.cadastros",
    "gestao.viagens",
    "gestao.painel",
    "gestao.ui_lab",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "gestao.plataforma.middleware.ContextoAuditoriaMiddleware",
    "gestao.plataforma.middleware.MedicaoServidorMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csp",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "gestao.plataforma.context_processors.plataforma",
            ],
            "builtins": ["gestao.plataforma.templatetags.ui"],
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "pcpr_gestao"),
        "USER": env("POSTGRES_USER", "pcpr_gestao"),
        "PASSWORD": env("POSTGRES_PASSWORD", ""),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "ATOMIC_REQUESTS": False,
        "OPTIONS": {"application_name": "pcpr-gestao"},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "identidade.Usuario"
AUTHENTICATION_BACKENDS = ["gestao.identidade.backends.EmailBackend"]
LOGIN_URL = "identidade:entrar"
LOGIN_REDIRECT_URL = "painel:inicio"
LOGOUT_REDIRECT_URL = "identidade:entrar"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "var" / "static"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_ROOT = BASE_DIR / "var" / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Sessão e cookies
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 10  # um turno de trabalho
SESSION_COOKIE_NAME = "pcpr_sessao"
CSRF_COOKIE_NAME = "pcpr_csrf"
CSRF_COOKIE_HTTPONLY = False  # HTMX lê o token do <meta>, não do cookie
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# Content Security Policy nativa do Django 6: nenhum script inline sem nonce,
# nenhum recurso de terceiros.
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE],
    "style-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:"],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "form-action": [CSP.SELF],
    "base-uri": [CSP.SELF],
    "object-src": [CSP.NONE],
}

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simples": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simples"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
        "weasyprint": {"level": "WARNING"},
        "fontTools": {"level": "WARNING"},
    },
}

# Identidade institucional exibida no shell e nos documentos.
INSTITUICAO = {
    "sigla": "PCPR",
    "nome": "Polícia Civil do Paraná",
    "produto": "Gestão de Eventos e Viagens",
}

# Domínio de e-mail institucional aceito no login (vazio = qualquer).
DOMINIO_EMAIL_INSTITUCIONAL = env("DOMINIO_EMAIL_INSTITUCIONAL", "pc.pr.gov.br")

# Tentativas de login: bloqueio progressivo por e-mail+IP.
LOGIN_MAX_TENTATIVAS = 5
LOGIN_JANELA_SEGUNDOS = 15 * 60

# Orçamento de consultas SQL por requisição (alerta em DEV/LAB e falha em teste).
ORCAMENTO_SQL_POR_REQUISICAO = 25
