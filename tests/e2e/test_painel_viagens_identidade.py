"""Painel: registros canônicos legíveis e ações acessíveis nas três larguras."""

import pytest
from playwright.sync_api import expect

from .conftest import rodar_axe

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_painel_registros_menu_resumo_e_teclado(logado, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.goto("/viagens/", wait_until="networkidle")
    expect(pg.get_by_role("heading", name="Para concluir", exact=True)).to_be_visible()
    registros = pg.locator('.registros--operacionais > .registro')
    assert registros.count() > 0
    assert registros.first.evaluate("e => getComputedStyle(e).display") == "grid"
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert not rodar_axe(pg)
    botao = registros.first.locator('[data-menu-botao]')
    botao.focus()
    pg.keyboard.press("Enter")
    menu = pg.locator('[role="menu"]:visible')
    expect(menu).to_be_visible()
    expect(menu.locator('[data-menu-carregando]')).to_have_count(0)
    assert not rodar_axe(pg)
    pg.keyboard.press("Escape")
    expect(botao).to_be_focused()
    link = registros.first.locator('.registro__link[data-abrir-dialogo="dialogo-resumo"]')
    link.focus()
    pg.keyboard.press("Enter")
    expect(pg.locator('#resumo-dialogo .registro-hero')).to_be_visible()
    pg.keyboard.press("Escape")
    expect(link).to_be_focused()
    assert not pg.erros_console
