"""E2E: roteiros cadastrados e o uso como modelo no ofício (paridade com a referência)."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from django.utils import timezone
from playwright.sync_api import expect

from gestao.viagens.models import Oficio, Roteiro

pytestmark = pytest.mark.e2e


def _data_hora(pg, campo: str, dias: int, hora: int) -> None:
    alvo = timezone.localtime() + timedelta(days=dias)
    pg.locator(f"#id_{campo}_0").fill(alvo.strftime("%d/%m/%Y"))
    pg.locator(f"#id_{campo}_1").fill(f"{hora:02d}:00")


def test_cadastrar_roteiro_pela_tela(logado):
    pg = logado
    pg.goto("/viagens/")
    pg.get_by_role("navigation", name="Navegação principal").get_by_role(
        "link", name="Roteiros").click()
    expect(pg.get_by_role("heading", level=1)).to_have_text("Roteiros")
    expect(pg.get_by_role("link", name=re.compile("Que vão acontecer"))).to_be_visible()
    pg.get_by_role("link", name="Novo roteiro").click()
    expect(pg.get_by_role("heading", level=1)).to_have_text("Novo roteiro")
    pg.locator("input[name='destino-0-cidade']").fill("Londrina/PR")
    _data_hora(pg, "destino-0-saida", 12, 7)
    _data_hora(pg, "retorno-saida", 14, 8)
    pg.get_by_label("Quantidade de servidores").fill("4")
    pg.get_by_role("button", name="Salvar roteiro").click()
    expect(pg.locator(".toast")).to_contain_text("cadastrado")
    expect(pg.locator("#diarias")).to_contain_text("Calculado para 4 servidores")
    roteiro = Roteiro.objects.latest("pk")
    assert roteiro.quantidade_servidores == 4 and roteiro.trechos.count() == 2
    assert pg.erros_console == []  # type: ignore[attr-defined]


def test_oficio_usa_roteiro_cadastrado(logado, dados_e2e):
    """Como no modelo: o roteiro do ofício vem de um roteiro cadastrado."""
    pg = logado
    oficio_id = dados_e2e.ids["oficio_vazio"]
    pg.goto(f"/viagens/oficios/{oficio_id}/editar/")
    pg.get_by_label("Motivo da viagem").fill("Motivo digitado antes de escolher o roteiro.")
    escolha = pg.get_by_role("combobox", name="Usar um roteiro cadastrado")
    escolha.fill("ponta")
    pg.get_by_role("option", name=re.compile("Ponta Grossa")).click()
    pg.get_by_role("button", name="Usar este roteiro").click()
    aviso = pg.locator("#roteiro-aplicado")
    expect(aviso).to_contain_text("preenchidos")
    expect(aviso).to_be_focused()
    expect(pg.locator("input[name='destino-0-cidade']")).to_have_value("Ponta Grossa/PR")
    expect(pg.get_by_label("Motivo da viagem")).to_have_value(
        "Motivo digitado antes de escolher o roteiro.")
    pg.get_by_role("button", name="Salvar rascunho").click()
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Rascunho salvo às")
    expect(pg.locator(".usar-roteiro__origem")).to_contain_text(
        f"roteiro #{dados_e2e.ids['roteiro']}")
    oficio = Oficio.objects.get(pk=oficio_id)
    assert oficio.roteiro_id == dados_e2e.ids["roteiro"] and oficio.trechos.count() == 2
    assert pg.erros_console == []  # type: ignore[attr-defined]


def test_criar_oficio_pelo_menu_do_roteiro(logado, dados_e2e):
    pg = logado
    pg.goto("/viagens/roteiros/")
    pg.get_by_role("button", name=f"Ações do roteiro #{dados_e2e.ids['roteiro']}").click()
    pg.get_by_role("menuitem", name="Criar ofício com este roteiro").click()
    expect(pg).to_have_url(re.compile(r"/viagens/oficios/\d+/editar/$"))
    expect(pg.locator(".toast")).to_contain_text(f"roteiro #{dados_e2e.ids['roteiro']}")
    expect(pg.locator("input[name='destino-0-cidade']")).to_have_value("Ponta Grossa/PR")
