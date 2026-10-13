"""Servidores: cadastro responsivo e navegação em estados da lista."""
import pytest
from playwright.sync_api import expect

from tests.e2e.test_justificativas_identidade import _axe_estavel

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_dialogo_campos_legiveis_e_estados(logado, dados_e2e, largura, tmp_path):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 700})
    pg.goto("/cadastros/servidores/")
    pg.evaluate("""async () => {
        await document.fonts.ready;
        await Promise.all(document.getAnimations().filter(a =>
            a.effect.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})));
    }""")
    busca = pg.get_by_role("searchbox", name="Buscar", exact=True).bounding_box()
    cargo = pg.get_by_role("combobox", name="Cargo", exact=True).bounding_box()
    assert busca and cargo
    if largura == 360:
        assert busca["y"] + busca["height"] <= cargo["y"]
    else:
        # Mesma linha: tolerância de um pixel para arredondamento subpixel.
        assert abs(busca["y"] - cargo["y"]) <= 1
    abrir = pg.get_by_role("button", name="Novo servidor", exact=True).first
    abrir.focus()
    abrir.press("Enter")
    janela = pg.get_by_role("dialog", name="Novo servidor")
    expect(janela).to_be_visible()
    nome = janela.get_by_label("Nome completo")
    nome.fill("Pessoa de teste com nome completo extenso")
    cpf = janela.get_by_label("CPF", exact=True)
    cpf.fill("529.982.247-25")
    assert cpf.evaluate("e=>e.clientWidth") >= 170
    assert nome.evaluate("e=>e.clientWidth") >= 220
    _axe_estavel(pg)
    janela.screenshot(path=str(tmp_path / f"servidores-campos-{largura}.png"))
    pg.keyboard.press("Escape")
    expect(abrir).to_be_focused()
    pg.goto("/cadastros/servidores/?q=zzzinexistente")
    expect(pg.get_by_text("Nenhum servidor encontrado", exact=True)).to_be_visible()
    _axe_estavel(pg)
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")
    pg.goto("/cadastros/servidores/?aba=incompletos")
    expect(pg.get_by_role("heading", name="Cadastros incompletos")).to_be_visible()
    assert pg.erros_console == []
