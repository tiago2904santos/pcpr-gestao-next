"""E2E: o administrador cria um usuário; no primeiro acesso a pessoa é levada a definir uma
senha só dela antes de qualquer outra tela."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from .conftest import SENHA, entrar

pytestmark = pytest.mark.e2e


def test_criar_usuario_e_primeiro_acesso(pagina, dados_e2e):
    from django.contrib.auth.models import Group

    from gestao.identidade.models import Usuario

    admin = Usuario.objects.create_user("admin", "admin@pc.pr.gov.br", SENHA, nome="Admin E2E")
    admin.groups.add(Group.objects.get(name="ADMINISTRADOR"))
    pg = pagina
    entrar(pg, "admin")
    pg.goto("/cadastros/usuarios/")
    pg.get_by_role("button", name="Novo usuário").first.click()
    janela = pg.get_by_role("dialog", name="Novo usuário")
    janela.get_by_label("Nome completo").fill("Pessoa Nova")
    janela.locator("input[name=login]").fill("pessoa.nova")
    janela.get_by_label("E-mail institucional").fill("pessoa.nova@pc.pr.gov.br")
    janela.get_by_label("Operador de viagens").check()
    inicial = "Inicial-Provisoria-2026"
    janela.get_by_label("Senha inicial").fill(inicial)
    janela.get_by_label("Confirmação da senha").fill(inicial)
    janela.get_by_role("button", name="Criar usuário").click()
    expect(pg.locator(".toast")).to_contain_text("Usuário “pessoa.nova” criado")
    expect(pg.get_by_text("Troca a senha no próximo acesso")).to_be_visible()

    # Primeiro acesso: qualquer tela leva a "Defina sua senha".
    pg.context.clear_cookies()
    entrar(pg, "pessoa.nova", inicial)
    expect(pg.get_by_role("heading", name="Defina sua senha")).to_be_visible()
    pg.goto("/viagens/oficios/")
    expect(pg.get_by_role("heading", name="Defina sua senha")).to_be_visible()
    nova = "So-Minha-Senha-2026"
    pg.locator("input[name=old_password]").fill(inicial)
    pg.locator("input[name=new_password1]").fill(nova)
    pg.locator("input[name=new_password2]").fill(nova)
    pg.get_by_role("button", name="Salvar nova senha").click()
    expect(pg.locator(".toast")).to_contain_text("Senha alterada com sucesso")
    pg.goto("/viagens/oficios/")
    expect(pg.get_by_role("heading", level=1)).to_contain_text("Ofícios")
