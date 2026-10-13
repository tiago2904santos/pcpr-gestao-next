"""Configuração: salvar, erro, substituição e consulta em todas as larguras."""
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.cadastros.models import Lotacao, Servidor, Unidade

from .conftest import entrar
from .test_justificativas_identidade import _axe_estavel

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_configuracao_salvar_substituir_e_consultar(pagina, largura):
    pg = pagina
    Servidor.objects.create(nome="Substituto de teste visual")
    entrar(pg, "gestor")
    pg.set_viewport_size({"width": largura, "height": 700})
    pg.goto("/cadastros/configuracao/")
    out = Path("artifacts/configuracao")
    out.mkdir(parents=True, exist_ok=True)
    nome = pg.locator("#id_nome_extenso")
    expect(nome).to_be_enabled()
    nome.fill("")
    pg.get_by_role("button", name="Salvar configuração", exact=True).click()
    expect(pg.locator("#id_nome_extenso-erro")).to_be_visible()
    _axe_estavel(pg)
    pg.screenshot(path=str(out/f"erro-{largura}.png"), full_page=True)
    nome.fill("Unidade sintética de conferência visual")
    pg.get_by_role("button", name="Salvar configuração", exact=True).click()
    expect(pg.locator(".toast")).to_contain_text("salva")
    expect(nome).to_have_value("Unidade sintética de conferência visual")
    abrir = pg.get_by_role("button", name="Nova substituição", exact=True)
    abrir.focus()
    abrir.press("Enter")
    dialog = pg.get_by_role("dialog", name="Nova substituição")
    expect(dialog).to_be_visible()
    dialog.locator("#id_servidor-busca").fill("Substituto de teste visual")
    dialog.get_by_role("option", name="Substituto de teste visual", exact=True).click()
    inicio = dialog.get_by_role("textbox", name="Início", exact=True)
    assert inicio.evaluate("e=>e.clientWidth") >= 200
    inicio.fill("10/07/2030")
    dialog.get_by_role("textbox", name="Fim", exact=True).fill("15/07/2030")
    dialog.get_by_label("Motivo", exact=True).fill("Afastamento sintético para teste")
    _axe_estavel(pg)
    dialog.screenshot(path=str(out/f"substituicao-{largura}.png"))
    pg.keyboard.press("Escape")
    expect(abrir).to_be_focused()
    abrir.press("Enter")
    expect(inicio).to_have_value("10/07/2030")
    # Reabertura foca a busca: fechar a lista antes de alcançar a ação do diálogo.
    pg.keyboard.press("Tab")
    expect(dialog).to_be_visible()
    dialog.get_by_role("button", name="Cadastrar substituição", exact=True).click()
    registro = pg.locator('section[aria-labelledby="t-substituicoes"] .registro').filter(has_text="Substituto de teste visual")
    expect(registro).to_be_visible()
    registro.get_by_role("button", name="Encerrar", exact=True).click()
    expect(registro.get_by_role("button", name="Reativar", exact=True)).to_be_visible()
    registro.get_by_role("button", name="Reativar", exact=True).click()
    expect(registro.get_by_role("button", name="Encerrar", exact=True)).to_be_visible()
    _axe_estavel(pg)
    pg.context.clear_cookies()
    entrar(pg, "operador")
    pg.goto("/cadastros/configuracao/")
    expect(pg.locator("#id_nome_extenso")).to_be_disabled()
    expect(pg.get_by_role("button", name="Salvar configuração", exact=True)).to_have_count(0)
    expect(pg.get_by_role("button", name="Nova substituição", exact=True)).to_have_count(0)
    _axe_estavel(pg)
    pg.screenshot(path=str(out/f"consulta-{largura}.png"), full_page=True)
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_configuracao_ausente_e_usuario_sem_unidade(pagina, dados_e2e, largura):
    nova = Unidade.objects.create(nome="Unidade sintética sem configuração", sigla="NOVA")
    Lotacao.objects.filter(usuario=dados_e2e.usuarios["gestor"]).update(unidade=nova)
    pg = pagina
    entrar(pg, "gestor")
    pg.set_viewport_size({"width": largura, "height": 700})
    pg.goto("/cadastros/configuracao/")
    expect(pg.get_by_text("NOVA ainda não tem configuração", exact=False)).to_be_visible()
    expect(pg.get_by_role("button", name="Nova substituição", exact=True)).to_have_count(0)
    _axe_estavel(pg)
    out = Path("artifacts/configuracao")
    out.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(out/f"sem-configuracao-{largura}.png"), full_page=True)
    Lotacao.objects.filter(usuario=dados_e2e.usuarios["operador"]).delete()
    pg.context.clear_cookies()
    entrar(pg, "operador")
    pg.goto("/cadastros/configuracao/")
    expect(pg.get_by_role("heading", name="Sem unidade", exact=True)).to_be_visible()
    expect(pg.locator("#form-configuracao")).to_have_count(0)
    _axe_estavel(pg)
    pg.screenshot(path=str(out/f"sem-unidade-{largura}.png"), full_page=True)
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")
