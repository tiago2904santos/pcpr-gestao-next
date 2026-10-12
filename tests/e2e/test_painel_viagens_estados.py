"""Vazio por unidade e consulta sem ações de escrita, em banco isolado."""

import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.cadastros.models import Unidade

from .conftest import entrar, rodar_axe

pytestmark = pytest.mark.e2e


def test_painel_unidade_sem_oficios(logado, dados_e2e):
    lotacao = dados_e2e.usuarios["operador"].lotacao
    lotacao.unidade = Unidade.objects.create(sigla="VZ", nome="Unidade sintética sem ofícios")
    lotacao.save(update_fields=["unidade"])
    for largura in (360, 768, 1440):
        logado.set_viewport_size({"width": largura, "height": 900})
        logado.goto("/viagens/", wait_until="networkidle")
        expect(logado.get_by_text("Nenhum rascunho pendente", exact=True)).to_be_visible()
        expect(logado.get_by_text("Nenhuma viagem programada", exact=True)).to_be_visible()
        expect(logado.locator('.registro-operacional')).to_have_count(0)
        assert not logado.evaluate("document.documentElement.scrollWidth > innerWidth")
        assert not rodar_axe(logado)
        if os.environ.get("MIGRACAO_CAPTURAS"):
            logado.screenshot(path=str(Path(os.environ["MIGRACAO_CAPTURAS"]) /
                                       f"painel-vazio-{largura}.png"),
                              full_page=True, animations="disabled")


def test_painel_consulta_menu_sem_escrita(pagina):
    entrar(pagina, "consulta")
    pagina.goto("/viagens/", wait_until="networkidle")
    botao = pagina.locator('.registro__acoes [data-menu-botao]').first
    botao.click()
    menu = pagina.locator('[role="menu"]:visible')
    expect(menu.locator('[data-menu-carregando]')).to_have_count(0)
    expect(menu.get_by_role("menuitem", name="Ver resumo", exact=True)).to_be_visible()
    for nome in ("Editar", "Cancelar", "Excluir", "Emitir"):
        expect(menu.get_by_role("menuitem", name=nome, exact=True)).to_have_count(0)
    assert not rodar_axe(pagina)
    if os.environ.get("MIGRACAO_CAPTURAS"):
        pagina.screenshot(path=str(Path(os.environ["MIGRACAO_CAPTURAS"]) /
                                   "painel-consulta-menu-1440.png"),
                          full_page=True, animations="disabled")
