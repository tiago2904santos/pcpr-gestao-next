"""Refinamento do hub: ordem real, vínculos filtráveis e etapas preservadas."""

from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.viagens import viagem
from gestao.viagens.models import Oficio
from tests.e2e.test_justificativas_identidade import _axe_estavel
from tests.e2e.test_viagens_folha_identidade import _viagem

pytestmark = pytest.mark.e2e
EVIDENCIAS = Path("docs/visual-agents/evidencias/viagens-refino-20261015/navegador")


@pytest.mark.parametrize("largura", [360, 1440])
def test_documentos_antes_dos_vinculos_e_busca_sem_gravacao(logado, dados_e2e, largura):
    pg = logado
    v = _viagem(dados_e2e)
    oficio = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])
    viagem.salvar_dados(dados_e2e.usuarios["operador"], v.pk, tipos=list(v.tipos.all()),
                       vinculos={"oficios": [oficio]})
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.goto(f"/viagens/viagens/{v.pk}/")
    expect(pg.locator("#documentos")).to_have_count(1)
    assert pg.locator("#documentos").evaluate("""e =>
        Boolean(e.compareDocumentPosition(document.querySelector('#vinculos'))
            & Node.DOCUMENT_POSITION_FOLLOWING)""")
    assert pg.locator("#documentos").evaluate("e => e.closest('form').id") == "form-viagem"
    for botao in pg.locator("#documentos button[form]").all():
        assert botao.evaluate("e => e.form.id") == botao.get_attribute("form")
        assert botao.get_attribute("form").startswith("novo-")
    expect(pg.locator(".viagem-trilha > .viagem-passo")).to_have_count(5)
    etapas = pg.locator(".viagem-etapas > li").count() + pg.locator(".viagem-concluida").count()
    assert etapas == 8
    expect(pg.locator(".viagem-vinculos")).not_to_have_attribute("open", "")
    # Os componentes da folha carregam sob demanda: abrir as caixas só com a página parada,
    # para o clique não cair no resumo vizinho se o layout ainda se mexer.
    pg.wait_for_load_state("networkidle")
    pg.locator(".viagem-vinculos > summary").press("Enter")
    expect(pg.locator(".viagem-vinculos")).to_have_js_property("open", True)
    grupo = pg.locator('.viagem-vinculo').filter(has=pg.locator('input[name="oficios"]'))
    grupo.locator("summary").click()
    expect(grupo).to_have_js_property("open", True)
    busca = pg.locator("#buscar-vinculo-oficios")
    selecionado = grupo.locator(f'input[name="oficios"][value="{oficio.pk}"]')
    expect(selecionado).to_be_checked()
    posts = []
    pg.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)
    url = pg.url
    estado = pg.locator("[data-status-salvamento]").inner_text()
    busca.fill("documento-inexistente-do-refino")
    busca.press("Enter")
    expect(grupo.locator(".caixas__item:visible")).to_have_count(0)
    expect(grupo.locator("[data-sem-resultado]")).to_be_visible()
    expect(selecionado).to_be_checked()
    busca.press("Tab")
    pg.wait_for_timeout(1800)
    expect(pg).to_have_url(url)
    expect(pg.locator("[data-status-salvamento]")).to_have_text(estado)
    assert posts == [], "Filtrar documentos não deve salvar ou navegar"
    busca.fill("")
    expect(selecionado).to_be_visible()
    expect(selecionado).to_be_checked()
    # A lista mostra no máximo três linhas e rola; o texto fica no centro da caixa.
    caixas = grupo.locator(".caixas")
    linha = grupo.locator(".caixas__item").first.bounding_box()["height"]
    assert caixas.bounding_box()["height"] <= 3 * linha + 3 * 8 + 2
    # Com mais de três linhas de opções, o resto fica rolando dentro da lista.
    assert caixas.evaluate("""e => {
        const colunas = getComputedStyle(e).gridTemplateColumns.split(" ").length;
        const linhas = Math.ceil(e.querySelectorAll(".caixas__item").length / colunas);
        return linhas > 3 ? e.scrollHeight > e.clientHeight : e.scrollHeight <= e.clientHeight + 1;
    }""")
    item = grupo.locator(".caixas__item").first
    caixa, texto = item.locator("input").bounding_box(), item.locator("span").bounding_box()
    assert abs((caixa["y"] + caixa["height"] / 2) - (texto["y"] + texto["height"] / 2)) <= 2
    _axe_estavel(pg)
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    pg.locator("#vinculos").screenshot(path=str(EVIDENCIAS / f"vinculos-{largura}.png"))
    assert pg.erros_console == []


@pytest.mark.parametrize("largura", [360, 1440])
def test_conferencia_atalhos_e_leitura_sem_descricao(pagina, dados_e2e, largura):
    from tests.e2e.conftest import entrar

    pg = pagina
    v = _viagem(dados_e2e)
    v.descricao = "Descrição antiga que não aparece mais."
    v.save(update_fields=["descricao"])
    entrar(pg, "consulta")
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.goto(f"/viagens/viagens/{v.pk}/")
    expect(pg.locator("#form-viagem")).to_have_count(0)
    expect(pg.locator("#dados")).not_to_contain_text(v.descricao)
    etapas = pg.locator(".viagem-etapas > li").count() + pg.locator(".viagem-concluida").count()
    assert etapas == 8
    expect(pg.locator("#documentos button[form]")).to_have_count(0)
    expect(pg.locator(".viagem-conferencia__barra")).to_be_visible()
    if pg.locator(".viagem-etapa__itens a").count():
        destino = pg.locator(".viagem-etapa__itens a").first.get_attribute("href")
        assert destino and "#" in destino
    _axe_estavel(pg)
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert pg.erros_console == []


def test_enter_na_busca_compartilhada_tambem_preserva_plano(logado, dados_e2e):
    from gestao.viagens.tests.test_planos import _completo

    pg = logado
    plano = _completo(dados_e2e)
    pg.goto(f"/viagens/planos/{plano.pk}/")
    posts = []
    pg.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)
    url = pg.url
    estado = pg.locator("[data-status-salvamento]").inner_text()
    busca = pg.locator("#atividades [data-filtro]")
    busca.fill("inexistente-regressao-do-filtro")
    busca.press("Enter")
    busca.press("Tab")
    expect(pg.locator("#atividades [data-sem-resultado]")).to_be_visible()
    pg.wait_for_timeout(1800)
    expect(pg).to_have_url(url)
    expect(pg.locator("[data-status-salvamento]")).to_have_text(estado)
    assert posts == []
    assert pg.erros_console == []
