"""E2E: janela "Baixar documentos" — lista vinda do servidor, regras de "um PDF só" e o
download pelo navegador; a escolha fica lembrada."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_baixar_documentos_do_termo(logado, dados_e2e):
    from gestao.identidade.models import Usuario
    from gestao.viagens import termos
    from gestao.viagens.models import Oficio

    termo = termos.salvar(Usuario.objects.get(login="operador"),
                          oficio=Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"]))
    pg = logado
    pg.goto(f"/viagens/termos/{termo.pk}/")
    acoes = pg.locator(".registro-hero__acoes")
    acoes.locator("[data-menu-botao]").click()
    acoes.get_by_role("menuitem", name="Baixar documentos", exact=True).click()
    janela = pg.get_by_role("dialog", name="Baixar documentos")
    expect(janela).to_be_visible()
    caixas = janela.locator("input[name=itens]")
    expect(caixas.first).to_be_checked()
    total = caixas.count()
    assert total >= 2
    unico = janela.get_by_role("radio", name="Um PDF só")
    expect(unico).to_be_enabled()
    # Com um só marcado, "um PDF só" desabilita; DOCX também.
    janela.get_by_role("button", name="Desmarcar todos").click()
    expect(janela.get_by_role("button", name="Baixar")).to_be_disabled()
    caixas.first.check()
    expect(unico).to_be_disabled()
    janela.get_by_role("button", name="Marcar todos").click()
    expect(unico).to_be_enabled()
    janela.locator("label[for=baixar-unico]").click()  # o cartão inteiro é o rótulo
    expect(unico).to_be_checked()
    with pg.expect_download() as baixado:
        janela.get_by_role("button", name="Baixar").click()
    assert baixado.value.suggested_filename == f"termo-{termo.pk}-documentos.pdf"
    expect(janela).to_be_hidden()
    # A escolha fica lembrada na próxima abertura.
    acoes.locator("[data-menu-botao]").click()
    acoes.get_by_role("menuitem", name="Baixar documentos", exact=True).click()
    expect(pg.get_by_role("dialog", name="Baixar documentos").get_by_role(
        "radio", name="Um PDF só")).to_be_checked()


def test_baixar_documentos_pelo_resumo_do_oficio(logado, dados_e2e):
    from gestao.plataforma import outbox
    from gestao.viagens.models import Documento

    while outbox.processar_lote():
        pass
    assert Documento.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"],
                                 tipo="oficio").situacao == "pronto"
    pg = logado
    pg.goto(f"/viagens/oficios/?resumo={dados_e2e.ids['oficio_emitido']}")
    # "Baixar documentos…" mora em "Mais ações" (o mesmo menu ⋮ da linha, D7).
    resumo = pg.get_by_role("dialog", name="Resumo do ofício")
    resumo.get_by_role("button", name="Mais ações").click()
    resumo.get_by_role("menuitem", name="Baixar documentos…").click()
    janela = pg.get_by_role("dialog", name="Baixar documentos")
    expect(janela.locator("input[name=itens]").first).to_be_checked()
    with pg.expect_download() as baixado:
        janela.get_by_role("button", name="Baixar").click()
    assert baixado.value.suggested_filename.endswith(".pdf")
