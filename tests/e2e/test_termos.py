"""E2E: termo de autorização a partir do ofício, com a herança à vista e os documentos."""

from __future__ import annotations

import re
from datetime import date, timedelta

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
    janela.get_by_role("menuitem", name="Criar a partir deste ofício").press("Enter")
    janela.get_by_role("menuitem", name="Novo termo de autorização").press("Enter")
    # Um clique: o termo nasce ligado ao ofício e abre direto nos documentos.
    expect(pg.locator(".toast")).to_contain_text("criado a partir do Ofício")
    termo = TermoAutorizacao.objects.get()
    expect(pg.get_by_role("heading", name="Documentos")).to_be_visible()
    # Cada servidor e o genérico têm sua página no editor unificado vigente.
    from gestao.viagens import termos

    servidores = termos.efetivo(termo).servidores
    expect(pg.locator("[data-editores] [data-pagina]")).to_have_count(len(servidores) + 1 + bool(termo.oficio.viatura_id))
    expect(pg.locator("[data-oficio-do-termo]")).to_contain_text(termo.oficio.numero_formatado)
    expect(pg.locator("#frase-termo")).to_contain_text(termo.oficio.numero_formatado)
    # O primeiro documento aparece como vai sair; o calendário vigente do evento
    # grava sozinho e a prévia se refaz.
    pg.locator("#previa").scroll_into_view_if_needed()  # o visualizador carrega ao aparecer
    primeiro = pg.locator("[data-editores] pc-editor-documento").first
    folha = primeiro.frame_locator('iframe[data-quadro="texto"]')
    expect(folha.locator("body")).to_contain_text("TERMO DE AUTORIZAÇÃO")
    calendario = pg.locator(".mesa-evento pc-data[data-periodo] button.seletor__botao")
    calendario.click()
    foco = date.fromisoformat(pg.locator(".calendario td[tabindex='0']").get_attribute("data-data"))
    nova_data = foco + timedelta(days=1)
    dia_focado = pg.locator(".calendario td[tabindex='0']")
    dia_focado.press("ArrowRight")
    dia_focado.press("Enter")
    dia_focado.press("Enter")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    termo.refresh_from_db()
    assert termo.data_inicio == termo.data_fim == nova_data
    pg.locator("#previa").scroll_into_view_if_needed()
    expect(folha.locator("body")).to_contain_text(termos.periodo_por_extenso(nova_data, nova_data))
    resposta = pg.request.get(f"/viagens/termos/{termo.pk}/documento/generico.pdf")
    assert resposta.ok and resposta.body().startswith(b"%PDF")
    pg.goto("/viagens/termos/")
    expect(pg.locator(".registro").first).to_contain_text("Termo")
    pg.wait_for_load_state("networkidle")
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
    pg.wait_for_load_state("networkidle")
    assert pg.erros_console == []  # type: ignore[attr-defined]
