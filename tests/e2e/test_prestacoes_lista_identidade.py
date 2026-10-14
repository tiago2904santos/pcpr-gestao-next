"""Prestação: filtros e diálogos HTMX, datas, autosave e equipe inteira."""

import re

import pytest
from django.utils import timezone
from playwright.sync_api import expect

from gestao.viagens.models import PrestacaoServidor
from tests.e2e.conftest import entrar
from tests.e2e.test_justificativas_identidade import _axe_estavel

pytestmark = pytest.mark.e2e


def _linhas(c):
    return list(PrestacaoServidor.objects.filter(
        prestacao__oficio_id=c.ids["oficio_emitido"])
        .select_related("servidor", "prestacao__oficio").order_by("servidor__nome"))


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_busca_dialogo_enviar_equipe_completa(logado, dados_e2e, largura):
    a, b = _linhas(dados_e2e)
    PrestacaoServidor.objects.filter(pk=a.pk).update(finalizada_em=timezone.now())
    PrestacaoServidor.objects.filter(pk=b.pk).update(arquivada_em=timezone.now())
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 500})
    pg.goto("/viagens/prestacoes/")
    busca = pg.get_by_role("searchbox", name="Buscar")
    with pg.expect_response(lambda r: r.request.headers.get("hx-request") == "true"):
        busca.fill(a.servidor.nome)
    expect(pg).to_have_url(re.compile("q="))
    expect(busca).to_be_focused()
    expect(pg.locator(".prestacao-servidor")).to_have_count(1)
    expect(pg.locator("#resultados .barra-acoes__status")).to_contain_text("1 servidor")
    expect(pg.get_by_text("Equipe finalizada", exact=True)).to_have_count(0)
    menu = pg.get_by_role("button", name=re.compile("Mais ações da equipe"))
    menu.press("Enter")
    expect(pg.get_by_role("menuitem", name="Desarquivar equipe")).to_be_visible()
    pg.keyboard.press("Escape")
    expect(menu).to_be_focused()
    envio = pg.locator(f"#envio-{a.pk}")
    gatilho = pg.locator(f"#ps-{a.pk}").get_by_role("button", name="Registrar envio", exact=True)
    gatilho.press("Enter")
    expect(envio).to_be_visible()
    _axe_estavel(pg)
    pg.keyboard.press("Escape")
    expect(gatilho).to_be_focused()
    gatilho.click()
    envio.get_by_role("textbox", name="Protocolo do envio").fill("ENVIO-SINTETICO-HTMX")
    with pg.expect_response(lambda r: r.request.method == "POST") as enviado:
        envio.get_by_role("button", name="Registrar envio", exact=True).click()
    assert enviado.value.status == 302
    expect(pg.locator(f"#ps-{a.pk}")).to_contain_text("Enviada em")
    a.refresh_from_db()
    assert a.protocolo_envio == "ENVIO-SINTETICO-HTMX" and a.situacao == "enviada"
    assert pg.locator(".barra-acoes--colecao").evaluate("e=>getComputedStyle(e).position") == "sticky"  # rodapé grudado, como no ofício
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    pg.wait_for_load_state("networkidle")
    _axe_estavel(pg)
    assert pg.erros_console == []


def test_filtros_combinados_exportacao_e_leitura(logado, dados_e2e):
    a, _ = _linhas(dados_e2e)
    PrestacaoServidor.objects.filter(pk=a.pk).update(data_liberacao_diarias=timezone.localdate())
    pg = logado
    pg.goto("/viagens/prestacoes/?aba=liberadas&aba=sem_solicitacao")
    busca = pg.get_by_role("searchbox", name="Buscar")
    with pg.expect_response(lambda r: r.request.headers.get("hx-request") == "true"):
        busca.fill(a.servidor.nome)
    expect(pg).to_have_url(re.compile("q="))
    assert pg.locator('form[role=search] input[name=aba]').evaluate_all(
        "els=>els.map(e=>e.value)") == ["liberadas", "sem_solicitacao"]
    exportar = pg.get_by_role("link", name="Exportar planilha")
    expect(exportar).to_have_attribute("href", re.compile("aba=liberadas&aba=sem_solicitacao&"))
    with pg.expect_download() as download:
        exportar.click()
    assert download.value.suggested_filename.endswith(".xlsx")
    with pg.expect_response(lambda r: r.request.headers.get("hx-request") == "true"):
        busca.fill("SEM-PRESTACAO-ENCONTRADA")
    expect(pg.locator("#resultados .barra-acoes__status")).to_contain_text("0 servidores")
    expect(exportar).to_have_attribute("href", re.compile("q=SEM-PRESTACAO-ENCONTRADA"))
    pg.context.clear_cookies()
    entrar(pg, "consulta")
    pg.goto("/viagens/prestacoes/")
    expect(pg.locator(".prestacao-servidor__campos")).to_have_count(0)
    expect(pg.get_by_role("button", name="Finalizar", exact=True)).to_have_count(0)
    expect(pg.get_by_role("link", name="Diário de bordo")).to_be_visible()
    _axe_estavel(pg)
    assert pg.erros_console == []


@pytest.mark.parametrize("largura", [360, 1440])
def test_calendario_autosave_e_menu(logado, dados_e2e, largura):
    a, _ = _linhas(dados_e2e)
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 500})
    pg.goto("/viagens/prestacoes/")
    cartao = pg.locator(f"#ps-{a.pk}")
    cartao.get_by_label("Nº da solicitação", exact=True).fill("NUMERO-SALVO-VISUAL")
    expect(cartao.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    a.refresh_from_db()
    assert a.numero_solicitacao == "NUMERO-SALVO-VISUAL" and not a.finalizada
    calendario = cartao.get_by_role("button", name="Escolher data: Liberação das diárias")
    calendario.press("Enter")
    expect(pg.get_by_role("dialog")).to_be_visible()
    pg.keyboard.press("Escape")
    expect(calendario).to_be_focused()
    menu = cartao.get_by_role("button", name=re.compile("Mais ações de"))
    menu.press("Enter")
    expect(pg.get_by_role("menuitem", name="Arquivar (sai das abas de trabalho)")).to_be_focused()
    pg.keyboard.press("Escape")
    expect(menu).to_be_focused()
    _axe_estavel(pg)
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert pg.erros_console == []
