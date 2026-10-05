"""E2E: documentos da prestação (módulo 9d) — anexar o despacho e um comprovante com valor,
ver a soma conferida com a diária, remover e trazer de volta."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_documentos_anexar_conferir_e_voltar(logado, dados_e2e):
    from gestao.viagens.models import AnexoPrestacao, PrestacaoContas, PrestacaoServidor

    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    a = PrestacaoServidor.objects.filter(prestacao=p).order_by("servidor__nome").first()
    pg = logado
    pg.goto("/viagens/prestacoes/")
    pg.locator(f"#equipe-{p.pk}").get_by_role("link", name="Documentos").click()
    expect(pg.get_by_role("heading", name="Despacho assinado")).to_be_visible()
    arquivo = {"name": "despacho.pdf", "mimeType": "application/pdf",
               "buffer": b"%PDF-1.4 teste e2e"}
    pg.locator("#enviar-despacho").set_input_files(arquivo)
    pg.locator("#despacho").get_by_role("button", name="Anexar", exact=True).click()
    expect(pg.locator(".toast").first).to_contain_text("Documento anexado")
    expect(pg.locator("#despacho")).to_contain_text("despacho.pdf")

    cartao = pg.locator(f"#ps-{a.pk}")
    cartao.locator(f"#enviar-comprovante-{a.pk}").set_input_files(
        {"name": "saque.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4 saque"})
    cartao.locator(f"#enviar-comprovante-{a.pk}-valor").fill("R$ 1,00")
    cartao.get_by_role("button", name="Anexar", exact=True).first.click()
    expect(pg.locator(f"#ps-{a.pk}")).to_contain_text("Os comprovantes somam R$ 1,00")

    pg.locator(f"#ps-{a.pk}").get_by_role("button", name="Remover saque.pdf").click()
    expect(pg.locator("#anteriores")).to_contain_text("saque.pdf")
    pg.locator("#anteriores").get_by_role("button", name="Trazer de volta saque.pdf").click()
    expect(pg.locator(f"#ps-{a.pk}")).to_contain_text("saque.pdf")
    assert AnexoPrestacao.objects.filter(tipo="comprovante", removido_em__isnull=True).count() == 1
