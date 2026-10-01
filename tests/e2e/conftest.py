"""Infra de testes de navegador (Playwright sync + live_server do pytest-django).

Marcadores: e2e, a11y, visual, perf. Capturas e relatórios vão para artifacts/.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

RAIZ = Path(__file__).resolve().parents[2]
ARTEFATOS = RAIZ / "artifacts"
AXE = RAIZ / "tests" / "_vendor" / "axe.min.js"
LARGURAS = [360, 390, 768, 1024, 1280, 1440]
SENHA = "senha-e2e-123"


@pytest.fixture(scope="session")
def navegador() -> Browser:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def dados_e2e(transactional_db):
    """Cenário fictício completo (usuários, cadastros, ofícios em vários estados)."""
    from gestao.viagens.tests.cenarios import cenario_completo

    return cenario_completo(senha=SENHA)


@pytest.fixture
def pagina(navegador: Browser, live_server, dados_e2e) -> Page:
    contexto = navegador.new_context(
        viewport={"width": 1440, "height": 900}, locale="pt-BR",
        timezone_id="America/Sao_Paulo", base_url=live_server.url,
    )
    pg = contexto.new_page()
    pg.erros_console = []  # type: ignore[attr-defined]
    pg.on("console", lambda m: m.type == "error" and pg.erros_console.append(m.text))  # type: ignore[attr-defined]
    pg.on("pageerror", lambda e: pg.erros_console.append(str(e)))  # type: ignore[attr-defined]
    yield pg
    contexto.close()


def entrar(pg: Page, login: str = "operador", senha: str = SENHA) -> None:
    pg.goto("/conta/entrar/")
    pg.fill("#id_username", login)
    pg.fill("#id_password", senha)
    pg.click("button[type=submit]")
    pg.wait_for_url(lambda url: "/conta/entrar/" not in url)


@pytest.fixture
def logado(pagina: Page) -> Page:
    entrar(pagina)
    return pagina


def rodar_axe(pg: Page) -> list[dict]:
    # evaluate() via CDP não é bloqueado pela CSP (add_script_tag seria).
    pg.evaluate(AXE.read_text() + "\n;true")
    resultado = pg.evaluate(
        """async () => await axe.run(document, {
            runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']},
            resultTypes: ['violations']
        })"""
    )
    return resultado["violations"]


def salvar_relatorio(nome: str, dados: object) -> None:
    ARTEFATOS.mkdir(exist_ok=True)
    (ARTEFATOS / nome).write_text(json.dumps(dados, ensure_ascii=False, indent=2))
