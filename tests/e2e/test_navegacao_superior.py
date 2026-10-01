"""E2E: a navegação principal é SUPERIOR em todas as larguras (ADR 0006).

Desktop/tablet: barra horizontal logo abaixo do cabeçalho, na largura toda, sem ☰.
Celular (decisão D9): o ☰ abre o menu numa gaveta lateral temporária sob o cabeçalho;
fechada ao carregar e depois de usada. Uma barra lateral permanente reprova aqui.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e

GEOMETRIA = """() => {
  const caixa = (el) => el.getBoundingClientRect();
  const nav = document.getElementById('navegacao-principal');
  const entradas = [nav.querySelector('.navegacao__seletor'),
                    ...nav.querySelectorAll('.navegacao__lista > li')];
  const interno = nav.querySelector('.navegacao__interno');
  return {
    nav: caixa(nav).toJSON(),
    cabecalho: caixa(document.querySelector('.cabecalho')).toJSON(),
    main: caixa(document.querySelector('main')).toJSON(),
    centros: entradas.map((e) => caixa(e).top + caixa(e).height / 2),
    transborda: interno.scrollWidth > interno.clientWidth + 1,
    largura: window.innerWidth,
  };
}"""


def _abrir(pg: Page, largura: int) -> None:
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.goto("/viagens/oficios/")


@pytest.mark.parametrize("largura", [768, 1024, 1280, 1440])
def test_menu_superior_horizontal_no_tablet_e_desktop(logado, largura):
    pg = logado
    _abrir(pg, largura)
    nav = pg.get_by_role("navigation", name="Navegação principal")
    expect(nav).to_be_in_viewport()
    expect(pg.get_by_role("button", name="Abrir menu de navegação")).to_be_hidden()
    g = pg.evaluate(GEOMETRIA)
    # Faixa horizontal colada sob o cabeçalho, na largura toda e com altura de uma linha.
    assert abs(g["nav"]["top"] - g["cabecalho"]["bottom"]) <= 1
    assert g["nav"]["left"] == 0 and g["nav"]["width"] >= g["largura"] - 1
    assert g["nav"]["height"] <= 64
    # Seletor de módulo e itens lado a lado (mesma linha), sem transbordo.
    assert max(g["centros"]) - min(g["centros"]) <= 2, g["centros"]
    assert not g["transborda"]
    # O conteúdo começa abaixo do menu e ocupa a largura (não há coluna lateral à esquerda).
    assert g["main"]["top"] >= g["nav"]["bottom"] - 1
    assert g["main"]["left"] == 0
    # Item ativo com filete dourado (cor da marca) e aria-current.
    ativo = nav.get_by_role("link", name="Ofícios")
    expect(ativo).to_have_attribute("aria-current", "page")
    filete, marca = pg.evaluate("""() => {
      const a = document.querySelector('#navegacao-principal [aria-current="page"]');
      const amostra = document.createElement('i');
      amostra.style.color = 'var(--cor-marca)';
      document.body.append(amostra);
      const cor = getComputedStyle(amostra).color;
      amostra.remove();
      return [getComputedStyle(a, '::after').backgroundColor, cor];
    }""")
    assert filete == marca


@pytest.mark.parametrize("largura", [360, 390])
def test_celular_abre_gaveta_lateral_temporaria(logado, largura):
    pg = logado
    _abrir(pg, largura)
    nav = pg.get_by_role("navigation", name="Navegação principal")
    botao = pg.get_by_role("button", name="Abrir menu de navegação")
    expect(nav).not_to_be_in_viewport()  # fechada ao carregar: nada fica preso na tela
    g = pg.evaluate(GEOMETRIA)
    assert g["main"]["left"] == 0 and g["main"]["width"] >= g["largura"] - 1
    botao.click()
    expect(nav).to_be_in_viewport()
    pg.wait_for_timeout(300)  # fim da transição
    g = pg.evaluate(GEOMETRIA)
    # Gaveta à esquerda, sob o cabeçalho, sem ocupar a tela toda (o véu mostra o conteúdo).
    assert abs(g["nav"]["top"] - g["cabecalho"]["bottom"]) <= 1
    assert g["nav"]["left"] == 0 and g["nav"]["width"] < g["largura"]
    pg.keyboard.press("Escape")
    expect(nav).not_to_be_in_viewport()
    expect(botao).to_be_focused()
    # Tocar fora (no véu) fecha.
    botao.click()
    expect(nav).to_be_in_viewport()
    pg.mouse.click(g["largura"] - 10, 600)
    expect(nav).not_to_be_in_viewport()
    # Escolher um destino fecha a gaveta e a página nova abre com ela fechada.
    botao.click()
    nav.get_by_role("link", name="Painel").click()
    expect(pg).to_have_url(re.compile(r"/viagens/$"))
    expect(nav).not_to_be_in_viewport()
