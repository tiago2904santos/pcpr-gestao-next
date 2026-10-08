"""Conferência visual do dossiê nas cinco larguras, com controles reais."""

import json
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.plataforma import outbox
from gestao.viagens.models import Oficio

from .conftest import rodar_axe

pytestmark = [pytest.mark.e2e, pytest.mark.visual, pytest.mark.a11y]


@pytest.mark.parametrize("largura", [360, 390, 768, 1024, 1440])
def test_dossie_legivel_sem_rolagem_interna_e_com_acoes_operaveis(
    logado, dados_e2e, largura,
):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    oficio = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])
    # A comparação visual representa o emitido com PDF pronto, como os prints.
    # Concluir pelo worker real evita misturar a conferência estática com um
    # polling ainda em voo. Geração/polling/abort continuam na suíte RS-02.
    outbox.processar_lote()
    assert all(d.situacao == "pronto" for d in oficio.documentos.all())
    pg.goto(f"/viagens/oficios/?resumo={oficio.pk}")
    janela = pg.locator("#dialogo-resumo")
    expect(janela).to_be_visible()
    expect(janela.locator(".identidade-documental__numero")).to_have_text(oficio.numero_formatado)
    pg.wait_for_function(
        "() => document.getAnimations().every(a => a.playState !== 'running' "
        "|| a.effect.getTiming().iterations === Infinity)"
    )
    caixa = janela.bounding_box()
    assert caixa and caixa["x"] >= 0 and caixa["x"] + caixa["width"] <= largura + 1
    assert caixa["y"] >= 0 and caixa["y"] + caixa["height"] <= 901
    assert janela.evaluate("e => e.scrollWidth <= e.clientWidth + 1")
    assert janela.locator(".resumo__trechos").evaluate(
        "e => e.scrollHeight <= e.clientHeight + 1"
    ), "O roteiro deve poder ser lido na rolagem única do dossiê."
    for alvo in [".resumo__definicoes", ".resumo__indicadores", ".resumo__cartoes"]:
        assert janela.locator(alvo).evaluate("e => e.scrollWidth <= e.clientWidth + 1")

    pasta = Path("artifacts/piloto-resumo")
    pasta.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(pasta / f"dossie-{largura}.png"))
    violacoes = rodar_axe(pg)
    (pasta / f"axe-{largura}.json").write_text(
        json.dumps(violacoes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    assert not violacoes
    # A leitura longa não pode tirar do alcance as decisões do rodapé.
    janela.locator("#resumo-documentos-area").scroll_into_view_if_needed()
    acoes = janela.locator("#resumo-rodape")
    expect(acoes).to_be_in_viewport()
    botao = acoes.get_by_role("button", name="Mais ações", exact=True)
    botao.press("Enter")
    painel = pg.locator(".menu__painel:popover-open")
    expect(painel).to_be_visible()
    pg.keyboard.press("Escape")
    expect(botao).to_be_focused()
    # Tab e Shift+Tab permanecem na janela; Escape volta para a página.
    for tecla in ["Tab", "Shift+Tab"]:
        pg.keyboard.press(tecla)
        assert janela.evaluate("e => e.contains(document.activeElement)")
    pg.keyboard.press("Escape")
    expect(janela).not_to_be_visible()
    assert pg.erros_console == []


@pytest.mark.parametrize("largura", [360, 1440])
@pytest.mark.parametrize("vazio", [False, True])
def test_dossie_ui_lab_conteudo_longo_e_vazio(logado, largura, vazio):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.goto("/ui-lab/")
    nome = "Dossiê sem dados" if vazio else "Dossiê de viagem"
    pg.get_by_role("button", name=nome, exact=True).click()
    identificador = "#lab-dossie-vazio" if vazio else "#lab-dossie"
    janela = pg.locator(identificador)
    expect(janela).to_be_visible()
    pg.wait_for_function(
        "() => document.getAnimations().every(a => a.playState !== 'running' "
        "|| a.effect.getTiming().iterations === Infinity)"
    )
    assert janela.evaluate("e => e.scrollWidth <= e.clientWidth + 1")
    assert not rodar_axe(pg)
    pg.keyboard.press("Escape")
    expect(pg.get_by_role("button", name=nome, exact=True)).to_be_focused()
    assert pg.erros_console == []
