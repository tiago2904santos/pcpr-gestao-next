"""Viaturas: campos legíveis e controles de criação acessíveis."""
import pytest
from playwright.sync_api import expect

from tests.e2e.test_justificativas_identidade import _axe_estavel

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_campos_tipo_combustivel_e_retorno_de_foco(logado, dados_e2e, largura, tmp_path):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 700})
    pg.goto("/cadastros/viaturas/")
    pg.evaluate("""async () => {
        await document.fonts.ready;
        await Promise.all(document.getAnimations().filter(a =>
            a.effect.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})));
    }""")
    if largura == 360:
        registro = pg.locator(".registro").first
        corpo = registro.locator(".registro__corpo").bounding_box()
        acoes = registro.locator(".registro__acoes").bounding_box()
        assert corpo and acoes and abs(corpo["y"] - acoes["y"]) <= 1
    abrir = pg.get_by_role("button", name="Nova viatura", exact=True).first
    abrir.focus()
    abrir.press("Enter")
    dialog = pg.get_by_role("dialog", name="Nova viatura")
    expect(dialog).to_be_visible()
    tipo = dialog.get_by_role("combobox", name="Tipo", exact=True)
    combustivel = dialog.get_by_role("combobox", name="Combustível", exact=True)
    assert tipo.evaluate("e=>e.clientWidth") >= 220
    assert combustivel.evaluate("e=>e.clientWidth") >= 200
    _axe_estavel(pg)
    dialog.screenshot(path=str(tmp_path / f"viaturas-campos-{largura}.png"))
    pg.keyboard.press("Escape")
    expect(abrir).to_be_focused()
    pg.goto("/cadastros/viaturas/?q=zzzinexistente")
    expect(pg.get_by_text("Nenhuma viatura encontrada", exact=True)).to_be_visible()
    _axe_estavel(pg)
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")
    assert pg.erros_console == []
