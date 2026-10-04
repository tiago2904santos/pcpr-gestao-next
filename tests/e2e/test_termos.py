"""E2E: termo de autorização a partir do ofício, com a herança à vista e os documentos."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

from gestao.viagens.models import TermoAutorizacao

pytestmark = pytest.mark.e2e


def test_termo_a_partir_do_oficio(logado, dados_e2e):
    pg = logado
    oficio = dados_e2e.ids["oficio_emitido"]
    pg.goto(f"/viagens/oficios/?resumo={oficio}")
    janela = pg.get_by_role("dialog")
    janela.get_by_role("button", name="Mais ações").click()
    janela.get_by_role("menuitem", name="Novo termo de autorização").press("Enter")
    # Um clique: o termo nasce ligado ao ofício e abre direto nos documentos.
    expect(pg.locator(".toast")).to_contain_text("criado a partir do Ofício")
    termo = TermoAutorizacao.objects.get()
    expect(pg.get_by_role("heading", name="Documentos")).to_be_visible()
    # Um link de PDF por servidor da equipe + o genérico; a herança aparece sob os campos.
    assert pg.get_by_role("link", name=re.compile(r"^Gerar .*\(PDF")).count() >= 2
    expect(pg.locator(".heranca").first).to_contain_text("Do ofício")
    # O primeiro documento aparece como vai sair; o evento editado grava sozinho e a
    # prévia se refaz.
    pg.locator("#previa").scroll_into_view_if_needed()  # o visualizador carrega ao aparecer
    folha = pg.frame_locator("#folha-termo")
    expect(folha.locator("body")).to_contain_text("TERMO DE AUTORIZAÇÃO")
    pg.get_by_role("textbox", name="Evento").fill("Feira Fictícia")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    expect(folha.locator("body")).to_contain_text("Feira Fictícia")
    termo.refresh_from_db()
    assert termo.evento == "Feira Fictícia"
    resposta = pg.request.get(f"/viagens/termos/{termo.pk}/documento/generico.pdf")
    assert resposta.ok and resposta.body().startswith(b"%PDF")
    pg.goto("/viagens/termos/")
    expect(pg.locator(".registro").first).to_contain_text("Termo")
    assert pg.erros_console == []  # type: ignore[attr-defined]


def test_cancelar_e_reativar_termo(logado, dados_e2e):
    from gestao.identidade.models import Usuario
    from gestao.viagens import termos
    from gestao.viagens.models import Oficio

    oficio = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])
    termo = termos.salvar(Usuario.objects.get(login="operador"), oficio=oficio)
    pg = logado
    pg.goto("/viagens/termos/")
    pg.get_by_role("button", name=f"Ações do {termo}").click()
    # Pelo teclado (o clique do Playwright espera a animação do painel "assentar").
    pg.get_by_role("menuitem", name="Cancelar").press("Enter")
    janela = pg.get_by_role("dialog", name=re.compile("Cancelar o Termo"))
    janela.get_by_label(re.compile("Motivo do cancelamento")).fill("Evento adiado")
    janela.get_by_role("button", name="Cancelar termo").click()
    expect(pg.locator(".toast")).to_contain_text("cancelado")
    termo.refresh_from_db()
    assert termo.cancelado and termo.motivo_cancelamento == "Evento adiado"
    pg.goto("/viagens/termos/?aba=cancelados")
    pg.get_by_role("button", name=f"Ações do {termo}").click()
    pg.get_by_role("menuitem", name="Reativar").press("Enter")
    expect(pg.locator(".toast")).to_contain_text("reativado")
    assert pg.erros_console == []  # type: ignore[attr-defined]
