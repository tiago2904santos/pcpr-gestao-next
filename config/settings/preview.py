"""PREVIEW — demonstração navegável, o mais parecida possível com produção.

Mesmo código, rotas, templates, CSP, WhiteNoise com manifest e gunicorn; banco PostgreSQL
próprio (`pcpr_preview`) só com dados fictícios (`semear_demo`). Com `DEMO_MODE=true`, a
tela de login aceita "Entrar" com os campos vazios e autentica o usuário de demonstração.

Proteções (docs/adr/0011-ambiente-preview-demo.md): `production_base` recusa DEMO_MODE;
o check `plataforma.E004` reprova DEMO_MODE fora do PREVIEW e `plataforma.E005` reprova
banco cujo nome não seja de preview/demo; `ambiente.demo_ativo()` exige as duas condições
em tempo de execução.
"""

from .base import *  # noqa: F403
from .base import AUTHENTICATION_BACKENDS as _BACKENDS_BASE
from .base import MIDDLEWARE as _MIDDLEWARE_BASE

APP_ENV = "preview"
DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)  # noqa: F405
DATABASES["default"]["NAME"] = env("POSTGRES_DB", "pcpr_preview")  # noqa: F405

# Atrás do proxy HTTPS (Codespaces, servidor com TLS) ou direto em http://localhost.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", False)  # noqa: F405
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = env_bool("PREVIEW_HTTPS", False)  # noqa: F405
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")  # noqa: F405

if DEMO_MODE:  # noqa: F405
    AUTHENTICATION_BACKENDS = [*_BACKENDS_BASE, "gestao.identidade.backends.DemoBackend"]
    _depois = _MIDDLEWARE_BASE.index("django.contrib.auth.middleware.AuthenticationMiddleware")
    MIDDLEWARE = [
        *_MIDDLEWARE_BASE[: _depois + 1],
        "gestao.identidade.middleware.EntradaDemoMiddleware",
        *_MIDDLEWARE_BASE[_depois + 1 :],
    ]
