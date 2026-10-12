"""Hierarquia financeira real nas três folhas que compartilham a conferência."""

import pytest
from playwright.sync_api import expect

from gestao.viagens.tests.test_planos import _completo
from tests.e2e.test_justificativas_identidade import _axe_estavel

pytestmark = pytest.mark.e2e


def _controle_visivel(pg, campo):
    expect(campo).to_be_focused()
    pg.wait_for_function("""e => {
        const r = e.getBoundingClientRect(), topo = document.querySelector('.topo');
        const limite = topo ? Math.max(0, topo.getBoundingClientRect().bottom) : 0;
        return r.top >= limite && r.bottom <= innerHeight && r.height >= 24 &&
            e.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
    }""", arg=campo.element_handle())


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_diarias_legiveis_sem_colunas_artificiais(logado, dados_e2e, largura):
    plano = _completo(dados_e2e)
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 700})
    rotas = [
        f"/viagens/roteiros/{dados_e2e.ids['roteiro']}/editar/",
        f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/editar/",
        f"/viagens/planos/{plano.pk}/",
    ]
    for rota in rotas:
        pg.goto(rota)
        pg.wait_for_load_state("networkidle")
        pg.evaluate("document.fonts.ready")
        _axe_estavel(pg)
        painel = pg.locator("#diarias .conferencia-serena")
        expect(painel).to_contain_text("R$")
        expect(painel.locator("dt")).to_have_text([
            "Por servidor", "Tipo de destino", "Quantidade por servidor"])
        dados = painel.locator("dl > div")
        # Uma leitura atômica evita comparar caixas de instantes diferentes
        # enquanto a rota e as fontes terminam de compor a página.
        caixas = dados.evaluate_all("els => els.map(e => e.getBoundingClientRect().toJSON())")
        assert len(caixas) == 3
        # Valor individual e destino podem ser comparados na mesma linha.
        assert abs(caixas[0]["y"] - caixas[1]["y"]) < 1
        assert caixas[1]["x"] > caixas[0]["x"] + caixas[0]["width"]
        if largura < 1024:
            # Composição extensa ocupa uma linha útil, sem colunas vazias ao lado.
            assert caixas[2]["y"] >= caixas[0]["y"] + caixas[0]["height"]
            assert abs(caixas[2]["x"] - caixas[0]["x"]) < 1
            assert caixas[2]["width"] > caixas[0]["width"] + caixas[1]["width"]
        else:
            assert abs(caixas[2]["y"] - caixas[0]["y"]) < 1
        assert painel.evaluate("""e => [...e.querySelectorAll('dt,dd,strong')].every(d =>
            d.scrollWidth <= d.clientWidth + 1 &&
            d.getBoundingClientRect().right <= e.getBoundingClientRect().right + 1)""")
        assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
        painel.scroll_into_view_if_needed()
        # A rolagem suave nativa não consta em document.getAnimations(). O índice
        # acompanha as seções via IntersectionObserver; medir no meio do scroll
        # mistura o contraste da transição e controles cruzando o topo fixo.
        pg.evaluate("""async () => {
            let anterior = scrollY, estavel = performance.now();
            const limite = estavel + 5000;
            while (performance.now() - estavel < 200) {
                await new Promise(requestAnimationFrame);
                if (scrollY !== anterior) { anterior = scrollY; estavel = performance.now(); }
                if (performance.now() > limite) throw new Error('Rolagem não estabilizou');
            }
        }""")
        # Auditoria da região visível, mantendo a auditoria global acima. Campos
        # anteriores podem cruzar o limite do viewport sob o cabeçalho sticky;
        # sua acessibilidade ao receber foco é verificada separadamente abaixo.
        violacoes = pg.evaluate("""async () => (await axe.run('#diarias', {
            runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']},
            resultTypes: ['violations']
        })).violations""")
        assert violacoes == [], str(violacoes)
        for campo in pg.locator('input[name^="destino-"][name*="saida_"]').all():
            campo.focus()
            _controle_visivel(pg, campo)
            botao = campo.locator('..').locator('.seletor__botao')
            campo.press("Tab")
            _controle_visivel(pg, botao)
            botao.press("Shift+Tab")
            _controle_visivel(pg, campo)
        pg.wait_for_load_state("networkidle")
    assert pg.erros_console == []
