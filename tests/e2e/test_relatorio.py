"""E2E: relatório técnico (módulo 9c) — da lista da prestação para o RT; o texto grava
sozinho; "Outro" no custeio abre o texto livre; diária acima da liberada é recusada; o PDF
de um servidor abre."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_relatorio_do_texto_ao_documento(logado, dados_e2e):
    from gestao.viagens.models import PrestacaoContas, PrestacaoServidor, RelatorioTecnico

    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    a = PrestacaoServidor.objects.filter(prestacao=p).order_by("servidor__nome").first()
    pg = logado
    pg.goto("/viagens/prestacoes/")
    pg.locator(f"#equipe-{p.pk}").get_by_role("link", name="Relatório técnico").click()
    expect(pg.get_by_role("heading", name="Relato")).to_be_visible()
    pg.get_by_label("Objetivo da participação").fill("Atendimento ao público no evento.")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    assert RelatorioTecnico.objects.get(prestacao=p).atividade.startswith("Atendimento")

    expect(pg.get_by_label("Translado (outro)")).to_be_hidden()
    pg.locator("#custeio fieldset").first.get_by_text("Outro", exact=True).click()
    pg.get_by_label("Translado (outro)").fill("Táxi da rodoviária")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")

    pg.locator(f"#ps-{a.pk}-diaria").fill("999999")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("liberado")

    # O PDF do servidor (o visualizador de PDF não abre no navegador sem interface).
    href = pg.get_by_role("link", name=f"PDF do RT de {a.servidor.nome}").get_attribute("href")
    resposta = pg.request.get(href)
    assert resposta.ok and resposta.headers["content-type"] == "application/pdf"
