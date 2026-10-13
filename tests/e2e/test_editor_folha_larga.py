"""Linhas oficiais indivisíveis continuam legíveis dentro da folha no celular."""

import pytest
from playwright.sync_api import expect

from gestao.viagens import termos
from gestao.viagens.models import Oficio

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 390, 768, 1440])
def test_termo_generico_alcanca_linha_inteira_sem_alterar_documento(logado, dados_e2e, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    oficio = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])
    termo = termos.salvar(dados_e2e.usuarios["operador"], oficio=oficio)
    pg.goto(f"/viagens/termos/{termo.pk}/")
    pg.locator("#previa").scroll_into_view_if_needed()
    pg.locator(".editor--ativo .editor__barra").wait_for(state="visible")
    botao = pg.locator('[data-ir-pagina="generico"]')
    if not botao.is_visible():
        pg.locator("[data-alternar-indice]:visible").click()
    botao.click()
    iframe = pg.locator('[data-pagina="generico"] iframe[data-quadro="texto"]')
    quadro = pg.frame_locator('[data-pagina="generico"] iframe[data-quadro="texto"]')
    expect(quadro.locator(".branco--nome")).to_be_visible()
    iframe.evaluate("async q => { await q.contentDocument.fonts.ready; }")
    html_antes = quadro.locator("main").inner_html()
    medidas = iframe.evaluate("""q => {
        const d=q.contentDocument, r=d.documentElement;
        const editor=q.closest('pc-editor-documento');
        editor.ajustarAltura();
        const antes=q.getBoundingClientRect().height;
        for(let i=0;i<20;i++)editor.ajustarAltura();
        const papel=d.body.getBoundingClientRect();
        return {antes, depois:q.getBoundingClientRect().height,
          conteudo:r.scrollWidth, largura:r.clientWidth,
          dentro:[...d.querySelectorAll('.par')].every(p => p.getBoundingClientRect().right <= papel.right + 1)};
    }""")
    assert medidas["antes"] == medidas["depois"]
    assert medidas["dentro"], "Linha oficial escapou do fundo da folha"
    if largura < 400:
        assert medidas["conteudo"] > medidas["largura"]
        # Um clique no timbre dá foco ao iframe; setas deslocam a folha sem editar.
        quadro.locator("header.timbre").click()
        pg.keyboard.press("ArrowRight")
        pg.wait_for_function("q => q.contentDocument.documentElement.scrollLeft > 0", arg=iframe.element_handle())
        iframe.evaluate("q => q.contentWindow.scrollTo({left:q.contentDocument.documentElement.scrollWidth})")
        assert iframe.evaluate("q => q.contentDocument.documentElement.scrollLeft > 0")
    assert quadro.locator("main").inner_html() == html_antes
    if largura == 360:
        # A apresentação acompanha uma edição real, inclusive ao remover texto.
        declaracao = quadro.locator('[data-bloco="declaracao"]')
        original = declaracao.inner_text()
        altura = iframe.evaluate("q => q.getBoundingClientRect().height")
        declaracao.fill("Texto sintético para conferir a altura da folha. " * 150)
        pg.wait_for_function("p => p.q.getBoundingClientRect().height > p.altura + 100", arg={"q": iframe.element_handle(), "altura": altura})
        declaracao.fill(original)
        pg.wait_for_function("p => Math.abs(p.q.getBoundingClientRect().height - p.altura) <= 2", arg={"q": iframe.element_handle(), "altura": altura})
        quadro.locator(".rodape").scroll_into_view_if_needed()
        expect(quadro.locator(".rodape")).to_be_in_viewport()
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert pg.erros_console == []
