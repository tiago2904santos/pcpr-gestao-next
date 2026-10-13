"""Entrada de cadastros: navegação, permissões e grupos responsivos."""

import re

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import entrar
from tests.e2e.test_justificativas_identidade import _axe_estavel

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
@pytest.mark.parametrize("perfil", ["operador", "consulta"])
def test_indice_preserva_links_e_permissoes(pagina, dados_e2e, largura, perfil, tmp_path):
    pg = pagina
    pg.set_viewport_size({"width": largura, "height": 700})
    entrar(pg, perfil)
    pg.goto("/cadastros/")
    expect(pg.get_by_role("heading", level=1)).to_have_text("Cadastros")
    main = pg.locator("main")
    expect(main.get_by_role("link", name="Servidores", exact=True)).to_be_visible()
    expect(main.get_by_role("link", name="Cargos", exact=True)).to_be_visible()
    expect(main.get_by_role("link", name="Tabela de diárias", exact=True)).to_have_count(
        0 if perfil == "consulta" else 1
    )
    expect(main.get_by_role("link", name="Configuração da unidade", exact=True)).to_have_count(
        0 if perfil == "consulta" else 1
    )
    _axe_estavel(pg)
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    pg.screenshot(path=str(tmp_path / f"cadastros-indice-{perfil}-{largura}.png"), full_page=True)
    link = main.get_by_role("link", name="Servidores", exact=True)
    link.focus()
    expect(link).to_be_focused()
    link.press("Enter")
    expect(pg).to_have_url(re.compile(r"/cadastros/servidores/$"))
    expect(pg.get_by_role("heading", level=1)).to_have_text("Servidores")
    assert pg.erros_console == []
