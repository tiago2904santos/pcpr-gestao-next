"""Composição responsiva e sugestões do diário, sem tocar no editor aprovado."""

import pytest
from playwright.sync_api import expect

from gestao.viagens import diario, prestacao
from gestao.viagens.models import DiarioBordo, PrestacaoContas
from tests.e2e.conftest import ARTEFATOS, entrar, estabilizar
from tests.e2e.test_justificativas_identidade import _axe_estavel as validar_acessibilidade

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 1440])
def test_diario_refinado_sem_tabela_e_acessivel(logado, dados_e2e, largura):
    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 1000})
    pg.goto(f"/viagens/prestacoes/equipe/{p.pk}/diario/")
    estabilizar(pg)
    expect(pg.locator("#tabela-trechos")).to_have_attribute("aria-label", "Trechos do diário")
    expect(pg.locator("#trechos table")).to_have_count(0)
    expect(pg.locator("#realizada")).to_have_count(1)
    expect(pg.locator("#form-diario label")).to_have_count(6)
    expect(pg.locator(".documento--preparacao > .secao")).to_have_count(3)
    expect(pg.locator(".documento--cartoes")).to_have_count(0)
    expect(pg.locator(".documento > .secao > .secao__cabecalho .secao__numero")).to_have_text(["1", "2", "3"])
    expect(pg.locator("#motorista form")).to_be_visible()
    expect(pg.locator("#previa [data-editores]")).to_have_count(1)
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    # O editor é carregado ao entrar na área visível; não capturar a moldura vazia.
    pg.locator("#previa").scroll_into_view_if_needed()
    expect(pg.locator("#folha-diario")).to_be_visible(timeout=30_000)
    expect(pg.frame_locator("#folha-diario").locator("body")).to_contain_text("Ficha individual do veículo")
    pg.get_by_role("heading", level=1).scroll_into_view_if_needed()
    estabilizar(pg)
    validar_acessibilidade(pg)
    destino = ARTEFATOS / "diario-base-oficio"
    destino.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(destino / f"diario-{largura}.png"), full_page=True)
    expect(pg.get_by_role("button", name="Ajustar horários")).to_be_visible()
    validar_acessibilidade(pg)


@pytest.mark.parametrize("distancia", [None, 400])
def test_sugestao_em_linhas_preserva_hodometro_digitado(logado, dados_e2e, distancia):
    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    p.oficio.trechos.update(distancia_km=distancia)
    pg = logado
    pg.goto(f"/viagens/prestacoes/equipe/{p.pk}/diario/")
    d = DiarioBordo.objects.get(prestacao=p)
    a, b = d.linhas.order_by("ordem")
    botao = pg.get_by_role("button", name="Preencher pelas distâncias")
    # Sem o hodômetro inicial, não inventa zero nem preenche o trecho.
    botao.click()
    inicial = pg.locator(f"#l-{a.pk}-km_inicial")
    expect(inicial).to_be_focused()
    expect(pg.locator(f"#l-{a.pk}-km_final")).to_have_value("")
    inicial.fill("0")
    pg.locator(f"#l-{a.pk}-km_final").fill("450")
    botao.click()
    expect(inicial).to_have_value("0")
    expect(pg.locator(f"#l-{a.pk}-km_final")).to_have_value("450")
    expect(pg.locator(f"#l-{b.pk}-km_inicial")).to_have_value("450")
    prevista = int(pg.locator(f"#linha-{b.pk}").get_attribute("data-prevista"))
    expect(pg.locator(f"#l-{b.pk}-km_final")).to_have_value(str(450 + prevista) if prevista else "")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    b.refresh_from_db()
    assert b.km_inicial == 450
    assert b.km_final == (450 + prevista if prevista else None)
    if prevista:
        expect(pg.locator("#estado-documento-diario")).to_contain_text("Pronto para imprimir")
    assert pg.erros_console == []


@pytest.mark.parametrize("estado", ["consulta", "finalizada"])
def test_diario_somente_leitura_preserva_documento(pagina, dados_e2e, estado):
    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    diario.obter(p)
    if estado == "finalizada":
        for ps in prestacao.ativos().filter(prestacao=p):
            prestacao.finalizar(dados_e2e.usuarios["operador"], ps.pk, "Cenário de teste.")
    pg = pagina
    pg.set_viewport_size({"width": 360, "height": 800})
    entrar(pg, "consulta" if estado == "consulta" else "operador")
    pg.goto(f"/viagens/prestacoes/equipe/{p.pk}/diario/")
    estabilizar(pg)
    expect(pg.locator("#form-diario")).to_have_count(0)
    expect(pg.locator("#motorista")).to_have_count(0)
    expect(pg.locator("#trechos input, #trechos select")).to_have_count(0)
    expect(pg.locator("#previa [data-editores]")).to_have_count(1)
    if estado == "finalizada":
        expect(pg.get_by_text("Prestação finalizada — reabra para editar.", exact=False)).to_be_visible()
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    validar_acessibilidade(pg)
