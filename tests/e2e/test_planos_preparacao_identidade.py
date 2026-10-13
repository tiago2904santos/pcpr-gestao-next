"""Preparação de Planos: quantitativos, calendário, evento e geração reais."""

from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.viagens import planos
from gestao.viagens.tests.test_planos import _completo
from tests.e2e.conftest import rodar_axe

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_preparacao_quantidade_calendario_e_conferencia(logado, dados_e2e, largura):
    pg = logado
    plano = _completo(dados_e2e)
    pg.set_viewport_size({"width": largura, "height": 700})
    pg.goto(f"/viagens/planos/{plano.pk}/")
    expect(pg.get_by_role("heading", level=1)).to_contain_text(str(plano))
    expect(pg.locator(".registro-hero .identidade-documental__complemento")).to_have_text(
        plano.sufixo)
    expect(pg.locator("#conferencia")).to_contain_text("dá para gerar o plano")
    escolhas_coordenacao = pg.locator('.campos--coordenacao pc-select .seletor__valor:visible')
    expect(escolhas_coordenacao.first).to_be_visible()
    assert escolhas_coordenacao.evaluate_all(
        "els => els.every(e => e.scrollWidth <= e.clientWidth)"
    ), "A origem e o tratamento da coordenação devem ser legíveis sem truncamento"
    assert pg.get_by_role("button", name="Programa", exact=True).bounding_box()["width"] > 200
    quantidade = pg.locator("#efetivo-quantidade-1")
    # Área de toque válida e três dígitos (limite 999) legíveis, sem limiar arbitrário.
    assert quantidade.bounding_box()["width"] >= 24
    assert quantidade.evaluate("""e => {
        const s = getComputedStyle(e), c = document.createElement('canvas').getContext('2d');
        c.font = s.font;
        return c.measureText('999').width <= e.clientWidth - parseFloat(s.paddingLeft)
            - parseFloat(s.paddingRight);
    }""")
    quantidade.fill("3")
    pg.locator("#efetivo-linhas").get_by_role("button", name="Aumentar a quantidade").click()
    expect(quantidade).to_have_value("4")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    plano.refresh_from_db()
    assert plano.efetivo.get().quantidade == 4
    calendario = pg.locator("pc-data[data-periodo] .seletor__botao")
    calendario.focus()
    calendario.press("Enter")
    expect(calendario).to_have_attribute("aria-expanded", "true")
    pg.keyboard.press("Escape")
    expect(calendario).to_be_focused()
    expect(pg.locator("#diarias .conferencia-serena--operacional")).to_contain_text("R$")
    assert pg.locator(".barra-acoes").evaluate("e => getComputedStyle(e).position") == "static"
    pg.evaluate("scrollTo(0,0)")
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert rodar_axe(pg) == []
    pasta = Path("artifacts/planos-preparacao-identidade")
    pasta.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(pasta / f"preparacao-{largura}.png"), full_page=True)
    assert pg.erros_console == []


def test_evento_manual_diarias_menu_remocao_e_pdf(logado, dados_e2e):
    pg = logado
    plano = _completo(dados_e2e)
    valor_principal = plano.diarias_total
    pg.goto(f"/viagens/planos/{plano.pk}/")
    pg.get_by_role("link", name="Acrescentar evento").click()
    janela = pg.get_by_role("dialog", name="Novo evento", exact=True)
    expect(janela).to_be_visible()
    assert janela.locator("form").evaluate("e => !e.closest('#form-plano')")
    janela.get_by_role("button", name="Programa", exact=True).click()
    janela.get_by_role("checkbox", name="Outro", exact=True).check()
    janela.get_by_role("button", name="Programa", exact=True).click()
    janela.get_by_label("Outro programa", exact=True).fill("Feira institucional sintética")
    janela.locator("#evento-periodo").fill("28/06/2030")
    janela.locator("#evento-periodo").press("Tab")
    janela.get_by_role("combobox", name="Destino 1", exact=True).fill("Maringá")
    janela.get_by_role("option", name="Maringá/PR", exact=True).click()
    cargo = janela.get_by_role("combobox", name="Cargo", exact=True)
    cargo.fill("Agente de Polícia")
    janela.get_by_role("option", name="Agente de Polícia Judiciária", exact=True).click()
    janela.locator("#evento-efetivo-quantidade-1").fill("2")
    for campo, valor in {"evento_saida_em_0": "28/06/2030", "evento_saida_em_1": "06:00",
                         "evento_chegada_em_0": "28/06/2030", "evento_chegada_em_1": "21:00"}.items():
        janela.locator(f"#{campo}").fill(valor)
    janela.get_by_role("button", name="Acrescentar evento", exact=True).click()
    expect(pg.locator("#eventos .registro-operacional")).to_have_count(1)
    plano.refresh_from_db()
    evento = plano.eventos.get()
    assert evento.diarias_total is not None
    registro = pg.locator("#eventos .registro__link")
    expect(registro).to_have_attribute("title", "Maringá/PR")
    expect(registro).to_have_accessible_name("Editar o evento 2 · Maringá/PR")
    registro.click()
    edicao = pg.get_by_role("dialog", name="Editar evento", exact=True)
    expect(edicao).to_be_visible()
    edicao.get_by_label("Outro programa", exact=True).fill("")
    with pg.expect_response(lambda r: r.request.method == "POST"
                            and r.url.endswith("/eventos/salvar/")) as invalido:
        edicao.get_by_role("button", name="Salvar evento", exact=True).click()
    assert invalido.value.status == 422
    expect(pg.get_by_role("dialog", name="Editar evento", exact=True)).to_be_visible()
    expect(pg.get_by_role("dialog", name="Editar evento", exact=True).locator(".campo__erro").first).to_be_visible()
    evento.refresh_from_db()
    assert str(evento.data_inicio) == "2030-06-28"
    pg.get_by_role("dialog", name="Editar evento", exact=True).get_by_role("link", name="Cancelar", exact=True).click()
    assert plano.diarias_total == valor_principal
    assert planos.diarias_geral(plano) == valor_principal + evento.diarias_total
    assert planos.efetivo_geral(plano) == 8
    pg.locator("#eventos").get_by_role("button", name="Ações do evento 2").press("Enter")
    expect(pg.get_by_role("menuitem", name="Editar evento", exact=True)).to_be_focused()
    pg.keyboard.press("Escape")
    expect(pg.get_by_role("button", name="Ações do evento 2")).to_be_focused()
    with pg.expect_response(lambda r: r.request.method == "POST"
                            and r.url.endswith("/finalizar/")) as finalizacao:
        pg.locator("#conferencia").get_by_role("button", name="Finalizar e gerar o plano").click()
    assert finalizacao.value.status == 302
    plano.refresh_from_db()
    assert plano.gerado
    resposta = pg.request.get(f"/viagens/planos/{plano.pk}/documento.pdf")
    assert resposta.ok and resposta.body().startswith(b"%PDF")
    pg.goto(f"/viagens/planos/{plano.pk}/")
    pg.get_by_role("button", name="Ações do evento 2").click()
    pg.get_by_role("menuitem", name="Remover evento", exact=True).click()
    pg.get_by_role("dialog", name="Remover evento?", exact=True).get_by_role(
        "button", name="Remover evento", exact=True).click()
    expect(pg.locator("#eventos .registro-operacional")).to_have_count(0)
    assert not plano.eventos.exists()
    pg.goto("/viagens/planos/")
    pg.wait_for_load_state("networkidle")
    # HTTP 422 é deliberado neste cenário; nenhuma falha de JS ou outro recurso.
    assert pg.erros_console == [
        "Failed to load resource: the server responded with a status of 422 (Unprocessable Content)",
    ]
