"""Download adiado: primeiro comando, cache, cancelamento e falhas sem envio automático."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Route, expect

from .conftest import rodar_axe, salvar_relatorio

pytestmark = pytest.mark.e2e


def _observar(pg: Page):
    pedidos = []
    pg.on("request", lambda r: pedidos.append((r.method, r.url)))
    return pedidos


def _modulo(pedidos):
    return [url for _, url in pedidos if urlsplit(url).path.endswith("/componentes/baixar.js")]


def _origem(pg: Page):
    return pg.locator("[data-baixar-documentos]").first


def _pronto(pg: Page):
    janela = pg.locator("#dialogo-baixar")
    expect(janela).to_be_visible()
    expect(janela.locator("input[name=itens]")).to_have_count(3)
    expect(janela.get_by_role("button", name="Baixar", exact=True)).to_be_enabled()
    return janela


def _acompanhar_rota(pg: Page, handler: Callable[[Route], None]):
    """Só libera os asserts após o callback concluir entrega e liberar sua resposta."""
    erros: list[Exception] = []
    pg.locator("html").evaluate(
        "e => e.setAttribute('data-teste-rota-baixar', 'pendente')")

    def acompanhada(rota: Route):
        try:
            handler(rota)
        except Exception as erro:
            # Relançado no teste que iniciou esta rota, nunca tolerado no teardown.
            erros.append(erro)
        finally:
            pg.locator("html").evaluate(
                "e => e.setAttribute('data-teste-rota-baixar', 'concluida')")

    def aguardar():
        expect(pg.locator("html")).to_have_attribute(
            "data-teste-rota-baixar", "concluida", timeout=60000)
        if erros:
            raise erros[0]

    return acompanhada, aguardar


def _buscar_resposta(rota: Route):
    try:
        return rota.fetch(timeout=15000)
    except Exception:
        # Falha inesperada continua sendo relançada, com a requisição finalizada.
        rota.abort(error_code="failed")
        raise


def _entregar_apos_cancelamento(pg: Page, rota: Route, **resposta):
    """Fechar aborta o GET; só esse cancelamento identificado pode recusar fulfill."""
    try:
        rota.fulfill(**resposta)
    except PlaywrightError:
        if pg.is_closed() or rota.request.failure != "net::ERR_ABORTED":
            raise


@pytest.mark.parametrize("rota", ["lista", "resumo", "folha"])
def test_baixar_nao_entra_ao_visitar_tela_ou_menu(logado, dados_e2e, rota):
    pg = logado
    urls = {"lista": "/viagens/oficios/",
            "resumo": f"/viagens/oficios/?resumo={dados_e2e.ids['oficio_emitido']}",
            "folha": f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/editar/"}
    pedidos = _observar(pg)
    pg.goto(urls[rota], wait_until="networkidle")
    if rota == "resumo":
        pg.get_by_role("button", name="Fechar o resumo", exact=True).click()
        expect(pg.locator("#dialogo-resumo")).to_be_hidden()
    pg.click(".perfil")
    pg.keyboard.press("Escape")
    pg.wait_for_load_state("networkidle")
    expect(pg.locator("#dialogo-baixar")).to_be_hidden()
    assert _modulo(pedidos) == []
    assert pg.erros_console == []


@pytest.mark.parametrize("largura", [360, 1440])
def test_primeiro_enter_abre_cache_regras_preferencias_e_arquivo(logado, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.emulate_media(reduced_motion="reduce")
    pedidos = _observar(pg)
    downloads = []
    pg.on("download", lambda d: downloads.append(d.suggested_filename))
    pg.goto("/ui-lab/", wait_until="networkidle")
    assert rodar_axe(pg) == []
    botao = _origem(pg)
    url = urljoin(pg.url, botao.get_attribute("data-baixar-documentos"))
    botao.scroll_into_view_if_needed()
    assert _modulo(pedidos) == []
    botao.focus()
    botao.press("Enter")
    janela = _pronto(pg)
    expect(janela.get_by_role("button", name="Baixar", exact=True)).to_be_focused()
    expect(botao).not_to_have_attribute("aria-busy", "true")
    assert len(_modulo(pedidos)) == 1
    assert pedidos.count(("GET", url)) == 1
    assert ("POST", url) not in pedidos
    assert downloads == []
    caixas = janela.locator("input[name=itens]")
    expect(janela.locator("input[name=itens]:checked")).to_have_count(3)
    janela.get_by_role("button", name="Desmarcar todos", exact=True).click()
    expect(janela.locator("input[name=itens]:checked")).to_have_count(0)
    expect(janela.get_by_role("button", name="Baixar", exact=True)).to_be_disabled()
    caixas.first.check()
    expect(janela.get_by_role("radio", name="Um PDF só", exact=True)).to_be_disabled()
    janela.get_by_role("button", name="Marcar todos", exact=True).click()
    expect(janela.get_by_role("radio", name="Um PDF só", exact=True)).to_be_enabled()
    janela.locator("label[for=baixar-docx]").click()
    expect(janela.get_by_role("radio", name="Um PDF só", exact=True)).to_be_disabled()
    expect(janela.locator("[data-baixar-versao]")).to_be_hidden()
    janela.locator("label[for=baixar-pdf]").click()
    expect(janela.locator("[data-baixar-versao]")).to_be_visible()
    janela.locator("label[for=baixar-original]").click()
    janela.locator("label[for=baixar-unico]").click()
    janela.evaluate("async d => { await Promise.all(d.getAnimations().map(a => a.finished)); }")
    pasta = Path("artifacts/baixar-carga")
    pasta.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(pasta / f"baixar-{largura}.png"))
    # A página inteira foi auditada antes; com dialog modal, a superfície operável é ele.
    violacoes = pg.evaluate("""async () => (await axe.run(
        document.querySelector('#dialogo-baixar'), {
        runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']},
        resultTypes: ['violations']
    })).violations""")
    salvar_relatorio(f"baixar-carga-axe-{largura}.json", violacoes)
    assert violacoes == []
    with pg.expect_download() as recebido:
        janela.get_by_role("button", name="Baixar", exact=True).click()
    assert recebido.value.suggested_filename == "ui-lab-exemplo.txt"
    expect(janela).to_be_hidden()
    expect(botao).to_be_focused()
    assert pedidos.count(("POST", url)) == 1
    assert downloads == ["ui-lab-exemplo.txt"]
    botao.press("Space")
    janela = _pronto(pg)
    expect(janela.get_by_role("radio", name="Um PDF só", exact=True)).to_be_checked()
    expect(janela.get_by_role("radio", name="Original", exact=True)).to_be_checked()
    assert len(_modulo(pedidos)) == 1
    assert pedidos.count(("GET", url)) == 2
    pg.keyboard.press("Escape")
    expect(janela).to_be_hidden()
    expect(botao).to_be_focused()
    assert pg.erros_console == []


@pytest.mark.parametrize("durante_import", ["repetir", "cancelar", "remover"])
def test_primeiro_import_nao_duplica_acao_e_respeita_cancelamento(logado, durante_import):
    pg = logado
    pedidos = _observar(pg)
    pg.goto("/ui-lab/", wait_until="networkidle")
    botao = _origem(pg)
    url = urljoin(pg.url, botao.get_attribute("data-baixar-documentos"))

    def entregar(rota: Route):
        resposta = _buscar_resposta(rota)
        try:
            expect(botao).to_have_attribute("aria-busy", "true")
            if durante_import == "repetir":
                expect(botao).to_be_focused()
                botao.press("Enter", timeout=5000)
            elif durante_import == "cancelar":
                pg.keyboard.press("Escape")
            else:
                botao.evaluate("e => e.remove()")
        finally:
            try:
                rota.fulfill(response=resposta)
            finally:
                resposta.dispose()

    handler, aguardar = _acompanhar_rota(pg, entregar)
    pg.route("**/componentes/baixar.js", handler, times=1)
    botao.click()
    aguardar()
    assert len(_modulo(pedidos)) == 1
    if durante_import == "repetir":
        _pronto(pg)
        assert pedidos.count(("GET", url)) == 1
    else:
        expect(pg.locator("#dialogo-baixar")).to_be_hidden()
        assert ("GET", url) not in pedidos
        if durante_import == "cancelar":
            expect(botao).not_to_have_attribute("aria-busy", "true")
            botao.press("Enter")
            _pronto(pg)
            assert pedidos.count(("GET", url)) == 1
    assert ("POST", url) not in pedidos
    assert pg.erros_console == []


def test_falha_do_import_anuncia_orienta_recarregar_e_preserva_foco(logado):
    pg = logado
    pedidos = _observar(pg)
    pg.goto("/ui-lab/", wait_until="networkidle")
    pg.route("**/componentes/baixar.js",
             lambda rota: rota.fulfill(status=503, content_type="text/javascript", body=""), times=1)
    botao = _origem(pg)
    url = urljoin(pg.url, botao.get_attribute("data-baixar-documentos"))
    botao.click()
    expect(pg.locator("pc-toasts .toast--perigo")).to_contain_text(
        "Não foi possível abrir os documentos. Recarregue a página e tente de novo.")
    expect(pg.locator("#dialogo-baixar")).to_be_hidden()
    expect(botao).to_be_focused()
    expect(botao).not_to_have_attribute("aria-busy", "true")
    assert ("GET", url) not in pedidos and ("POST", url) not in pedidos
    # Erros esperados deste 503 deliberado, sem tolerar qualquer outra exceção.
    assert pg.erros_console
    assert all("503" in erro or "Failed to fetch dynamically imported module" in erro
               or "Não foi possível carregar a janela de documentos." in erro
               for erro in pg.erros_console), pg.erros_console
    anteriores = len(pg.erros_console)
    pg.reload(wait_until="networkidle")
    _origem(pg).click()
    _pronto(pg)
    assert len(pg.erros_console) == anteriores


def test_fechar_durante_get_nao_rouba_foco_ao_concluir(logado):
    pg = logado
    pg.goto("/ui-lab/", wait_until="networkidle")
    botao = _origem(pg)
    url = urljoin(pg.url, botao.get_attribute("data-baixar-documentos"))
    janela = pg.locator("#dialogo-baixar")

    def entregar(rota: Route):
        resposta = _buscar_resposta(rota)
        try:
            expect(janela).to_be_visible()
            janela.get_by_role("button", name="Fechar", exact=True).click(timeout=5000)
            expect(janela).to_be_hidden()
            pg.locator(".perfil").focus()
        finally:
            try:
                _entregar_apos_cancelamento(pg, rota, response=resposta)
            finally:
                resposta.dispose()

    handler, aguardar = _acompanhar_rota(pg, entregar)
    pg.route(url, handler, times=1)
    botao.click()
    aguardar()
    expect(janela).to_be_hidden()
    expect(pg.locator(".perfil")).to_be_focused()
    assert pg.erros_console == []


def test_reabrir_durante_get_descarta_resposta_antiga_divergente(logado):
    pg = logado
    pedidos = _observar(pg)
    pg.goto("/ui-lab/", wait_until="networkidle")
    botao = _origem(pg)
    url = urljoin(pg.url, botao.get_attribute("data-baixar-documentos"))
    janela = pg.locator("#dialogo-baixar")

    def entregar_antiga(rota: Route):
        # Completa esta rota no próprio handler. A segunda leitura usa o endpoint real.
        try:
            expect(janela).to_be_visible()
            janela.get_by_role("button", name="Fechar", exact=True).click(timeout=5000)
            expect(janela).to_be_hidden()
            expect(botao).to_be_focused()
            botao.press("Enter", timeout=5000)
            _pronto(pg)
        finally:
            _entregar_apos_cancelamento(pg, rota, status=200, json={"itens": [{
                "valor": "antigo", "nome": "Resposta antiga que deve ser descartada",
                "detalhe": "", "estado": "", "assinado": False,
            }]})

    handler, aguardar = _acompanhar_rota(pg, entregar_antiga)
    pg.route(url, handler, times=1)
    botao.click()
    aguardar()
    janela = _pronto(pg)
    expect(janela).not_to_contain_text("Resposta antiga que deve ser descartada")
    expect(janela.get_by_role("button", name="Baixar", exact=True)).to_be_focused()
    assert pedidos.count(("GET", url)) == 2
    assert ("POST", url) not in pedidos
    assert pg.erros_console == []
