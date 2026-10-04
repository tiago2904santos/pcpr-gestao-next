"""E2E: via assinada pela janela — anexar o PDF que voltou assinado, ver o selo, a via
prevalecer no PDF e remover (o gerado volta a valer). Inclui a recusa no navegador."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from gestao.viagens.models import ViaAssinada

pytestmark = pytest.mark.e2e

PDF = b"%PDF-1.7\n% via assinada de teste\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _os_gerada(dados_e2e):
    from gestao.identidade.models import Usuario
    from gestao.viagens import ordens
    from gestao.viagens.models import Oficio

    ordem, _ = ordens.salvar(Usuario.objects.get(login="operador"),
                             oficios=[Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])])
    ordens.dados_do_documento(ordem, fixar=True)
    return ordem


def test_anexar_e_remover_a_via_da_os(logado, dados_e2e, tmp_path):
    ordem = _os_gerada(dados_e2e)
    pg = logado
    pg.goto(f"/viagens/ordens/{ordem.pk}/#via-assinada")
    bloco = pg.locator("#via-assinada")
    expect(bloco).to_contain_text("Sem via assinada")

    # Arquivo que não é PDF: a janela recusa antes de enviar.
    errado = tmp_path / "foto.png"
    errado.write_bytes(b"\x89PNG")
    bloco.get_by_role("link", name="Anexar via assinada").click()
    janela = pg.get_by_role("dialog", name="Anexar via assinada")
    expect(janela).to_be_visible()
    expect(janela).to_contain_text(str(ordem))
    janela.get_by_label("PDF assinado").set_input_files(str(errado))
    janela.get_by_role("button", name="Anexar via assinada").click()
    expect(janela.locator("#dialogo-assinado-erro")).to_contain_text("Envie um arquivo PDF.")
    assert not ViaAssinada.objects.exists()

    certo = tmp_path / "os-assinada.pdf"
    certo.write_bytes(PDF)
    janela.get_by_label("PDF assinado").set_input_files(str(certo))
    janela.get_by_role("button", name="Anexar via assinada").click()
    expect(pg.locator(".toast").first).to_contain_text("Via assinada anexada")
    # A conferência do PDF (ADR 0022) avisa, sem bloquear: este PDF de teste não tem assinatura.
    expect(pg.locator(".toast--aviso").first).to_contain_text("não tem assinatura digital")
    expect(pg.locator("#via-assinada")).to_contain_text("os-assinada.pdf")
    expect(pg.locator("#via-assinada .selo")).to_have_text("Assinado")
    via = ViaAssinada.objects.get()
    assert via.ordem_id == ordem.pk and via.revogada_em is None

    # A via abre pela rota própria; "Gerar a OS" continua gerando o documento atual.
    assert pg.request.get(f"/viagens/assinados/via/{via.pk}/").body() == PDF
    gerado = pg.request.get(f"/viagens/ordens/{ordem.pk}/documento.pdf")
    assert gerado.body() != PDF and gerado.body().startswith(b"%PDF")
    expect(pg.locator("#frase-ordem")).to_contain_text("Assinado")

    # Remover: confirmação no diálogo do sistema; o arquivo fica guardado.
    pg.locator("#via-assinada").get_by_role("button", name="Ações da via assinada").click()
    pg.get_by_role("menuitem", name="Remover via assinada").click()
    pg.get_by_role("dialog", name="Remover a via assinada").get_by_role(
        "button", name="Remover via assinada").click()
    expect(pg.locator(".toast").last).to_contain_text("o PDF gerado volta a valer")
    via.refresh_from_db()
    assert via.revogada_em is not None
    expect(pg.locator("#via-assinada")).to_contain_text("Sem via assinada")
