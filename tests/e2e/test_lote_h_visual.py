"""Capturas reais do checkpoint e regressão das ações documentais do Lote H."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import expect

from gestao.viagens.models import Documento

from .conftest import SENHA, rodar_axe

pytestmark = pytest.mark.e2e


@pytest.fixture
def dados_e2e(transactional_db, monkeypatch):
    from gestao.viagens.tests.cenarios import cenario_completo

    instante = timezone.localtime().replace(hour=12, minute=0, second=0, microsecond=0)
    monkeypatch.setattr(timezone, "now", lambda: instante)
    return cenario_completo(senha=SENHA)


def test_lote_h_capturas(logado, dados_e2e):
    pg = logado
    pg.emulate_media(reduced_motion="reduce")
    etapa = os.environ.get("LOTE_H_CAPTURA", "depois")
    pasta = Path(os.environ.get("LOTE_H_EVIDENCIAS", "artifacts/lote-h")) / etapa
    pasta.mkdir(parents=True, exist_ok=True)
    rascunho = dados_e2e.ids["oficio_rascunho"]
    emitido = dados_e2e.ids["oficio_emitido"]
    doc = Documento.objects.get(oficio_id=emitido)
    Documento.objects.filter(pk=doc.pk).update(situacao="falhou", erro="Falha simulada no laboratório")
    for largura in (360, 390, 768, 1024, 1440):
        pg.set_viewport_size({"width": largura, "height": 900})
        pg.goto(f"/viagens/oficios/{rascunho}/editar/")
        expect(pg.get_by_role("heading", level=1)).to_be_visible()
        pg.screenshot(path=str(pasta / f"folha-{largura}.png"), full_page=True, animations="disabled")
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        pg.goto(f"/viagens/oficios/?resumo={emitido}")
        dialogo = pg.get_by_role("dialog", name="Resumo do ofício")
        expect(dialogo).to_be_visible()
        expect(dialogo).to_contain_text("falhou")
        pg.screenshot(path=str(pasta / f"falha-{largura}.png"), full_page=True, animations="disabled")
        if etapa == "depois":
            expect(dialogo.get_by_role("button", name="Gerar de novo Ofício versão 1")).to_be_visible()
        dialogo.get_by_role("heading", name="Documentos", exact=True).scroll_into_view_if_needed()
        pg.screenshot(path=str(pasta / f"falha-documentos-{largura}.png"), full_page=True, animations="disabled")
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_motorista_autosave_e_conflito_entre_abas(logado, dados_e2e):
    pg = logado
    oficio = dados_e2e.ids["oficio_rascunho"]
    rota = f"/viagens/oficios/{oficio}/editar/"
    pg.goto(rota)
    outra = pg.context.new_page()
    outra.goto(rota)
    try:
        pg.get_by_label("Motivo da viagem").fill("Alteração da primeira aba.")
        expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
        pg.reload()
        expect(pg.get_by_role("button", name="Desmarcar Carla Regina Duarte como motorista"))\
            .to_have_attribute("aria-pressed", "true")
        outra.get_by_label("Motivo da viagem").fill("Alteração da segunda aba.")
        expect(outra.locator("[data-status-salvamento]")).to_contain_text("Outra pessoa salvou")
        from gestao.viagens.models import Oficio

        assert Oficio.objects.get(pk=oficio).motivo == "Alteração da primeira aba."
    finally:
        outra.close()


def test_falha_retry_por_teclado_e_pdf_sem_duplicacao(logado, dados_e2e):
    from gestao.plataforma import outbox
    from gestao.plataforma.models import MensagemOutbox

    pg = logado
    oficio = dados_e2e.ids["oficio_emitido"]
    doc = Documento.objects.get(oficio_id=oficio)
    identidade = (doc.pk, doc.versao, doc.dados, doc.oficio.numero)
    mensagem = MensagemOutbox.objects.get(chave_idempotencia=f"documento:{doc.pk}")
    Documento.objects.filter(pk=doc.pk).update(situacao="falhou", erro="Falha controlada")
    MensagemOutbox.objects.filter(pk=mensagem.pk).update(situacao="falhou", tentativas=8)
    pg.goto(f"/viagens/oficios/?resumo={oficio}")
    dialogo = pg.get_by_role("dialog", name="Resumo do ofício")
    botao = dialogo.get_by_role("button", name="Gerar de novo Ofício versão 1")
    botao.focus()
    expect(botao).to_be_focused()
    assert rodar_axe(pg) == []
    botao.press("Enter")
    expect(pg.get_by_role("dialog", name="Resumo do ofício")).to_contain_text("gerando")
    outbox.processar_lote()
    doc.refresh_from_db()
    assert doc.situacao == "pronto"
    assert (doc.pk, doc.versao, doc.dados, doc.oficio.numero) == identidade
    expect(pg.get_by_role("dialog", name="Resumo do ofício").get_by_role(
        "link", name="Ofício v1 (nova aba)", exact=True)).to_be_visible()
    assert Documento.objects.filter(oficio_id=oficio).count() == 1
    assert MensagemOutbox.objects.filter(chave_idempotencia=f"documento:{doc.pk}").count() == 1
    resposta = pg.request.get(reverse("viagens:baixar_documento", args=[doc.pk]))
    assert resposta.status == 200
    assert resposta.body().startswith(b"%PDF-")
    assert resposta.headers["x-content-sha256"] == doc.sha256
    pg.keyboard.press("Escape")
    expect(pg.get_by_role("dialog", name="Resumo do ofício")).to_be_hidden()
