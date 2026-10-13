"""Vigências: leitura, dimensões móveis, prévia e teclado sem mudar regras."""
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.cadastros.models import TabelaDiaria

from .conftest import entrar
from .test_justificativas_identidade import _axe_estavel

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_vigencia_campos_previa_e_foco(pagina, largura):
    pg = pagina
    entrar(pg, "gestor")
    pg.set_viewport_size({"width": largura, "height": 700})
    pg.goto("/cadastros/diarias/")
    expect(pg.get_by_role("heading", name="Tabela de diárias", exact=True)).to_be_visible()
    _axe_estavel(pg)
    abrir = pg.get_by_role("button", name="Nova vigência", exact=True).first
    abrir.focus()
    abrir.press("Enter")
    janela = pg.get_by_role("dialog", name="Nova vigência")
    expect(janela).to_be_visible()
    data = janela.get_by_role("textbox", name="Vigente a partir de")
    assert data.evaluate("e=>e.clientWidth") >= 200
    janela.get_by_role("combobox", name="Faixa").click()
    janela.get_by_role("option", name="Capital", exact=True).click()
    data.fill("01/01/2030")
    janela.get_by_label("Diária de 24 horas").fill("290.55")
    expect(janela.locator("[data-diaria-percentual='15']")).to_have_text(re.compile("43,58"))
    expect(janela.locator("[data-diaria-percentual='30']")).to_have_text(re.compile("87,17"))
    _axe_estavel(pg)
    pg.keyboard.press("Escape")
    expect(abrir).to_be_focused()
    abrir.press("Enter")
    expect(data).to_have_value("01/01/2030")
    pg.keyboard.press("Escape")
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert pg.erros_console == []


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_vazio_erro_e_consulta_sem_edicao(pagina, largura):
    # Apenas o banco descartável da fixture transactional_db; nunca o DEMO.
    TabelaDiaria.objects.all().delete()
    pg = pagina
    entrar(pg, "gestor")
    pg.set_viewport_size({"width": largura, "height": 700})
    pg.goto("/cadastros/diarias/")
    expect(pg.get_by_text("Nenhuma vigência cadastrada", exact=True)).to_be_visible()
    _axe_estavel(pg)
    out = Path("artifacts/tabela-diarias")
    out.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(out / f"vazio-{largura}.png"), full_page=True)
    pg.get_by_role("button", name="Nova vigência", exact=True).first.click()
    janela = pg.get_by_role("dialog", name="Nova vigência")
    janela.get_by_role("textbox", name="Vigente a partir de").fill("01/01/2030")
    janela.get_by_label("Diária de 24 horas").fill("0.03")
    janela.get_by_label("Norma de referência").fill("Norma sintética preservada ao corrigir valor")
    janela.get_by_role("button", name="Cadastrar vigência").click()
    expect(janela).to_be_visible()
    expect(janela.get_by_text(re.compile("15% ficaria zerado"))).to_be_visible()
    expect(janela.get_by_label("Norma de referência")).to_have_value("Norma sintética preservada ao corrigir valor")
    _axe_estavel(pg)
    janela.screenshot(path=str(out / f"erro-{largura}.png"))
    janela.get_by_label("Diária de 24 horas").fill("290.55")
    janela.get_by_role("button", name="Cadastrar vigência").click()
    expect(pg.locator(".toast")).to_contain_text("cadastrada")
    pg.context.clear_cookies()
    entrar(pg, "operador")
    pg.goto("/cadastros/diarias/")
    expect(pg.locator("tbody tr")).to_have_count(1)
    expect(pg.get_by_role("button", name="Nova vigência", exact=True)).to_have_count(0)
    expect(pg.locator("tbody [data-menu-botao]")).to_have_count(0)
    _axe_estavel(pg)
    pg.screenshot(path=str(out / f"consulta-{largura}.png"), full_page=True)
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
