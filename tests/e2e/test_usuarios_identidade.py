"""Usuários: grupo de perfis, campos inferiores, erro e diálogo aninhado."""
from pathlib import Path

import pytest
from django.contrib.auth.models import Group
from playwright.sync_api import expect

from gestao.identidade.models import Usuario

from .conftest import SENHA, entrar
from .test_justificativas_identidade import _axe_estavel

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_usuarios_dialogo_responsivo(pagina, dados_e2e, largura):
    admin = Usuario.objects.create_user("adminvisual", "adminvisual@pc.pr.gov.br", SENHA, nome="Admin Visual")
    admin.groups.add(Group.objects.get(name="ADMINISTRADOR"))
    pg = pagina
    entrar(pg, "adminvisual")
    pg.set_viewport_size({"width": largura, "height": 800})
    pg.goto("/cadastros/usuarios/")
    abrir = pg.get_by_role("button", name="Novo usuário", exact=True).first
    abrir.focus()
    abrir.press("Enter")
    janela = pg.get_by_role("dialog", name="Novo usuário", exact=True)
    expect(janela.get_by_role("group", name="Perfis de acesso")).to_be_visible()
    assert not janela.evaluate("e=>e.scrollWidth>e.clientWidth")
    janela.get_by_label("Nome completo").fill("Pessoa de Teste Visual")
    janela.locator("input[name=login]").fill("visual.teste")
    janela.get_by_label("E-mail institucional").fill("visual.teste@pc.pr.gov.br")
    janela.get_by_label("Operador de viagens", exact=True).check()
    janela.get_by_role("button", name="Cadastrar unidade").click()
    nested = pg.get_by_role("dialog", name="Cadastrar unidade", exact=True)
    expect(nested).to_be_visible()
    pg.keyboard.press("Escape")
    expect(janela.get_by_role("button", name="Cadastrar unidade")).to_be_focused()
    janela.get_by_role("button", name="Criar usuário", exact=True).click()
    expect(janela).to_be_visible()
    expect(janela.get_by_label("Nome completo")).to_have_value("Pessoa de Teste Visual")
    _axe_estavel(pg)
    out = Path("artifacts/usuarios")
    out.mkdir(parents=True, exist_ok=True)
    janela.get_by_label("Senha inicial", exact=True).fill("Inicial-Segura-2030!")
    janela.get_by_label("Confirmação da senha", exact=True).fill("Inicial-Segura-2030!")
    janela.screenshot(path=str(out / f"inferior-{largura}.png"))
    janela.get_by_role("button", name="Criar usuário", exact=True).click()
    expect(pg.get_by_role("link", name="Pessoa de Teste Visual", exact=True)).to_be_visible()
    novo = Usuario.objects.get(login="visual.teste")
    assert novo.deve_trocar_senha
    assert list(novo.groups.values_list("name", flat=True)) == ["OPERADOR_VIAGENS"]
    _axe_estavel(pg)
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")
