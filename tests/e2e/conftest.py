"""Infra de testes de navegador (Playwright sync + live_server do pytest-django).

Marcadores: e2e, a11y, visual, perf. Capturas e relatórios vão para artifacts/.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Locator, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

RAIZ = Path(__file__).resolve().parents[2]
ARTEFATOS = RAIZ / "artifacts"
AXE = RAIZ / "tests" / "_vendor" / "axe.min.js"
LARGURAS = [360, 390, 768, 1024, 1280, 1440]
SENHA = "senha-e2e-123"


# Os controles da página são importados sob demanda (app.js): logo após uma navegação, um
# <select> ainda é o nativo e um formulário ainda não tem autosave. Agir nesse instante pega o
# elemento no meio da troca — e numa máquina lenta (CI) isso acontece. Toda ação espera o sinal
# <html data-controladores="prontos"> (páginas sem app.js passam direto).
CONTROLADORES_PRONTOS = """() => document.documentElement.dataset.controladores !== 'carregando'
    && (document.documentElement.dataset.controladores === 'prontos'
        || !document.querySelector('script[src*="/js/app."]'))"""
_ACOES = ("click", "dblclick", "fill", "press", "press_sequentially", "type", "check",
          "uncheck", "set_checked", "select_option", "set_input_files", "hover", "tap")


def aguardar_controladores(pg: Page) -> None:
    with contextlib.suppress(PlaywrightTimeout, PlaywrightError):
        pg.main_frame.wait_for_function(CONTROLADORES_PRONTOS, timeout=15_000)


def estabilizar(pg: Page) -> None:
    """Antes de medir geometria: controles montados, fontes carregadas e o layout assentado
    (dois quadros) — medir no instante da navegação pegava o rótulo antes da fonte final."""
    aguardar_controladores(pg)
    pg.evaluate("""() => document.fonts.ready.then(() => new Promise(
        r => requestAnimationFrame(() => requestAnimationFrame(() => r(true)))))""")


def _esperando(original):
    def acao(self, *args, **kwargs):
        aguardar_controladores(self.page if isinstance(self, Locator) else self)
        return original(self, *args, **kwargs)

    acao.__wrapped__ = original
    return acao


for _alvo in (Locator, Page):
    for _nome in _ACOES:
        if hasattr(_alvo, _nome) and not hasattr(getattr(_alvo, _nome), "__wrapped__"):
            setattr(_alvo, _nome, _esperando(getattr(_alvo, _nome)))


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


# Transições e animações finitas em curso (cor do rótulo ao trocar de estado, esmaecer da lista):
# o axe mede a cor do instante e acusaria um meio-termo que ninguém lê. As infinitas (fita de
# carregamento) não terminam e ficam de fora.
ANIMACOES_EM_CURSO = """() => document.getAnimations().some(a => a.playState === 'running'
    && a.effect && a.effect.getComputedTiming().iterations !== Infinity)"""


def rodar_axe(pg: Page) -> list[dict]:
    # Sem estabilizar em 5 s (alguma transição em laço), mede assim mesmo.
    with contextlib.suppress(PlaywrightTimeout):
        pg.wait_for_function(f"() => !({ANIMACOES_EM_CURSO})()", timeout=5_000)
    # evaluate() via CDP não é bloqueado pela CSP (add_script_tag seria).
    pg.evaluate(AXE.read_text() + "\n;true")
    # Com uma janela modal aberta, o resto da página é inerte (sem clique nem foco): o alvo de
    # toque (WCAG 2.5.8) só se mede dentro dela — o que está por baixo aparecia "encoberto".
    # As demais regras seguem auditando a página inteira.
    resultado = pg.evaluate(
        """async () => {
            const base = {
                runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']},
                resultTypes: ['violations'],
            };
            const modal = document.querySelector('dialog:modal');
            if (!modal) return await axe.run(document, base);
            const pagina = await axe.run(document, {...base, rules: {'target-size': {enabled: false}}});
            const alvos = await axe.run(modal, {resultTypes: ['violations'],
                                                runOnly: {type: 'rule', values: ['target-size']}});
            return {violations: [...pagina.violations, ...alvos.violations]};
        }"""
    )
    return resultado["violations"]


def nome_seguro(texto: str) -> str:
    """Nome de arquivo válido em qualquer sistema e no upload de artefatos do CI."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", texto).strip("_") or "raiz"


def salvar_relatorio(nome: str, dados: object) -> None:
    ARTEFATOS.mkdir(exist_ok=True)
    (ARTEFATOS / nome_seguro(nome)).write_text(json.dumps(dados, ensure_ascii=False, indent=2))
