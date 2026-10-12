"""Fallback real sem JavaScript: erro, anexação e troca preservam o retorno."""

import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from gestao.plataforma import outbox
from gestao.viagens import assinados
from gestao.viagens.models import Oficio, ViaAssinada

pytestmark = pytest.mark.e2e
PDF = b"%PDF-1.7\n% documento sintetico\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def test_fallback_erro_por_teclado(logado, dados_e2e):
    from .conftest import rodar_axe

    pg = logado
    pg.set_viewport_size({"width": 360, "height": 800})
    pg.goto(f"/viagens/assinados/oficio/{dados_e2e.ids['oficio_emitido']}/",
            wait_until="networkidle")
    botao = pg.get_by_role("button", name="Anexar via assinada")
    botao.focus()
    expect(botao).to_be_focused()
    with pg.expect_response(lambda r: r.request.method == "POST") as resposta:
        pg.keyboard.press("Enter")
    assert resposta.value.status == 422
    pg.wait_for_load_state("networkidle")
    expect(pg.locator("#arquivo-assinado-erro")).to_have_text("Escolha o PDF assinado.")
    assert not rodar_axe(pg)


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_fallback_sem_js_erro_anexar_e_trocar(logado, dados_e2e, largura):
    while outbox.processar_lote():
        pass
    assert assinados.documento_emitido(
        Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"]), "oficio") is not None
    origem = urlsplit(logado.url)
    base = f"{origem.scheme}://{origem.netloc}"
    context = logado.context.browser.new_context(
        storage_state=logado.context.storage_state(), java_script_enabled=False,
        base_url=base, viewport={"width": largura, "height": 800}, locale="pt-BR")
    pg = context.new_page()
    pg.bring_to_front()
    pk = dados_e2e.ids["oficio_emitido"]
    rota = f"/viagens/assinados/oficio/{pk}/"
    try:
        pg.goto(rota, wait_until="networkidle")
        retorno = pg.locator('input[name="voltar"]').input_value()
        assert retorno.startswith('/viagens/oficios/') and f'resumo={pk}' in retorno
        expect(pg.get_by_role("heading", name="Anexar via assinada")).to_be_visible()
        campo = pg.locator("#arquivo-assinado")
        campo.set_input_files({"name": "invalido.pdf", "mimeType": "application/pdf", "buffer": b"invalido"})
        with pg.expect_response(lambda r: r.request.method == "POST") as resposta:
            pg.get_by_role("button", name="Anexar via assinada").click()
        assert resposta.value.status == 422
        pg.wait_for_load_state("networkidle")
        expect(campo).to_have_attribute("aria-invalid", "true")
        expect(pg.locator("#arquivo-assinado-erro")).to_be_visible()
        if os.environ.get("MIGRACAO_CAPTURAS"):
            pg.screenshot(path=str(Path(os.environ["MIGRACAO_CAPTURAS"]) / f"assinados-erro-{largura}.png"),
                          full_page=True, animations="disabled")
        for nome, acao in [("primeiro.pdf", "Anexar via assinada"), ("segundo.pdf", "Trocar via assinada")]:
            campo.set_input_files({"name": nome, "mimeType": "application/pdf", "buffer": PDF})
            pg.get_by_role("button", name=acao).click()
            expect(pg).to_have_url(base + retorno)
            pg.goto(rota)
            expect(pg.get_by_role("heading", name="Trocar via assinada")).to_be_visible()
            expect(pg.get_by_role("link", name="Abrir a via atual")).to_be_visible()
        if os.environ.get("MIGRACAO_CAPTURAS"):
            pg.screenshot(path=str(Path(os.environ["MIGRACAO_CAPTURAS"]) / f"assinados-troca-{largura}.png"),
                          full_page=True, animations="disabled")
        vias = ViaAssinada.objects.filter(oficio_id=pk)
        assert vias.count() == 2
        assert vias.filter(revogada_em__isnull=True).get().nome_original == "segundo.pdf"
    finally:
        context.close()
