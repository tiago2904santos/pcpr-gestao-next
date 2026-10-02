"""Fase 5: estados interativos dos componentes do UI Lab, exercitados de verdade.

Hover, foco por teclado e ativo são capturados (artifacts/ui-lab/) e o foco
visível é verificado por estilo computado (WCAG 2.4.7).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from .conftest import ARTEFATOS

pytestmark = pytest.mark.visual

COMPONENTES = {
    "botao-primario": "[data-lab='botao-primario']",
    "botao-marca": "[data-lab='botao-marca']",
    "botao-secundario": "[data-lab='botao-secundario']",
    "entrada": "#id_nome",
    "selecao": "#id_destino-gatilho",
    "aba": ".abas .aba:not([aria-current])",
    "registro": ".registro .registro__link",
}


@pytest.mark.parametrize("nome", list(COMPONENTES))
def test_estados_hover_foco_ativo(logado, nome):
    pg = logado
    pg.goto("/ui-lab/")
    alvo = pg.locator(COMPONENTES[nome]).first
    alvo.scroll_into_view_if_needed()
    destino = ARTEFATOS / "ui-lab"
    destino.mkdir(parents=True, exist_ok=True)
    caixa = alvo.bounding_box()
    recorte = {"x": max(caixa["x"] - 24, 0), "y": max(caixa["y"] - 24, 0),
               "width": caixa["width"] + 48, "height": caixa["height"] + 48}
    pg.screenshot(path=str(destino / f"{nome}-padrao.png"), clip=recorte)
    alvo.hover()
    pg.screenshot(path=str(destino / f"{nome}-hover.png"), clip=recorte)
    pg.mouse.move(0, 0)
    alvo.focus()
    pg.keyboard.press("Shift+Tab")
    pg.keyboard.press("Tab")
    pg.screenshot(path=str(destino / f"{nome}-foco.png"), clip=recorte)
    estilo = alvo.evaluate("""e => { const s = getComputedStyle(e);
        return {outline: s.outlineStyle, sombra: s.boxShadow, borda: s.borderColor}; }""")
    focado_visivel = estilo["outline"] != "none" or estilo["sombra"] != "none"
    focado_no_pai = alvo.evaluate(
        "e => !!e.closest('.registro') && getComputedStyle(e.closest('.registro')).boxShadow !== 'none'")
    assert focado_visivel or focado_no_pai, f"{nome}: foco sem indicação visual {estilo}"


def test_toast_dialogo_e_gaveta(logado):
    pg = logado
    pg.goto("/ui-lab/")
    pg.get_by_role("button", name="Toast de erro (persistente)").click()
    expect(pg.locator(".toast--perigo")).to_be_visible()
    pg.locator(".toast--perigo .toast__fechar").click()
    expect(pg.locator(".toast--perigo")).to_have_count(0)
    pg.get_by_role("button", name="Abrir gaveta").click()
    gaveta = pg.get_by_role("dialog", name="Filtros avançados")
    expect(gaveta).to_be_visible()
    pg.keyboard.press("Escape")
    expect(gaveta).to_be_hidden()
    pg.get_by_role("button", name="Confirmação destrutiva").click()
    confirmacao = pg.get_by_role("dialog", name="Cancelar ofício?")
    expect(confirmacao).to_be_visible()
    confirmacao.get_by_role("button", name="Cancelar", exact=True).click()
    expect(confirmacao).to_be_hidden()


def test_combobox_local_por_teclado(logado):
    pg = logado
    pg.goto("/ui-lab/")
    campo = pg.get_by_role("combobox", name="Município (lista local)")
    campo.fill("londr")
    pg.keyboard.press("ArrowDown")
    pg.keyboard.press("Enter")
    expect(campo).to_have_value("Londrina")
    assert pg.locator("#lab-municipio").input_value() == "Londrina"
