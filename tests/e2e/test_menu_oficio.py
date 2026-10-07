"""Lote 3 da lista de ofícios no navegador: menu ⋮ canônico (LP-30), "Mais" da barra
(LP-31; a página Numeração foi excluída a pedido — 4a3f835) — teclado, foco devolvido, posição do painel, perfis e axe.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import entrar, rodar_axe

pytestmark = pytest.mark.e2e


def _botao(pg: Page, pk: int):
    from gestao.viagens.models import Oficio

    numero = Oficio.objects.get(pk=pk).numero_formatado
    return pg.get_by_role("button", name=f"Ações do Ofício {numero}", exact=True)


def _abrir(pg: Page, pk: int):
    botao = _botao(pg, pk)
    botao.focus()  # o foco já pede os itens ao servidor
    botao.press("Enter")
    menu = pg.get_by_role("menu", name=re.compile("Ações do Ofício"))
    expect(menu.get_by_role("menuitem", name="Ver resumo")).to_be_focused()
    return botao, menu


def _barra_parada(pg: Page) -> None:
    # Como as ferramentas do QA: a barra flutuante cobre linhas ao rolar (artefato do axe).
    pg.evaluate("document.querySelectorAll('.barra-acoes').forEach(b => b.style.position = 'static')")


def _parado(pg: Page) -> None:
    """Espera as animações finitas (entrada da página, da folha, do painel) acabarem."""
    pg.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running'"
                         " || a.effect.getTiming().iterations === Infinity)")


def _axe(pg: Page) -> list[dict]:
    _parado(pg)
    return rodar_axe(pg)


def test_teclado_setas_home_end_esc_e_foco_devolvido(logado, dados_e2e):
    pg = logado
    pg.goto("/viagens/oficios/?documento=rascunho")
    botao, menu = _abrir(pg, dados_e2e.ids["oficio_rascunho"])
    pg.keyboard.press("ArrowDown")
    expect(menu.get_by_role("menuitem", name="Abrir o ofício")).to_be_focused()
    pg.keyboard.press("End")
    expect(menu.get_by_role("menuitem", name="Excluir rascunho")).to_be_focused()
    pg.keyboard.press("ArrowDown")  # dá a volta
    expect(menu.get_by_role("menuitem", name="Ver resumo")).to_be_focused()
    pg.keyboard.press("ArrowUp")
    expect(menu.get_by_role("menuitem", name="Excluir rascunho")).to_be_focused()
    pg.keyboard.press("Home")
    expect(menu.get_by_role("menuitem", name="Ver resumo")).to_be_focused()
    # O inativo recebe o foco e diz por quê (descrição), mas não age.
    anexar = menu.get_by_role("menuitem", name="Anexar assinado…")
    expect(anexar).to_have_attribute("aria-disabled", "true")
    expect(anexar).to_have_accessible_description(re.compile("Emita o ofício primeiro"))
    for _ in range(4):
        pg.keyboard.press("ArrowDown")
    expect(anexar).to_be_focused()
    pg.keyboard.press("Enter")
    expect(menu).to_be_visible()
    # Nome do item sem a descrição; descrição como descrição.
    expect(menu.get_by_role("menuitem", name="Marcar como complementar", exact=True)).to_have_count(1)
    pg.keyboard.press("Escape")
    expect(menu).to_be_hidden()
    expect(botao).to_be_focused()


def test_painel_dentro_da_janela_em_toda_largura(logado, dados_e2e):
    pg = logado
    for largura, altura in ((1440, 900), (1024, 768), (768, 900), (390, 844), (360, 640)):
        pg.set_viewport_size({"width": largura, "height": altura})
        pg.goto("/viagens/oficios/")
        botoes = pg.locator(".registro__acoes [data-menu-botao]")
        ultimo = botoes.nth(botoes.count() - 1)
        ultimo.scroll_into_view_if_needed()
        ultimo.click()
        painel = pg.locator(".menu__painel:popover-open")
        expect(painel.get_by_role("menuitem", name="Ver resumo")).to_be_visible()  # chegaram
        _parado(pg)
        caixa = painel.bounding_box()
        assert caixa is not None
        assert caixa["x"] >= 0 and caixa["x"] + caixa["width"] <= largura, largura
        assert caixa["y"] >= 0 and caixa["y"] + caixa["height"] <= altura + 1, largura
        folha = "menu__painel--folha" in (painel.get_attribute("class") or "")
        assert folha == (largura < 768)
        pg.keyboard.press("Escape")
        expect(painel).to_have_count(0)


def test_toque_fora_so_fecha(logado, dados_e2e):
    pg = logado
    pg.set_viewport_size({"width": 390, "height": 844})
    pg.goto("/viagens/oficios/?documento=rascunho")
    botao, menu = _abrir(pg, dados_e2e.ids["oficio_rascunho"])
    pg.mouse.click(195, 120)  # véu, sobre a lista
    expect(menu).to_be_hidden()
    assert pg.url.endswith("/viagens/oficios/?documento=rascunho")  # nada por trás acionou
    expect(botao).to_be_focused()


def test_baixar_documentos_pelo_menu_e_foco_volta_ao_botao(logado, dados_e2e):
    pg = logado
    pg.goto("/viagens/oficios/?documento=rascunho")
    botao, menu = _abrir(pg, dados_e2e.ids["oficio_rascunho"])
    menu.get_by_role("menuitem", name="Baixar documentos…").click()
    janela = pg.get_by_role("dialog", name="Baixar documentos")
    expect(janela).to_be_visible()
    expect(menu).to_be_hidden()
    pg.keyboard.press("Escape")
    expect(janela).to_be_hidden()
    expect(botao).to_be_focused()


def test_ver_resumo_pelo_menu(logado, dados_e2e):
    pg = logado
    pg.goto("/viagens/oficios/?documento=rascunho")
    botao, menu = _abrir(pg, dados_e2e.ids["oficio_rascunho"])
    menu.get_by_role("menuitem", name="Ver resumo").press("Enter")
    janela = pg.get_by_role("dialog", name="Resumo do ofício")
    expect(janela.locator(".resumo")).to_contain_text("Roteiro")
    pg.keyboard.press("Escape")
    expect(botao).to_be_focused()


def test_marcar_complementar_pelo_menu(logado, dados_e2e):
    from gestao.viagens.models import Oficio

    pg = logado
    pg.goto("/viagens/oficios/?documento=rascunho")
    _, menu = _abrir(pg, dados_e2e.ids["oficio_rascunho"])
    menu.get_by_role("menuitem", name="Marcar como complementar").click()
    expect(pg.get_by_text(re.compile(r"marcado como complementar"))).to_be_visible()
    assert "documento=rascunho" in pg.url  # a lista volta como estava
    assert Oficio.objects.get(pk=dados_e2e.ids["oficio_rascunho"]).marcador == "complementar"
    _, menu = _abrir(pg, dados_e2e.ids["oficio_rascunho"])
    expect(menu.get_by_role("menuitem", name="Deixar de ser complementar")).to_be_visible()
    expect(menu.get_by_role("menuitem", name="Marcar como retificado")).to_have_accessible_description(
        re.compile("tira a de complementar"))


def test_quem_so_consulta_ve_so_leitura(pagina, dados_e2e):
    entrar(pagina, "consulta")
    pagina.goto("/viagens/oficios/?documento=rascunho")
    _, menu = _abrir(pagina, dados_e2e.ids["oficio_rascunho"])
    expect(menu.get_by_role("menuitem")).to_have_count(2)
    expect(menu.get_by_role("menuitem", name="Ver resumo")).to_be_visible()
    expect(menu.get_by_role("menuitem", name=re.compile("^Ver minuta"))).to_be_visible()
    expect(pagina.locator(".barra-acoes__mais")).to_have_count(0)


@pytest.mark.parametrize("largura", [1440, 390])
def test_menu_aberto_sem_violacoes(logado, dados_e2e, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 844 if largura < 768 else 900})
    pg.goto("/viagens/oficios/?documento=rascunho")
    _barra_parada(pg)
    _abrir(pg, dados_e2e.ids["oficio_rascunho"])
    assert _axe(pg) == []


def test_lista_sem_mais_vazio(logado, dados_e2e):
    pg = logado
    pg.goto("/viagens/oficios/")
    expect(pg.locator(".barra-acoes__mais")).to_have_count(0)  # nunca um "Mais" vazio
