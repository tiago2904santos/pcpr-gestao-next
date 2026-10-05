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


def test_sugerir_e_copiar_textos(logado, dados_e2e):
    from gestao.viagens.models import Oficio, PrestacaoContas, RelatorioTecnico, Trecho

    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    outro = Oficio.objects.get(pk=dados_e2e.ids["oficio_rascunho"])
    Trecho.objects.filter(oficio=outro, ordem=1).update(
        destino=Trecho.objects.get(oficio=p.oficio, ordem=1).destino)
    RelatorioTecnico.objects.create(prestacao=PrestacaoContas.objects.create(oficio=outro),
                                    medidas="Medidas copiadas do outro ofício.")
    pg = logado
    pg.goto(f"/viagens/prestacoes/equipe/{p.pk}/relatorio/")
    pg.get_by_role("button", name="Sugerir texto para conclusão").click()
    expect(pg.locator("#rt-conclusao")).to_have_value(
        __import__("re").compile("foi realizada conforme o planejado"))
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    assert "conforme o planejado" in RelatorioTecnico.objects.get(prestacao=p).conclusao

    pg.get_by_role("combobox", name="Copiar de outro relatório técnico").click()
    pg.get_by_role("option", name=f"Ofício {outro.numero_formatado} · mesmo destino").click()
    pg.get_by_role("button", name="Copiar textos").click()
    expect(pg.locator("#rt-medidas")).to_have_value("Medidas copiadas do outro ofício.")
