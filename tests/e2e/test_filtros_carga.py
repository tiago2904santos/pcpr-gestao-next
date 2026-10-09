"""A gaveta fechada não pede seletores; primeira abertura mantém filtros e foco."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Page, Route, expect

from tests.e2e.conftest import rodar_axe

pytestmark = pytest.mark.e2e

MODULOS = ("seletor.js", "seletor-data.js", "seletor-base.js", "painel-flutuante.js")


def _pedidos_de(pedidos: list[str], arquivo: str) -> list[str]:
    return [url for url in pedidos if urlsplit(url).path.endswith("/" + arquivo)]


def _observar(pg: Page) -> list[str]:
    pedidos = []
    pg.on("request", lambda r: pedidos.append(r.url))
    return pedidos


def _frio(pg: Page, pedidos: list[str]):
    expect(pg.locator("#filtros-mais")).not_to_have_attribute("open", "")
    expect(pg.locator("#filtros-avancados")).not_to_be_visible()
    # CSS aprovado também atende o eProtocolo do Resumo; só os módulos são adiados.
    assert _pedidos_de(pedidos, "formulario.css")
    assert not _pedidos_de(pedidos, "seletores.css")
    for arquivo in MODULOS:
        assert not _pedidos_de(pedidos, arquivo), arquivo


def _abrir(pg: Page):
    pg.locator("#filtros-mais > summary").click()
    expect(pg.locator("#ordem-oficios-gatilho")).to_be_visible()
    expect(pg.get_by_role("button", name="Escolher data: Período de saída", exact=True)).to_be_visible()


@pytest.mark.parametrize("largura", [360, 1440])
def test_gaveta_frio_menu_ordem_periodo_teclado(logado, dados_e2e, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    pedidos = _observar(pg)
    pg.goto("/viagens/oficios/", wait_until="networkidle")
    pg.click(".perfil")
    pg.keyboard.press("Escape")
    pg.wait_for_load_state("networkidle")
    _frio(pg, pedidos)
    _abrir(pg)

    # Escolher ordem realmente filtra e atualiza a URL pelo fluxo HTMX existente.
    opcao = pg.locator("#ordem-oficios option").last
    valor, texto = opcao.get_attribute("value"), opcao.inner_text()
    assert valor
    pg.locator("#ordem-oficios-gatilho").click()
    pg.get_by_role("option", name=texto, exact=True).click()
    expect(pg.locator("#ordem-oficios")).to_have_value(valor)
    pg.wait_for_url(lambda url: parse_qs(urlsplit(url).query).get("ordem") == [valor])

    botao = pg.get_by_role("button", name="Escolher data: Período de saída", exact=True)
    botao.click()
    calendario = pg.get_by_role("dialog", name="Escolher data: Período de saída", exact=True)
    expect(calendario).to_be_visible()
    pg.keyboard.press("Escape")
    expect(calendario).not_to_be_visible()
    expect(botao).to_be_focused()
    expect(pg.locator("#filtros-mais")).to_have_attribute("open", "")
    botao.click()
    expect(calendario).to_be_visible()
    pasta = Path("artifacts/filtros-carga")
    pasta.mkdir(parents=True, exist_ok=True)
    calendario.evaluate("""async el => {
        await Promise.all(el.getAnimations({subtree: true})
            .filter(a => a.effect.getComputedTiming().iterations !== Infinity)
            .map(a => a.finished.catch(() => {})));
    }""")
    pg.screenshot(path=str(pasta / f"filtros-{largura}.png"))
    violacoes = rodar_axe(pg)
    (pasta / f"axe-filtros-{largura}.json").write_text(
        json.dumps(violacoes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    assert violacoes == []

    # Não depende de mês fixo: duas escolhas na grade estabelecem um período real.
    pg.keyboard.press("Enter")
    expect(calendario).to_be_visible()
    expect(calendario.locator("td[tabindex='0']")).to_be_focused()
    pg.keyboard.press("ArrowRight")
    pg.keyboard.press("Enter")
    expect(calendario).not_to_be_visible()
    de = pg.locator("[name='saida_de']").input_value()
    ate = pg.locator("[name='saida_ate']").input_value()
    assert de and ate and de != ate
    expect(pg.locator("#filtro-periodo")).to_have_value(f"{de} a {ate}")
    pg.wait_for_url(lambda url: all(parse_qs(urlsplit(url).query).get(k) == [v]
                                  for k, v in (("saida_de", de), ("saida_ate", ate))))
    pg.keyboard.press("Escape")
    expect(pg.locator("#filtros-avancados")).not_to_be_visible()
    expect(pg.locator("#filtros-mais > summary")).to_be_focused()
    _abrir(pg)
    pg.wait_for_load_state("networkidle")
    for arquivo in MODULOS:
        assert len(_pedidos_de(pedidos, arquivo)) == 1, arquivo
    assert pg.erros_console == []


def test_resumo_frio_nao_antecipa_gaveta(logado, dados_e2e):
    pg = logado
    pedidos = _observar(pg)
    pk = dados_e2e.ids["oficio_emitido"]
    pg.goto(f"/viagens/oficios/?resumo={pk}", wait_until="networkidle")
    expect(pg.locator("#dialogo-resumo")).to_be_visible()
    _frio(pg, pedidos)
    pg.get_by_role("button", name="Fechar o resumo", exact=True).click()
    expect(pg.locator("#dialogo-resumo")).not_to_be_visible()
    _abrir(pg)
    assert pg.erros_console == []


SUBSTITUIR = """(html) => {
    const antigo = document.querySelector('#filtros-mais');
    antigo.outerHTML = html;
    const novo = document.querySelector('#filtros-mais');
    document.body.dispatchEvent(new CustomEvent('htmx:afterSwap', {detail: {target: novo}}));
}"""


def test_reposicao_htmx_fechada_e_com_modulos_em_cache(logado, dados_e2e):
    pg = logado
    pedidos = _observar(pg)
    pg.goto("/viagens/oficios/", wait_until="networkidle")
    # Guarda HTML ainda nativo: repor markup inicializado por clone perderia seus handlers.
    original = pg.locator("#filtros-mais").evaluate("e => e.outerHTML")
    pg.evaluate(SUBSTITUIR, original)
    pg.wait_for_load_state("networkidle")
    _frio(pg, pedidos)
    _abrir(pg)
    pg.keyboard.press("Escape")
    expect(pg.locator("#filtros-avancados")).not_to_be_visible()
    pg.evaluate(SUBSTITUIR, original)
    _abrir(pg)
    gatilho = pg.locator("#ordem-oficios-gatilho")
    gatilho.click()
    expect(pg.locator("#ordem-oficios-gatilho-lista")).to_be_visible()
    pg.keyboard.press("Escape")
    expect(gatilho).to_be_focused()
    expect(pg.locator("#ordem-oficios-gatilho-lista")).not_to_be_visible()
    pg.wait_for_load_state("networkidle")
    for arquivo in MODULOS:
        assert len(_pedidos_de(pedidos, arquivo)) == 1, arquivo
    assert pg.erros_console == []


@pytest.mark.parametrize("largura", [360, 1440])
def test_import_em_curso_preserva_foco_do_select_nativo(logado, dados_e2e, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})

    def entregar_depois_do_foco(rota: Route):
        # O handler conclui o próprio Route. Não retém rota nem espera evento externo.
        resposta = None
        try:
            resposta = rota.fetch(timeout=15000)
            nativo = pg.locator("#ordem-oficios")
            expect(nativo).to_be_visible()
            nativo.focus()
        finally:
            if resposta is None:
                rota.abort()
            else:
                try:
                    rota.fulfill(response=resposta)
                finally:
                    resposta.dispose()

    pg.route("**/componentes/seletor.js", entregar_depois_do_foco, times=1)
    pg.goto("/viagens/oficios/", wait_until="networkidle")
    pg.locator("#filtros-mais > summary").click()
    expect(pg.locator("#ordem-oficios-gatilho")).to_be_visible()
    expect(pg.locator("#ordem-oficios-gatilho")).to_be_focused()
    pg.keyboard.press("ArrowDown")
    expect(pg.locator("#ordem-oficios-gatilho-lista")).to_be_visible()
    pg.keyboard.press("Escape")
    expect(pg.locator("#ordem-oficios-gatilho")).to_be_focused()
    assert pg.erros_console == []
