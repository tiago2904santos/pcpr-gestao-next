"""Consulta após troca HTMX, geometria e teclado da coleção migrada."""

from decimal import Decimal
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.viagens.models import Roteiro
from tests.e2e.conftest import rodar_axe

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 390, 768, 1440])
def test_busca_atualiza_acoes_e_menu_mantem_teclado(logado, dados_e2e, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 700})
    pg.goto("/viagens/roteiros/")
    ident = dados_e2e.ids["roteiro"]
    Roteiro.objects.filter(pk=ident).update(
        diarias_total=Decimal("999999.99"),
        diarias_resumo="18 × 100% + 1 × 15% + 1 × 30%",
    )
    pg.reload()
    busca = pg.get_by_role("searchbox", name="Buscar")
    busca.fill(f"#{ident}")
    expect(pg.locator(".barra-acoes__status")).to_have_text("1 roteiro")
    expect(busca).to_be_focused()
    registro = pg.locator(".registro-operacional")
    expect(registro).to_have_count(1)
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    valor = registro.locator(".registro__valor")
    expect(valor).to_have_text("R$ 999.999,99")
    assert valor.evaluate("e => e.scrollWidth <= e.clientWidth")
    assert registro.locator(".registro-operacional__conferencia").evaluate(
        """e => [...e.querySelectorAll('*')].every(item =>
        item.getBoundingClientRect().right <= e.getBoundingClientRect().right + 1)"""
    )
    menu = registro.get_by_role("button", name=f"Ações do roteiro #{ident}")
    menu.focus()
    menu.press("Enter")
    expect(registro.get_by_role("menuitem", name="Editar roteiro")).to_be_focused()
    pg.keyboard.press("Escape")
    expect(menu).to_be_focused()
    assert rodar_axe(pg) == []
    pasta = Path("artifacts/roteiros-identidade")
    pasta.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(pasta / f"um-registro-{largura}.png"), full_page=True)
    busca.fill("nenhum-roteiro-identidade")
    expect(pg.get_by_role("heading", name="Nenhum roteiro encontrado")).to_be_visible()
    expect(pg.locator(".barra-acoes__status")).to_have_text("0 roteiros")
    expect(pg.get_by_role("link", name="Novo roteiro")).to_be_visible()
    assert pg.locator(".barra-acoes").evaluate("e => getComputedStyle(e).position") == "static"
    assert rodar_axe(pg) == []
    assert pg.erros_console == []
