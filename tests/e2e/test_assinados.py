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


def test_anexar_via_da_os_pela_barra_e_revogar_por_http(logado, dados_e2e, tmp_path):
    ordem = _os_gerada(dados_e2e)
    pg = logado
    pg.goto(f"/viagens/ordens/{ordem.pk}/#documento")
    bloco = pg.locator("#editor-ordem")
    pg.locator("#documento").scroll_into_view_if_needed()
    expect(bloco.get_by_role("link", name="Anexar", exact=True)).to_be_visible(timeout=15000)
    expect(bloco.locator("[data-anexar-assinado]")).to_have_text("Anexar")

    # Arquivo que não é PDF: a janela recusa antes de enviar.
    errado = tmp_path / "foto.png"
    errado.write_bytes(b"\x89PNG")
    bloco.get_by_role("link", name="Anexar", exact=True).click()
    janela = pg.get_by_role("dialog", name="Anexar via assinada")
    expect(janela).to_be_visible()
    expect(janela).to_contain_text(str(ordem))
    janela.locator('input[type="file"]').set_input_files(str(errado))
    janela.get_by_role("button", name="Anexar via assinada").click()
    expect(janela.locator("#dialogo-assinado-erro")).to_contain_text("Envie um arquivo PDF.")
    assert not ViaAssinada.objects.exists()

    certo = tmp_path / "os-assinada.pdf"
    certo.write_bytes(PDF)
    janela.locator('input[type="file"]').set_input_files(str(certo))
    janela.get_by_role("button", name="Anexar via assinada").click()
    expect(pg.locator(".toast").first).to_contain_text("Via assinada anexada")
    # A conferência do PDF (ADR 0022) avisa, sem bloquear: este PDF de teste não tem assinatura.
    expect(pg.locator(".toast--aviso").first).to_contain_text("não tem assinatura digital")
    pg.locator("#documento").scroll_into_view_if_needed()
    expect(bloco.locator(".editor__estado").get_by_text("Assinado", exact=True)).to_be_visible()
    expect(bloco.locator("[data-anexar-assinado]")).to_have_text("Trocar via")
    via = ViaAssinada.objects.get()
    assert via.ordem_id == ordem.pk and via.revogada_em is None
    assert via.nome_original == "os-assinada.pdf"

    # A via abre pela rota própria; "Gerar a OS" continua gerando o documento atual.
    assert pg.request.get(f"/viagens/assinados/via/{via.pk}/").body() == PDF
    gerado = pg.request.get(f"/viagens/ordens/{ordem.pk}/documento.pdf")
    assert gerado.body() != PDF and gerado.body().startswith(b"%PDF")
    expect(pg.locator("#frase-ordem")).to_contain_text("Assinado")

    # Ação visual de remover ausente também em d566; dívida documentada, sem simular UI.
    # Exercita o POST real com a sessão/CSRF do navegador, preservando o arquivo.
    csrf = pg.locator('input[name="csrfmiddlewaretoken"]').first.input_value()
    resposta = pg.request.post(f"/viagens/assinados/via/{via.pk}/remover/", form={
        "csrfmiddlewaretoken": csrf, "voltar": f"/viagens/ordens/{ordem.pk}/"})
    assert resposta.ok
    via.refresh_from_db()
    assert via.revogada_em is not None
    assert via.arquivo.storage.exists(via.arquivo.name)
    pg.reload()
    pg.locator("#documento").scroll_into_view_if_needed()
    expect(bloco.locator("[data-anexar-assinado]")).to_have_text("Anexar")
