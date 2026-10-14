"""Resultados manuais: edição, validação, leitura e geometria responsiva reais."""

import pytest
from playwright.sync_api import expect

from gestao.cadastros.models import AtividadePlano
from gestao.viagens import planos, resultados
from gestao.viagens.tests.test_planos import _completo
from tests.e2e.conftest import estabilizar, rodar_axe

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_lancamento_zero_milhar_limpeza_e_teclado(logado, dados_e2e, largura):
    pg = logado
    plano = _completo(dados_e2e)
    cin = AtividadePlano.objects.get(codigo="CIN")
    url = f"/viagens/planos/{plano.pk}/resultados/"
    pg.set_viewport_size({"width": largura, "height": 500})
    pg.goto(url)
    quantidade = pg.locator(f"#realizado_{cin.pk}")
    observacao = pg.locator(f"#observacao_{cin.pk}")
    expect(quantidade).to_have_accessible_name(f"Realizado — {cin.nome}")
    if largura < 1024:
        estabilizar(pg)
        rotulo = pg.locator(f'label[for="realizado_{cin.pk}"]')
        # Rótulo acima do campo; tolera o arredondamento de subpixel (medido: 0,12px).
        assert (rotulo.bounding_box()["y"] + rotulo.bounding_box()["height"]
                <= quantidade.bounding_box()["y"] + 0.5)
    expect(observacao).to_have_attribute("maxlength", "500")
    quantidade.fill("0")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Alterações não salvas")
    assert not plano.resultados.exists()  # Não há autosave nesta página.
    with pg.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/resultados/")) as salvo:
        quantidade.press("Control+s")
    assert salvo.value.status == 302
    expect(quantidade).to_have_value("0")
    assert plano.resultados.get(atividade=cin).realizado == 0
    expect(pg.locator("#relatorio")).to_contain_text(f"{cin.nome}: 0")
    quantidade.fill("1.234")
    observacao.fill("RGs emitidos")
    with pg.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/resultados/")) as salvo:
        pg.get_by_role("button", name="Salvar resultados").click()
    assert salvo.value.status == 302
    expect(pg.locator("#relatorio")).to_contain_text("1234 (RGs emitidos)")
    assert plano.resultados.get(atividade=cin).realizado == 1234
    assert pg.locator(".barra-acoes").evaluate("e => getComputedStyle(e).position") == "sticky"  # rodapé grudado, como no ofício
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    pg.evaluate("scrollTo(0,0)")
    pg.evaluate("""async () => await Promise.all(document.getAnimations().filter(a =>
        a.effect.getComputedTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})))""")
    violacoes = rodar_axe(pg)
    assert violacoes == [], violacoes
    quantidade.fill("")
    observacao.fill("")
    with pg.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/resultados/")) as salvo:
        pg.get_by_role("button", name="Salvar resultados").click()
    assert salvo.value.status == 302
    expect(quantidade).to_have_value("")
    assert not plano.resultados.exists()
    assert pg.erros_console == []
    pg.goto("/viagens/planos/")
    pg.wait_for_load_state("networkidle")


def test_erro_preserva_digitado_sem_gravacao_parcial(logado, dados_e2e):
    pg = logado
    plano = _completo(dados_e2e)
    cin = AtividadePlano.objects.get(codigo="CIN")
    movel = AtividadePlano.objects.get(codigo="UNIDADE_MOVEL")
    pg.goto(f"/viagens/planos/{plano.pk}/resultados/")
    pg.locator(f"#realizado_{cin.pk}").fill("doze")
    pg.locator(f"#realizado_{movel.pk}").fill("7")
    with pg.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/resultados/")) as invalido:
        pg.get_by_role("button", name="Salvar resultados").click()
    assert invalido.value.status == 422
    expect(pg.locator("#erros-resultados")).to_contain_text("não é um número inteiro")
    expect(pg.locator(f"#realizado_{cin.pk}")).to_have_value("doze")
    expect(pg.locator(f"#realizado_{movel.pk}")).to_have_value("7")
    assert not plano.resultados.exists()
    assert pg.erros_console == ["Failed to load resource: the server responded with a status of 422 (Unprocessable Content)"]
    pg.on("dialog", lambda d: d.accept())
    pg.goto("/viagens/planos/")
    pg.wait_for_load_state("networkidle")


def test_resultado_fora_do_plano_cancelado_consulta_sem_scroll(logado, dados_e2e):
    pg = logado
    plano = _completo(dados_e2e)
    cin = AtividadePlano.objects.get(codigo="CIN")
    resultados.salvar(dados_e2e.usuarios["operador"], plano.pk, {cin.pk: ("10", "Anterior")})
    plano.atividades.remove(cin)
    planos.cancelar(dados_e2e.usuarios["operador"], plano.pk, "Teste sintético")
    pg.set_viewport_size({"width": 768, "height": 500})
    pg.goto(f"/viagens/planos/{plano.pk}/resultados/")
    expect(pg.get_by_role("row", name="Confecção da Carteira", exact=False)).to_contain_text("fora do plano")
    expect(pg.locator(f"#realizado_{cin.pk}")).to_be_disabled()
    expect(pg.get_by_role("button", name="Salvar resultados")).to_have_count(0)
    expect(pg.locator("#relatorio")).to_contain_text("10 (Anterior)")
    assert not pg.locator(".tabela-rolagem").evaluate("e => e.scrollWidth > e.clientWidth")
    pg.evaluate("""async () => await Promise.all(document.getAnimations().filter(a =>
        a.effect.getComputedTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})))""")
    violacoes = rodar_axe(pg)
    assert violacoes == [], violacoes
    assert pg.erros_console == []
    pg.goto("/viagens/planos/")
    pg.wait_for_load_state("networkidle")
