"""Visualizador da folha da viagem: o cartão abre o documento pronto ao lado do resumo (ou só
o resumo), as setas passam entre os documentos do mesmo tipo e Esc devolve o foco ao cartão."""

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
    expect(pg.locator("#visualizador-resumo #resumo-titulo")).to_be_attached()
    titulo = pg.locator("[data-v-titulo]").inner_text()
    pg.keyboard.press("ArrowRight")
    expect(pg.locator("[data-v-posicao]")).to_have_text("2 de 2")
    expect(pg.locator("[data-v-titulo]")).not_to_have_text(titulo)
    expect(pg.locator("[data-v-proximo]")).to_be_disabled()
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
    expect(pg.locator("[data-v-navegacao]")).to_be_hidden()
    expect(pg.frame_locator("[data-v-folha]").locator("body")).to_contain_text("Ofício")
    expect(pg.locator("#visualizador-resumo #resumo-rodape")).to_be_visible()
    assert pg.erros_console == []
