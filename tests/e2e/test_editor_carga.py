"""Rede do editor: miniaturas esperam a aproximação da seção Documentos."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, Route, expect

pytestmark = pytest.mark.e2e


def _miniaturas(pg: Page):
    return pg.locator("[data-editores] iframe[data-miniatura][src]:not([data-carregando])")


def _indice(pg: Page):
    return pg.locator("[data-editores] .editor--ativo [data-alternar-indice]:visible")


def _esperar_editor(pg: Page):
    total = pg.locator("[data-editores] [data-ir-pagina]").count()
    assert total > 0
    expect(_miniaturas(pg)).to_have_count(total, timeout=15000)
    expect(pg.locator("#editor-oficio [data-salvo]")).not_to_have_text("Carregando…")
    expect(pg.frame_locator("#folha-oficio").locator("[data-regiao='corpo']")).to_be_visible()


SUBSTITUIR = """(interno) => {
    const antigo = document.querySelector('[data-editores]');
    const novo = antigo.cloneNode(true);
    novo.querySelectorAll('iframe').forEach(q => q.removeAttribute('src'));
    novo.querySelectorAll('iframe[data-miniatura]').forEach(q => {
        q.removeAttribute('style'); q.removeAttribute('data-carregando');
    });
    // Equivalente ao fragmento servido: barras começam ocultas, iframes sem src.
    novo.querySelectorAll('.editor__barra').forEach(b => b.hidden = true);
    document.body.dispatchEvent(new CustomEvent('htmx:beforeSwap', {detail: {target: antigo}}));
    if (interno) antigo.replaceChildren(...novo.childNodes);
    else antigo.replaceWith(novo);
    document.body.dispatchEvent(new CustomEvent('htmx:afterSwap', {
        detail: {target: interno ? antigo : novo}
    }));
    return antigo;
}"""


@pytest.mark.parametrize("largura", [360, 1440])
def test_miniaturas_esperam_rolagem_e_editor_continua_funcionando(logado, dados_e2e, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    pedidos = []
    pg.on("request", lambda r: pedidos.append(r.url))
    pk = dados_e2e.ids["oficio_rascunho"]
    pg.goto(f"/viagens/oficios/{pk}/editar/", wait_until="networkidle")
    pg.click(".perfil")
    pg.keyboard.press("Escape")
    pg.wait_for_load_state("networkidle")
    assert not [url for url in pedidos if "miniatura=" in url]
    assert not [url for url in pedidos if "/componentes/editores.js" in url]
    expect(pg.locator("[data-editores] iframe[src]")).to_have_count(0)

    pg.locator("#minuta").scroll_into_view_if_needed()
    _esperar_editor(pg)
    assert [url for url in pedidos if "miniatura=" in url]
    # O índice mantém o comando de abrir/fechar depois da carga adiada.
    botao = _indice(pg)
    expect(botao).to_be_visible()
    antes = botao.get_attribute("aria-expanded")
    assert antes in ("true", "false")
    botao.click()
    expect(botao).to_have_attribute("aria-expanded", "false" if antes == "true" else "true")
    botao.click()
    expect(botao).to_have_attribute("aria-expanded", antes)
    # Gravar texto refaz apenas a miniatura correspondente, como antes.
    miniatura_antes = _miniaturas(pg).first.get_attribute("src")
    assert miniatura_antes
    corpo = pg.frame_locator("#folha-oficio").locator("[data-bloco='saudacao']")
    corpo.click()
    pg.keyboard.press("End")
    pg.keyboard.type(" Carga adiada verificada.")
    expect(pg.locator("#editor-oficio [data-salvo]")).to_have_text(re.compile(r"· v1$"), timeout=15000)
    expect(_miniaturas(pg).first).not_to_have_attribute("src", miniatura_antes, timeout=15000)
    _esperar_editor(pg)
    pasta = Path("artifacts/qa-carga-editores")
    pasta.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(pasta / f"editor-{largura}.png"))
    assert pg.erros_console == []


def test_reposicao_antes_da_visibilidade_e_com_modulo_ja_carregado(logado, dados_e2e):
    pg = logado
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/editar/",
            wait_until="networkidle")
    # O alvo original ainda não apareceu. Repor a caixa não pode perder a observação.
    pg.evaluate(SUBSTITUIR, False)
    expect(pg.locator("[data-editores] iframe[src]")).to_have_count(0)
    pg.locator("#minuta").scroll_into_view_if_needed()
    _esperar_editor(pg)
    # Um pedido sem swap não desliga o índice que já funciona.
    pg.evaluate("""() => document.body.dispatchEvent(new CustomEvent('htmx:beforeSwap', {
        detail: {target: document.querySelector('[data-editores]'), shouldSwap: false}
    }))""")
    indice = _indice(pg)
    aberto = indice.get_attribute("aria-expanded")
    indice.click()
    expect(indice).to_have_attribute("aria-expanded", "false" if aberto == "true" else "true")
    indice.click()
    # Agora o módulo está em cache. Tanto troca externa como interna religam o índice.
    for interno in (False, True):
        pg.evaluate(SUBSTITUIR, interno)
        _esperar_editor(pg)
        _indice(pg).click()
        expect(pg.locator("[data-editores]")).to_have_class(re.compile("editores--sem-indice"))
        _indice(pg).click()
        expect(pg.locator("[data-editores]")).not_to_have_class(re.compile("editores--sem-indice"))
    # Import em cache não antecipa as miniaturas de uma caixa nova longe da tela.
    pg.evaluate("window.scrollTo(0, 0)")
    pg.evaluate(SUBSTITUIR, False)
    pg.wait_for_load_state("networkidle")
    expect(pg.locator("[data-editores] iframe[data-miniatura][src]")).to_have_count(0)
    pg.locator("#minuta").scroll_into_view_if_needed()
    _esperar_editor(pg)
    assert pg.erros_console == []


def test_reposicao_durante_import_nao_inicializa_caixa_removida(logado, dados_e2e):
    pg = logado
    antigos = []

    def repor_antes_de_liberar(rota: Route):
        resposta = None
        try:
            resposta = rota.fetch(timeout=15000)
            # A resposta do import ainda não chegou ao navegador: a raiz é trocada
            # enquanto o mesmo callback mantém a Route ativa, sem unroute/continue.
            antigos.append(pg.evaluate_handle(SUBSTITUIR, False))
        finally:
            if resposta is None:
                rota.abort()
            else:
                try:
                    rota.fulfill(response=resposta)
                finally:
                    resposta.dispose()

    pg.route("**/componentes/editores.js", repor_antes_de_liberar, times=1)
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/editar/",
            wait_until="networkidle")
    with pg.expect_request("**/componentes/editores.js"):
        pg.locator("#minuta").scroll_into_view_if_needed()
    _esperar_editor(pg)
    assert len(antigos) == 1
    antigo = antigos[0]
    assert antigo.evaluate("raiz => !raiz.isConnected")
    assert antigo.evaluate("raiz => raiz.querySelectorAll('iframe[data-miniatura][src]').length") == 0
    antigo.dispose()
    assert pg.erros_console == []


def test_fallback_sem_intersection_observer(logado, dados_e2e):
    pg = logado
    pg.add_init_script("delete window.IntersectionObserver")
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/editar/",
            wait_until="networkidle")
    # Sem o recurso do navegador a carga imediata preserva o editor utilizável.
    _esperar_editor(pg)
    expect(pg.locator("[data-mapa] .leaflet-map-pane")).to_have_count(1, timeout=15000)
    pg.locator("#minuta").scroll_into_view_if_needed()
    _indice(pg).click()
    expect(pg.locator("[data-editores]")).to_have_class(re.compile("editores--sem-indice"))
    assert pg.erros_console == []
