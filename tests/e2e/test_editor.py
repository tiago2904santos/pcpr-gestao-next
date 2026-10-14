"""Editor de documento no visualizador (ADR 0018), no navegador de verdade.

Escrever na folha salva sozinho; o campo vivo grava no ofício e o formulário acompanha; o
histórico lista a versão e restaura; o modo PDF troca a folha pela minuta; a barra é um
toolbar acessível (um só tabstop, setas entre os botões).
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import rodar_axe

pytestmark = [pytest.mark.e2e]


def _abrir_folha(pg: Page, pk: int):
    pg.goto(f"/viagens/oficios/{pk}/editar/#minuta")
    pg.locator("#minuta").scroll_into_view_if_needed()
    quadro = pg.frame_locator("#folha-oficio")
    quadro.locator("[data-regiao='corpo']").wait_for(timeout=15000)
    expect(pg.locator("#editor-oficio [data-salvo]")).not_to_have_text("Carregando…", timeout=10000)
    return quadro


def test_escrever_na_folha_salva_e_persiste(logado: Page, dados_e2e):
    pk = dados_e2e.ids["oficio_rascunho"]
    pg = logado
    quadro = _abrir_folha(pg, pk)
    expect(pg.locator("#editor-oficio [data-salvo]")).to_have_text("Como o modelo")
    saudacao = quadro.locator("[data-bloco='saudacao']")
    saudacao.click()
    pg.keyboard.press("End")
    pg.keyboard.type(" Acrescentado pelo editor E2E.")
    expect(pg.locator("#editor-oficio [data-salvo]")).to_have_text(
        re.compile(r"^Salvo .* · v1$"), timeout=10000
    )
    # Negrito pela barra marca o estado do botão.
    pg.keyboard.press("Shift+Home")
    pg.click("#editor-oficio [data-comando='bold']")
    expect(pg.locator("#editor-oficio [data-comando='bold']")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(pg.locator("#editor-oficio [data-salvo]")).to_have_text(
        re.compile(r"^Salvo .* · v1$"), timeout=10000
    )
    # Recarregando, o texto editado está na folha e o bloco aparece marcado.
    quadro = _abrir_folha(pg, pk)
    expect(quadro.locator("[data-bloco='saudacao']")).to_contain_text(
        "Acrescentado pelo editor E2E."
    )
    expect(quadro.locator("[data-bloco='saudacao']")).to_have_class(re.compile("bloco--alterado"))
    expect(pg.locator("#editor-oficio [data-salvo]")).to_have_text(re.compile(r"· v1$"))
    # Histórico: a versão em vigor, com o bloco alterado nomeado; "Ver" a versão 0 não existe,
    # mas o modelo pode ser visto com ?versao=0 pelo botão Voltar ao modelo.
    pg.click("#editor-oficio [data-acao='historico']")
    historico = pg.locator("#historico-oficio")
    expect(historico).to_be_visible()
    expect(historico.locator(".editor__versao--vigente")).to_contain_text("Saudação e pedido")
    pg.keyboard.press("Escape")


def test_campo_vivo_grava_no_oficio_e_o_formulario_acompanha(logado: Page, dados_e2e):
    pk = dados_e2e.ids["oficio_rascunho"]
    pg = logado
    quadro = _abrir_folha(pg, pk)
    versao_antes = int(pg.locator("#form-oficio [name='versao']").input_value())
    motivo = quadro.locator("[data-campo='motivo']")
    motivo.click()
    pg.keyboard.press("End")  # fim da linha, ainda dentro do campo
    pg.keyboard.type(" (ajustado na folha)")
    expect(pg.locator("#id_motivo")).to_have_value(
        re.compile(r"\(ajustado na folha\)$"), timeout=10000
    )
    assert int(pg.locator("#form-oficio [name='versao']").input_value()) == versao_antes + 1
    # O texto em volta não virou versão: continua "como o modelo".
    expect(pg.locator("#editor-oficio [data-salvo]")).to_have_text("Como o modelo")
    # Salvar o formulário depois disso não conflita (a versão acompanhou).
    pg.click("#form-oficio button[type=submit]", force=True)
    pg.wait_for_load_state("networkidle")
    expect(pg.locator(".alerta--perigo")).to_have_count(0)


def test_voltar_ao_modelo_e_restaurar(logado: Page, dados_e2e):
    pk = dados_e2e.ids["oficio_rascunho"]
    pg = logado
    quadro = _abrir_folha(pg, pk)
    quadro.locator("[data-bloco='declaracao']").click()
    pg.keyboard.press("End")
    pg.keyboard.type(" Complemento.")
    expect(pg.locator("#editor-oficio [data-salvo]")).to_have_text(
        re.compile(r"· v1$"), timeout=10000
    )
    pg.click("#editor-oficio [data-acao='modelo']")
    pg.click("#dialogo-confirmacao [data-confirmar]")
    expect(pg.locator("#editor-oficio [data-salvo]")).to_have_text("Como o modelo", timeout=10000)
    quadro = pg.frame_locator("#folha-oficio")
    expect(quadro.locator("[data-bloco='declaracao']")).not_to_contain_text("Complemento.")
    pg.click("#editor-oficio [data-acao='historico']")
    pg.click("#historico-oficio [data-versao='1']:not([data-ver])")
    pg.click("#dialogo-confirmacao [data-confirmar]")
    expect(pg.locator("#editor-oficio [data-salvo]")).to_have_text(
        re.compile(r"· v3$"), timeout=10000
    )
    expect(pg.frame_locator("#folha-oficio").locator("[data-bloco='declaracao']")).to_contain_text(
        "Complemento."
    )


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_modo_pdf_e_barra_acessivel(logado: Page, dados_e2e, largura):
    pk = dados_e2e.ids["oficio_rascunho"]
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    _abrir_folha(pg, pk)
    pg.click("#editor-oficio [data-modo='pdf']")
    # O bloco unido usa um PDF com ofício + justificativa (editores.js).
    # O iframe individual continua oculto para não baixar os documentos duas vezes.
    pdf = pg.locator("[data-editores] iframe[data-pdf-bloco]")
    expect(pdf).to_be_visible()
    assert f"/viagens/oficios/{pk}/minuta.pdf?tipo=todos" in (pdf.get_attribute("src") or "")
    expect(pg.locator("#editor-oficio iframe[data-quadro='pdf']")).to_be_hidden()
    expect(pg.locator("#folha-oficio")).to_be_hidden()
    expect(pg.locator("#editor-oficio .editor__linha--ferramentas")).to_be_hidden()
    pg.click("#editor-oficio [data-modo='texto']")
    expect(pg.locator("#folha-oficio")).to_be_visible()
    # A barra inclui a divulgação "Formatar texto", recolhida no mobile.
    # Setas/Home/End percorrem também esse controle, mantendo um único tabstop.
    barra = pg.locator("#editor-oficio [role='toolbar']")
    botoes = barra.locator("button:visible:not([disabled]), summary:visible")
    primeiro = botoes.first
    primeiro.focus()
    pg.keyboard.press("Home")
    expect(primeiro).to_be_focused()
    pg.keyboard.press("ArrowRight")
    expect(botoes.nth(1)).to_be_focused()
    assert barra.evaluate("""el => [...el.querySelectorAll('button, summary')]
        .filter(b => b.getClientRects().length && b.tabIndex === 0).length""") == 1
    pg.keyboard.press("End")
    expect(botoes.last).to_be_focused()
    pg.keyboard.press("ArrowRight")
    expect(primeiro).to_be_focused()
    barra.locator("[data-modo='texto']").focus()
    pg.keyboard.press("ArrowRight")
    assert pg.evaluate("document.activeElement.dataset.modo") == "pdf"
    pg.keyboard.press("ArrowLeft")
    assert pg.evaluate("document.activeElement.dataset.modo") == "texto"
    ferramentas = barra.locator("details[data-ferramentas-recolhiveis]")
    if ferramentas.get_attribute("open") is None:
        ferramentas.locator("summary").press("Enter")
        expect(ferramentas).to_have_attribute("open", "")
    expect(barra.get_by_role("button", name="Negrito (Ctrl+B)")).to_be_visible()
    # O cabeçalho e o rodapé grudados cobrem o que calhar atrás deles: mede do topo, com o
    # rodapé em repouso.
    pg.evaluate("window.scrollTo(0, 0); document.querySelectorAll('.barra-acoes').forEach(b => b.style.position = 'static')")
    violacoes = [v for v in rodar_axe(pg) if v["impact"] in ("serious", "critical")]
    assert not violacoes, [(v["id"], [n["target"] for n in v["nodes"]][:5],
                            [r["target"] for a in v["nodes"][0]["any"]
                             for r in a.get("relatedNodes", [])][:4]) for v in violacoes]
