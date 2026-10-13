"""OS migrada: relações, filtros, calendário, ações e leitura sem edição."""

from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.viagens import ordens
from gestao.viagens.models import Oficio
from tests.e2e.conftest import entrar, rodar_axe

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_preparacao_e_lista_operacional(logado, dados_e2e, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 700})
    ordem, _ = ordens.salvar(
        dados_e2e.usuarios["operador"],
        oficios=[Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])],
    )
    pg.goto(f"/viagens/ordens/{ordem.pk}/")
    expect(pg.locator(".registro-hero")).to_contain_text(ordem.numero_formatado)
    expect(pg.locator("[data-destino] .itin__ordem").first).to_have_text("1")
    assert pg.locator(".barra-acoes").evaluate("e => getComputedStyle(e).position") == "static"
    assert pg.locator(".campo-equipe--compacta .equipe__cartoes").evaluate(
        """e => [...e.children].every(c => c.getBoundingClientRect().height < 80 &&
        c.getBoundingClientRect().width >= e.getBoundingClientRect().width * 0.4)"""
    )
    calendario = pg.locator("pc-data[data-periodo] button.seletor__botao")
    calendario.focus()
    calendario.press("Enter")
    expect(calendario).to_have_attribute("aria-expanded", "true")
    pg.keyboard.press("Escape")
    expect(calendario).to_be_focused()
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert rodar_axe(pg) == []
    pg.goto("/viagens/ordens/")
    busca = pg.get_by_role("searchbox", name="Buscar")
    busca.fill("ordem-sem-resultado-identidade")
    expect(pg.locator(".barra-acoes__status")).to_contain_text("0 ordens de serviço")
    expect(busca).to_be_focused()
    expect(pg.get_by_role("button", name="Nova ordem de serviço", exact=True)).to_be_visible()
    assert rodar_axe(pg) == []
    busca.fill(ordem.numero_formatado)
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    menu = pg.get_by_role("button", name=f"Ações da {ordem}")
    menu.focus()
    menu.press("Enter")
    expect(pg.get_by_role("menuitem", name="Documento (PDF)", exact=True)).to_be_focused()
    pg.keyboard.press("Escape")
    expect(menu).to_be_focused()
    pasta = Path("artifacts/ordens-identidade")
    pasta.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(pasta / f"lista-{largura}.png"), full_page=True)
    assert pg.erros_console == []


def test_documento_cancelamento_e_consulta(logado, dados_e2e, tmp_path):
    pg = logado
    ordem, _ = ordens.salvar(
        dados_e2e.usuarios["operador"],
        oficios=[Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])],
    )
    pg.goto(f"/viagens/ordens/{ordem.pk}/")
    pg.locator(".registro-hero__acoes [data-menu-botao]").click()
    with pg.expect_download() as descarga:
        pg.get_by_role("menuitem", name="Baixar o PDF", exact=True).click()
    destino = tmp_path / "ordem.pdf"
    descarga.value.save_as(destino)
    assert destino.read_bytes().startswith(b"%PDF")
    ordem.refresh_from_db()
    assert ordem.documento_gerado_em is not None
    pg.goto("/viagens/ordens/")
    pg.get_by_role("button", name=f"Ações da {ordem}").click()
    pg.get_by_role("menuitem", name="Cancelar", exact=True).press("Enter")
    dialogo = pg.get_by_role("dialog", name=f"Cancelar a {ordem}?")
    dialogo.get_by_label("Motivo do cancelamento").fill("Operação adiada para conferência")
    dialogo.get_by_role("button", name="Cancelar OS", exact=True).click()
    expect(pg.locator(".toast").first).to_contain_text("cancelada")
    pg.goto("/viagens/ordens/?aba=canceladas")
    expect(pg.locator('#abas-filtro [aria-current="page"]')).to_contain_text("Canceladas")
    expect(pg.locator('.registro-operacional')).to_have_count(1)
    pg.get_by_role("button", name=f"Ações da {ordem}").click()
    pg.get_by_role("menuitem", name="Reativar", exact=True).press("Enter")
    expect(pg.locator(".toast").first).to_contain_text("reativada")
    pg.context.clear_cookies()
    entrar(pg, "consulta")
    pg.goto(f"/viagens/ordens/{ordem.pk}/")
    expect(pg.locator("#form-ordem fieldset").first).to_have_attribute("disabled", "")
    expect(pg.locator("#id_motivo")).to_be_disabled()
    expect(pg.locator("pc-editor-documento")).to_have_count(0)
    expect(pg.get_by_role("button", name="Finalizar", exact=True)).to_have_count(0)
    assert rodar_axe(pg) == []
    assert pg.erros_console == []
