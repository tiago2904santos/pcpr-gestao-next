"""Numeração editável em Plano/OS e minuta incompleta já carregada."""

import pytest
from playwright.sync_api import expect

from gestao.viagens import ordens, planos

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 1440])
@pytest.mark.parametrize("servico,rota", [(planos, "planos"), (ordens, "ordens")])
def test_numero_autosave_atualiza_identidade_e_rejeita_duplicado(
        logado, dados_e2e, largura, servico, rota):
    pg = logado
    doc, _ = servico.salvar(dados_e2e.usuarios["operador"], numero=851)
    servico.salvar(dados_e2e.usuarios["operador"], numero=852)
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.goto(f"/viagens/{rota}/{doc.pk}/")
    pg.locator("#id_numero").fill("853")
    expect(pg.locator(".registro-hero")).to_contain_text("853/")
    expect(pg.locator("#id_numero")).to_have_value("853")
    doc.refresh_from_db()
    assert doc.numero == 853
    pg.locator("#id_numero").fill("852")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("já está em uso")
    doc.refresh_from_db()
    assert doc.numero == 853
    pg.locator("#id_numero").fill("853")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert pg.erros_console == []


@pytest.mark.parametrize("largura", [360, 1440])
def test_minuta_incompleta_ja_carregada_sem_finalizar(logado, dados_e2e, largura):
    pg = logado
    plano, _ = planos.salvar(dados_e2e.usuarios["operador"])
    assert planos.pendencias(plano)
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.goto(f"/viagens/planos/{plano.pk}/")
    quadro = pg.locator("#folha-plano")
    expect(quadro).to_have_attribute("src", quadro.get_attribute("data-src"))
    expect(quadro).not_to_have_attribute("hidden", "")
    # A folha inicia antes de rolar até Documento; conferência não bloqueia a minuta.
    expect(pg.frame_locator("#folha-plano").locator("body")).to_contain_text(
        plano.numero_formatado)
    quadro.scroll_into_view_if_needed()
    expect(quadro).to_be_visible()
    plano.refresh_from_db()
    assert plano.documento_gerado_em is None and plano.data_documento is None
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert pg.erros_console == []
