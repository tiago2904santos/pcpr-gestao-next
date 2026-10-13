"""Catálogo de textos: fluxo real de criação, edição e estados responsivos."""
from pathlib import Path

import pytest
from django.contrib.auth.models import Permission
from playwright.sync_api import expect

from gestao.cadastros.models import ModeloTexto

from .conftest import entrar
from .test_justificativas_identidade import _axe_estavel

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_textos_fluxo_e_estados(pagina, largura):
    pg = pagina
    entrar(pg, "gestor")
    pg.set_viewport_size({"width": largura, "height": 800})
    pg.goto("/cadastros/textos-prontos/")
    out = Path("artifacts/textos")
    out.mkdir(parents=True, exist_ok=True)
    abrir = pg.get_by_role("button", name="Novo texto pronto", exact=True).first
    abrir.focus()
    abrir.press("Enter")
    janela = pg.get_by_role("dialog")
    janela.get_by_label("Nome", exact=False).fill("Texto visual de teste")
    janela.locator("textarea").fill("Conteúdo preservado durante a edição. " * 12)
    pg.keyboard.press("Escape")
    expect(abrir).to_be_focused()
    abrir.press("Enter")
    expect(janela.locator("textarea")).to_have_value("Conteúdo preservado durante a edição. " * 12)
    _axe_estavel(pg)
    janela.get_by_role("button", name="Criar texto pronto").click()
    expect(pg.get_by_role("link", name="Texto visual de teste", exact=True)).to_be_visible()
    registro = pg.locator("li.registro").filter(has=pg.get_by_role("link", name="Texto visual de teste", exact=True))
    if largura == 360:
        corpo = registro.locator(".registro__corpo").bounding_box()
        acoes = registro.locator(".registro__acoes").bounding_box()
        assert abs(corpo["y"] - acoes["y"]) < 8
    registro.get_by_role("button", name="Ações de").click()
    pg.get_by_role("menuitem", name="Editar", exact=True).click()
    janela = pg.get_by_role("dialog")
    janela.locator("textarea").fill("Texto revisado e preservado.")
    janela.get_by_role("button", name="Salvar alterações").click()
    expect(pg.get_by_text("Texto revisado e preservado.", exact=True)).to_be_visible()
    assert ModeloTexto.objects.get(nome="Texto visual de teste").texto == "Texto revisado e preservado."
    _axe_estavel(pg)
    pg.screenshot(path=str(out / f"lista-{largura}.png"), full_page=True)
    pg.get_by_role("searchbox", name="Buscar").fill("zzsemresultadozz")
    pg.get_by_role("button", name="Buscar", exact=True).click()
    expect(pg.get_by_text("Nenhum texto encontrado", exact=True)).to_be_visible()
    _axe_estavel(pg)
    pg.screenshot(path=str(out / f"sem-resultados-{largura}.png"), full_page=True)
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert pg.erros_console == []


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_textos_vazio_erro_e_leitura(pagina, dados_e2e, largura):
    # Somente banco descartável da fixture; nunca o DEMO.
    ModeloTexto.objects.all().delete()
    pg = pagina
    entrar(pg, "gestor")
    pg.set_viewport_size({"width": largura, "height": 800})
    pg.goto("/cadastros/textos-prontos/")
    expect(pg.get_by_text("Nenhum texto pronto deste tipo", exact=True)).to_be_visible()
    _axe_estavel(pg)
    out = Path("artifacts/textos")
    out.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(out / f"vazio-{largura}.png"), full_page=True)
    pg.get_by_role("button", name="Novo texto pronto", exact=True).first.click()
    janela = pg.get_by_role("dialog")
    janela.locator("textarea").fill("Conteúdo mantido após validação.")
    janela.get_by_role("button", name="Criar texto pronto").click()
    expect(janela).to_be_visible()
    expect(janela.locator("textarea")).to_have_value("Conteúdo mantido após validação.")
    _axe_estavel(pg)
    janela.screenshot(path=str(out / f"erro-{largura}.png"))
    janela.get_by_label("Nome", exact=False).fill("Leitura visual")
    janela.get_by_role("button", name="Criar texto pronto").click()
    usuario = dados_e2e.usuarios["consulta"]
    usuario.user_permissions.add(Permission.objects.get(codename="view_modelotexto"))
    pg.context.clear_cookies()
    entrar(pg, "consulta")
    pg.goto("/cadastros/textos-prontos/")
    expect(pg.get_by_text("Leitura visual", exact=True)).to_be_visible()
    expect(pg.get_by_role("button", name="Novo texto pronto", exact=True)).to_have_count(0)
    expect(pg.locator(".barra-acoes--rodape")).to_have_count(0)
    _axe_estavel(pg)
    pg.screenshot(path=str(out / f"leitura-{largura}.png"), full_page=True)
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
