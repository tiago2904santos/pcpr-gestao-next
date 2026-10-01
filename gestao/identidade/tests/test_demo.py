"""Entrada DEMO (sem senha) — existe só no PREVIEW com DEMO_MODE; produção nunca aceita.

Camadas testadas: settings (production_base recusa), startup (`ready`), system check
(E004/E005), backend (`DemoBackend`), formulário de login, middleware de entrada direta e
indicadores visuais. ADR 0011.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.urls import reverse

from gestao.identidade.backends import LOGIN_DEMO, DemoBackend
from gestao.identidade.middleware import COOKIE_SAIU
from gestao.identidade.models import Usuario
from gestao.plataforma import ambiente
from gestao.plataforma.checks import verificar_ambiente

pytestmark = pytest.mark.django_db

RAIZ = Path(__file__).resolve().parents[3]
DEMO = "gestao.identidade.backends.DemoBackend"
MIDDLEWARE_DEMO = "gestao.identidade.middleware.EntradaDemoMiddleware"


def _middleware_preview() -> list[str]:
    i = settings.MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware")
    return [*settings.MIDDLEWARE[: i + 1], MIDDLEWARE_DEMO, *settings.MIDDLEWARE[i + 1 :]]


def preview_demo():
    """Mesmo que config.settings.preview com DEMO_MODE=true (backend + middleware)."""
    return override_settings(
        APP_ENV="preview", DEMO_MODE=True,
        AUTHENTICATION_BACKENDS=[*settings.AUTHENTICATION_BACKENDS, DEMO],
        MIDDLEWARE=_middleware_preview(),
    )


@pytest.fixture
def usuario_demo(db):
    from django.contrib.auth.models import Group

    usuario = Usuario.objects.create_user(LOGIN_DEMO, "demo@demo.invalid", None,
                                          nome="Operador de Demonstração")
    usuario.groups.add(Group.objects.get(name="GESTOR_VIAGENS"))
    return usuario


def _entrar(client, usuario="", senha=""):
    return client.post(reverse("identidade:entrar"), {"username": usuario, "password": senha})


def _usuario_da_sessao(client) -> str | None:
    pk = client.session.get("_auth_user_id")
    return Usuario.objects.get(pk=pk).login if pk else None


# ------------------------------------------------------------------ login DEMO
def test_tela_de_login_existe_e_e_a_mesma_no_demo(client, usuario_demo):
    normal = client.get(reverse("identidade:entrar")).content.decode()
    assert "Acesso ao sistema" in normal and "Ambiente de demonstração" not in normal
    with preview_demo():
        demo = client.get(reverse("identidade:entrar")).content.decode()
    assert "Acesso ao sistema" in demo and 'name="username"' in demo
    assert "Ambiente de demonstração" in demo and "PREVIEW" in demo


def test_demo_campos_vazios_entra_como_usuario_demo(client, usuario_demo):
    with preview_demo():
        resposta = _entrar(client)
        assert resposta.status_code == 302 and resposta["Location"] == reverse("painel:inicio")
        assert _usuario_da_sessao(client) == LOGIN_DEMO
        pagina = client.get(reverse("painel:inicio"))
    assert pagina.status_code == 200 and "Operador de Demonstração" in pagina.content.decode()


def test_demo_com_credenciais_normais_segue_o_fluxo_normal(client, usuario, usuario_demo):
    with preview_demo():
        assert _entrar(client, "operador", "senha-forte-123").status_code == 302
        assert _usuario_da_sessao(client) == "operador"
        client.logout()
        errada = _entrar(client, "operador", "errada")
    assert errada.status_code == 200 and "Usuário ou senha incorretos" in errada.content.decode()
    assert _usuario_da_sessao(client) is None  # senha errada nunca cai no usuário demo


def test_demo_sem_usuario_demo_mostra_como_resolver(client):
    with preview_demo():
        resposta = _entrar(client)
    assert resposta.status_code == 200 and "semear_demo" in resposta.content.decode()


def test_producao_recusa_login_vazio(client, usuario_demo):
    with override_settings(APP_ENV="production", DEMO_MODE=False):
        resposta = _entrar(client)
    assert resposta.status_code == 200 and "obrigatório" in resposta.content.decode()
    assert _usuario_da_sessao(client) is None


def test_bypass_nao_liga_por_acidente(client, usuario_demo):
    """Backend e middleware instalados mas fora do PREVIEW (ou sem DEMO_MODE): nada muda."""
    for app_env, demo_mode in [("production", True), ("staging", True), ("dev", True),
                               ("preview", False)]:
        with override_settings(
            APP_ENV=app_env, DEMO_MODE=demo_mode, MIDDLEWARE=_middleware_preview(),
            AUTHENTICATION_BACKENDS=[*settings.AUTHENTICATION_BACKENDS, DEMO],
        ):
            assert not ambiente.demo_ativo()
            assert authenticate(None, demo=True) is None
            assert _entrar(client).status_code == 200
            assert client.get(reverse("viagens:oficios")).status_code == 302  # vai ao login
            assert _usuario_da_sessao(client) is None


def test_backend_demo_exige_pedido_explicito(usuario_demo):
    with preview_demo():
        assert DemoBackend().authenticate(None) is None
        assert DemoBackend().authenticate(None, username="demo", password="") is None
        assert DemoBackend().authenticate(None, demo=True) == usuario_demo
        Usuario.objects.filter(pk=usuario_demo.pk).update(is_active=False)
        assert DemoBackend().authenticate(None, demo=True) is None


# ------------------------------------------------------------------ entrada direta e sessão
def test_entrada_direta_cria_sessao_normal_do_usuario_demo(client, usuario_demo):
    with preview_demo():
        resposta = client.get(reverse("viagens:oficios"))
        assert resposta.status_code == 200
        assert _usuario_da_sessao(client) == LOGIN_DEMO
        assert client.get(reverse("painel:inicio")).status_code == 200  # mesma sessão


def test_sair_volta_ao_login_e_para_a_entrada_automatica(client, usuario_demo):
    with preview_demo():
        client.get(reverse("painel:inicio"))
        saida = client.post(reverse("identidade:sair"))
        assert saida.status_code == 302 and saida["Location"] == reverse("identidade:entrar")
        assert client.cookies[COOKIE_SAIU].value == "1"
        assert _usuario_da_sessao(client) is None
        protegida = client.get(reverse("viagens:oficios"))
        assert protegida.status_code == 302 and "/conta/entrar/" in protegida["Location"]
        # Entrar de novo (campos vazios) limpa a marca de saída.
        assert _entrar(client).status_code == 302
        assert client.cookies[COOKIE_SAIU].value == ""
        assert _usuario_da_sessao(client) == LOGIN_DEMO


def test_indicador_de_demonstracao_no_cabecalho(client, usuario_demo):
    with preview_demo():
        html = client.get(reverse("painel:inicio")).content.decode()
    assert 'class="cabecalho__ambiente"' in html and ">PREVIEW<" in html
    assert "Demonstração · PREVIEW" in html  # menu do usuário
    assert 'class="navegacao__ambiente"' in html  # gaveta do celular


# ------------------------------------------------------------------ configuração e startup
@pytest.mark.parametrize("app_env", ["production", "staging", "dev", "lab", "test"])
def test_startup_falha_com_demo_fora_do_preview(app_env):
    with override_settings(APP_ENV=app_env, DEMO_MODE=True), \
            pytest.raises(ImproperlyConfigured, match="só existe no PREVIEW"):
        ambiente.exigir_demo_somente_no_preview()
    with override_settings(APP_ENV="preview", DEMO_MODE=True):
        ambiente.exigir_demo_somente_no_preview()


def test_check_reprova_demo_fora_do_preview_e_banco_que_nao_e_de_preview(monkeypatch):
    from gestao.plataforma import checks

    with override_settings(APP_ENV="production", DEMO_MODE=True, DEBUG=False,
                           SECRET_KEY="x" * 60):
        assert "plataforma.E004" in {e.id for e in verificar_ambiente(None)}
    preview = override_settings(APP_ENV="preview", DEMO_MODE=True, DEBUG=False,
                                SECRET_KEY="x" * 60)
    monkeypatch.setattr(checks, "nome_do_banco", lambda: "pcpr_gestao")
    with preview:
        assert {e.id for e in verificar_ambiente(None)} == {"plataforma.E005"}
    monkeypatch.setattr(checks, "nome_do_banco", lambda: "pcpr_preview")
    with preview:
        assert verificar_ambiente(None) == []


def _carregar_settings(modulo: str, **env: str) -> subprocess.CompletedProcess:
    ambiente_proc = {k: v for k, v in os.environ.items()
                     if not k.startswith(("DJANGO_", "APP_ENV", "DEMO_MODE", "POSTGRES_"))}
    ambiente_proc.update(env)
    codigo = (f"import json, {modulo} as s; print(json.dumps([s.APP_ENV, s.DEMO_MODE, "
              f"s.AUTHENTICATION_BACKENDS, s.MIDDLEWARE, s.DATABASES['default']['NAME']]))")
    return subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, env=ambiente_proc,  # noqa: S603
                          capture_output=True, text=True, check=False)


@pytest.mark.parametrize("modulo", ["config.settings.production", "config.settings.staging"])
def test_production_e_staging_nao_carregam_com_demo_mode(modulo):
    r = _carregar_settings(modulo, DEMO_MODE="true", DJANGO_SECRET_KEY="k" * 60,
                           POSTGRES_PASSWORD="x")
    assert r.returncode != 0 and "DEMO_MODE=true é proibido" in r.stderr


def test_production_sem_demo_nao_instala_backend_nem_middleware():
    import json

    r = _carregar_settings("config.settings.production", DJANGO_SECRET_KEY="k" * 60,
                           POSTGRES_PASSWORD="x")
    app_env, demo, backends, middleware, _ = json.loads(r.stdout)
    assert app_env == "production" and demo is False
    assert DEMO not in backends and MIDDLEWARE_DEMO not in middleware


def test_preview_com_demo_instala_backend_middleware_e_banco_proprio():
    import json

    r = _carregar_settings("config.settings.preview", DEMO_MODE="true",
                           DJANGO_SECRET_KEY="k" * 60)
    app_env, demo, backends, middleware, banco = json.loads(r.stdout)
    assert (app_env, demo, banco) == ("preview", True, "pcpr_preview")
    assert DEMO in backends
    assert middleware.index(MIDDLEWARE_DEMO) == middleware.index(
        "django.contrib.auth.middleware.AuthenticationMiddleware") + 1
