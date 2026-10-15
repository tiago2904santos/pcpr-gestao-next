"""Visualizador da folha da viagem: o cartão abre o documento pronto ao lado do resumo (ou só
o resumo), as setas passam entre os documentos do mesmo tipo e Esc devolve o foco ao cartão."""

import re

import pytest
from playwright.sync_api import expect

from gestao.viagens import viagem
from gestao.viagens.models import Oficio
from tests.e2e.test_justificativas_identidade import _axe_estavel
from tests.e2e.test_viagens_folha_identidade import _viagem

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 1440])
def test_cartao_abre_documento_e_resumo_com_setas(logado, dados_e2e, largura):
    pg = logado
    v = _viagem(dados_e2e)
    emitido = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])
    rascunho = Oficio.objects.get(pk=dados_e2e.ids["oficio_rascunho"])
    viagem.salvar_dados(dados_e2e.usuarios["operador"], v.pk, tipos=list(v.tipos.all()),
                        vinculos={"oficios": [emitido, rascunho]})
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.goto(f"/viagens/viagens/{v.pk}/")
    cartoes = pg.locator('a[data-visualizar][data-grupo="oficio"]')
    expect(cartoes).to_have_count(2)
    # Só o emitido está pronto: abre a folha; o rascunho abre o resumo.
    assert "/documento/oficio/folha/" in (pg.locator(
        f'a[data-visualizar][href$="/oficios/{emitido.pk}/editar/"]').get_attribute(
        "data-paginas") or "")
    assert pg.locator(f'a[data-visualizar][href$="/oficios/{rascunho.pk}/editar/"]') \
        .get_attribute("data-paginas") is None

    primeiro = cartoes.first
    primeiro.click()
    dialogo = pg.locator("#dialogo-documento")
    expect(dialogo).to_be_visible()
    expect(pg.locator("[data-v-posicao]")).to_have_text("1 de 2")
    titulo = pg.locator("[data-v-titulo]").inner_text()
    pg.keyboard.press("ArrowRight")
    expect(pg.locator("[data-v-posicao]")).to_have_text("2 de 2")
    expect(pg.locator("[data-v-titulo]")).not_to_have_text(titulo)
    expect(pg.locator("[data-v-proximo]")).to_be_disabled()
    # O rascunho flutua como o resumo (com as ações dele no rodapé).
    editar = pg.locator("[data-v-editar]").get_attribute("href") or ""
    if f"/oficios/{rascunho.pk}/" in editar:
        expect(pg.locator("#visualizador-resumo #resumo-titulo")).to_be_attached()
    pg.locator("[data-v-anterior]").click()
    expect(pg.locator("[data-v-posicao]")).to_have_text("1 de 2")
    _axe_estavel(pg)
    pg.keyboard.press("Escape")
    expect(dialogo).to_be_hidden()
    expect(primeiro).to_be_focused()
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert pg.erros_console == []


def test_documento_pronto_abre_a_folha(logado, dados_e2e):
    pg = logado
    v = _viagem(dados_e2e)
    emitido = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])
    viagem.salvar_dados(dados_e2e.usuarios["operador"], v.pk, tipos=list(v.tipos.all()),
                        vinculos={"oficios": [emitido]})
    pg.set_viewport_size({"width": 1440, "height": 900})
    pg.goto(f"/viagens/viagens/{v.pk}/")
    pg.locator('a[data-visualizar][data-grupo="oficio"]').click()
    folha = pg.locator("[data-v-folha]")
    expect(folha).to_be_visible()
    assert f"/oficios/{emitido.pk}/documento/oficio/folha/" in (folha.get_attribute("src") or "")
    assert "final=1" in (folha.get_attribute("src") or "")  # emitido: sem a marca de minuta
    expect(pg.locator("[data-v-anterior]")).to_be_hidden()
    expect(pg.frame_locator("[data-v-folha]").locator("body")).to_contain_text("Ofício")
    # As ações rápidas: imprimir, baixar todos e editar (baixar e anexar assinado aparecem
    # quando há PDF emitido e quem vê pode anexar).
    for acao in ("imprimir", "todos", "editar"):
        expect(pg.locator(f"[data-v-{acao}]")).to_be_visible()
    expect(pg.locator("[data-v-cartao]")).to_be_hidden()
    assert pg.erros_console == []


def test_solicitacao_anexada_abre_no_visualizador(logado, dados_e2e, tmp_path, settings):
    pg = logado
    v = _viagem(dados_e2e)
    pdf = tmp_path / "oficio-pedido.pdf"
    pdf.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    pg.set_viewport_size({"width": 1440, "height": 900})
    pg.goto(f"/viagens/viagens/{v.pk}/")
    pg.get_by_role("button", name="Anexar e-mail ou ofício").click()
    pg.get_by_label("Ofício de solicitação").check()
    pg.set_input_files("#solicitacao-arquivo", str(pdf))
    pg.locator("#dialogo-solicitacao button[type=submit]").click()
    cartao = pg.locator('a[data-visualizar][data-grupo="solicitacao"]')
    expect(cartao).to_contain_text("oficio-pedido.pdf")
    expect(cartao).to_contain_text("Ofício")
    with pg.expect_response(lambda r: "/viagens/solicitacao/" in r.url) as resposta:
        cartao.click()
    assert resposta.value.status == 200
    assert resposta.value.headers.get("x-frame-options") == "SAMEORIGIN"
    expect(pg.locator("[data-v-baixar]")).to_have_attribute("href", re.compile(r"baixar=1"))
    expect(pg.locator("[data-v-cartao]")).to_be_hidden()
    pg.keyboard.press("Escape")
    assert pg.erros_console == []
