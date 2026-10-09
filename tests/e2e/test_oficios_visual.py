"""Padrões compartilhados em Lista, Folha e Documentos de Ofícios."""

import json
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from .conftest import rodar_axe

pytestmark = [pytest.mark.e2e, pytest.mark.visual, pytest.mark.a11y]


def _avaliar(pg, nome, largura):
    pg.wait_for_function(
        "() => document.getAnimations().every(a => a.playState !== 'running' "
        "|| a.effect.getTiming().iterations === Infinity)"
    )
    assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth")
    violacoes = rodar_axe(pg)
    pasta = Path("artifacts/oficios-premium")
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"axe-{nome}-{largura}.json").write_text(
        json.dumps(violacoes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    pg.screenshot(path=str(pasta / f"{nome}-{largura}.png"))
    assert not violacoes
    assert pg.erros_console == []


@pytest.mark.parametrize("largura", [360, 390, 768, 1024, 1440])
def test_lista_folha_documentos_coerentes_e_operaveis(logado, dados_e2e, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.goto("/viagens/oficios/")
    _avaliar(pg, "lista", largura)
    # Período e protocolo precisam continuar legíveis na nova composição mobile.
    # Ausência de overflow da página não detecta duas informações sobrepostas.
    for linha in pg.locator(".registro-operacional").all():
        for selo in linha.locator(".registro__selos .selo").all():
            assert selo.evaluate("e => e.scrollWidth <= e.clientWidth + 1"), "O texto do selo precisa caber inteiro."
            assert selo.evaluate("e => e.clientHeight <= parseFloat(getComputedStyle(e).lineHeight) + 6"), "Selo não pode virar duas linhas."
        placa = linha.locator(".placa").bounding_box()
        acao = linha.locator("[data-menu-botao]").bounding_box()
        assert placa and acao
        assert abs((placa["y"] + placa["height"] / 2) - (acao["y"] + acao["height"] / 2)) <= 2, "Identidade e ação devem compartilhar o eixo vertical."
        periodo = linha.locator(".registro__meta-item--periodo").bounding_box()
        protocolo = linha.locator(".registro__meta-item--protocolo").bounding_box()
        assert periodo and protocolo
        assert (
            periodo["y"] + periodo["height"] <= protocolo["y"] + 1
            or protocolo["y"] + protocolo["height"] <= periodo["y"] + 1
            or periodo["x"] + periodo["width"] <= protocolo["x"] + 1
            or protocolo["x"] + protocolo["width"] <= periodo["x"] + 1
        ), "Período e protocolo não podem ocupar a mesma área."
    if largura >= 1024:
        assert pg.locator(".registro-operacional .registro__meta-item--diarias .registro__meta-texto").evaluate_all(
            "els => els.every(e => e.scrollHeight <= e.clientHeight + 1)"
        ), "Valor e composição das diárias devem aparecer inteiros, sem recorte vertical."
    else:
        expect(pg.locator(".registro-operacional .registro__meta-item--protocolo").first).to_be_visible()
    botao = pg.locator(".registro__acoes [data-menu-botao]").first
    botao.press("Enter")
    expect(pg.locator(".menu__painel:popover-open")).to_be_visible()
    pg.keyboard.press("Escape")
    expect(botao).to_be_focused()

    pk = dados_e2e.ids["oficio_rascunho"]
    pg.goto(f"/viagens/oficios/{pk}/editar/")
    expect(pg.locator(".campos--legiveis")).to_be_visible()
    assert pg.locator(".campos--legiveis .campo__rotulo").evaluate_all(
        "els => els.every(e => !e.getClientRects().length "
        "|| e.scrollWidth <= e.clientWidth + 1)"
    ), "Os rótulos da identificação devem caber sem cortes."
    _avaliar(pg, "folha", largura)
    recursos = pg.locator("[data-indice-preparacao] a[href='#recursos']")
    recursos.press("Enter")
    expect(recursos).to_have_attribute("aria-current", "location")
    if largura >= 768:
        meio = pg.locator(".transporte > .campo").first.bounding_box()
        viatura = pg.locator(".transporte > .so-viatura").bounding_box()
        assert meio and viatura and abs(meio["y"] - viatura["y"]) <= 1, "Meio e viatura devem ocupar a mesma linha."
    pg.locator("#roteiro").scroll_into_view_if_needed()
    assert pg.locator(".itin__uf .entrada").evaluate_all("""els => els.every(e => {
      if (!e.getClientRects().length) return true;
      const s = getComputedStyle(e), c = document.createElement('canvas').getContext('2d');
      c.font = s.font;
      return c.measureText(e.value).width <= e.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight) + 1;
    })"""), "UF deve mostrar as duas letras sem reticências."
    assert pg.locator(".documento--preparacao").evaluate("""el => {
      const barra = document.querySelector('.barra-acoes--documental').getBoundingClientRect();
      return [...el.querySelectorAll('input, button, select, textarea')].every(campo => {
        const caixa = campo.getBoundingClientRect();
        return !caixa.width || !caixa.height || caixa.bottom <= barra.top
          || caixa.top >= barra.bottom || caixa.right <= barra.left || caixa.left >= barra.right;
      });
    }"""), "A barra de fechamento não pode encobrir controles do formulário."
    campo = pg.locator("#id_protocolo")
    campo.focus()
    expect(campo).to_be_focused()
    caixa = campo.bounding_box()
    assert caixa and caixa["y"] >= 0 and caixa["y"] + caixa["height"] < 900

    # O bloco pode conter duas folhas. A barra acompanha a folha no centro
    # da tela; selecionar o bloco inteiro não garante que a primeira esteja ativa.
    pg.locator("#editor-oficio .editor__folha").scroll_into_view_if_needed()
    pg.frame_locator("#folha-oficio").locator("[data-regiao='corpo']").wait_for()
    barra = pg.locator(".editor--ativo .editor__barra")
    expect(barra).to_be_visible()
    paginas = barra.locator("[data-alternar-indice]")
    aberto = paginas.get_attribute("aria-expanded") == "true"
    paginas.click()
    expect(paginas).to_have_attribute("aria-expanded", str(not aberto).lower())
    if aberto:
        expect(pg.locator("#indice-oficio")).to_be_hidden()
    else:
        expect(pg.locator("#indice-oficio")).to_be_visible()
    paginas.click()
    expect(paginas).to_have_attribute("aria-expanded", str(aberto).lower())

    ferramentas = barra.locator("details[data-ferramentas-recolhiveis]")
    resumo = ferramentas.locator("summary")
    expect(ferramentas).to_have_js_property("open", largura >= 768)
    resumo.press("Enter")
    expect(ferramentas).to_have_js_property("open", largura < 768)
    if largura < 768:
        expect(ferramentas.locator("[data-comando='bold']")).to_be_visible()
    resumo.press("Enter")
    expect(ferramentas).to_have_js_property("open", largura >= 768)

    # Avaliar a seção desde o título, e não uma posição arbitrária que corta
    # um controle anterior sob a navegação fixa. Nenhuma regra axe é excluída.
    pg.locator("#t-emissao").evaluate("el => el.scrollIntoView({block: 'start'})")
    _avaliar(pg, "documentos", largura)
    expect(barra.locator("[tabindex='0']")).to_have_count(1)
    resumo.press("Home")
    expect(barra.locator("[data-alternar-indice]")).to_be_focused()
    pg.keyboard.press("End")
    assert pg.evaluate(
        "() => document.activeElement.getClientRects().length > 0 "
        "&& !document.activeElement.closest('details:not([open]) :not(summary)')"
    )

    if pg.locator("#editor-justificativa").count():
        if paginas.get_attribute("aria-expanded") == "false":
            paginas.click()
        pg.locator("[data-ir-pagina='justificativa']").click()
        expect(pg.locator("#editor-justificativa")).to_have_class(
            re.compile(r"editor--ativo")
        )
        expect(barra.locator("[tabindex='0']")).to_have_count(1)
