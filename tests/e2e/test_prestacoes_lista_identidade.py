"""Prestação: a lista (uma linha por equipe, busca e filtros HTMX) e a folha da equipe
(cartões com datas e autosave, diálogos de envio, navegação entre as folhas)."""

import os
import re
from pathlib import Path

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
    expect(pg.locator("#resultados .registro-operacional")).to_have_count(1)
    expect(pg.locator("#resultados .barra-acoes__status")).to_contain_text("1 servidor")
    expect(pg.get_by_text("Equipe finalizada", exact=True)).to_have_count(0)
    expect(pg.locator("#resultados")).to_contain_text("1 de 2 finalizadas")
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    _axe_estavel(pg)
    # A linha leva à folha da equipe: as ações da equipe e os cartões moram lá.
    pg.locator(f"#equipe-{a.prestacao_id} .registro__link").click()
    expect(pg.get_by_role("heading", name="Servidores")).to_be_visible()
    menu = pg.get_by_role("button", name=re.compile("^Mais ações da equipe")).first
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
    assert pg.locator(".barra-acoes--registro").evaluate("e=>getComputedStyle(e).position") == "sticky"  # rodapé grudado, como na viagem
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
    expect(pg.locator('[id^="form-ps-"] input[name="numero"]')).to_have_count(0)
    expect(pg.get_by_role("button", name="Finalizar", exact=True)).to_have_count(0)
    expect(pg.locator(f"#equipe-{a.prestacao_id} .registro__link")).to_be_visible()
    _axe_estavel(pg)
    # Consulta: a folha da equipe sem campos nem ações de edição.
    pg.locator(f"#equipe-{a.prestacao_id} .registro__link").click()
    expect(pg.locator('[id^="form-ps-"] input[name="numero"]')).to_have_count(0)
    expect(pg.locator("form[data-autosave]")).to_have_count(0)
    expect(pg.get_by_role("button", name="Finalizar equipe")).to_have_count(0)
    _axe_estavel(pg)
    assert pg.erros_console == []


@pytest.mark.parametrize("largura", [360, 1440])
def test_calendario_autosave_e_menu(logado, dados_e2e, largura):
    a, _ = _linhas(dados_e2e)
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 500})
    pg.goto(f"/viagens/prestacoes/equipe/{a.prestacao_id}/")
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


@pytest.mark.parametrize("largura", [360, 1440])
def test_resumo_existente_e_navegacao_da_equipe(logado, dados_e2e, largura):
    from gestao.viagens.models import DiarioBordo, RelatorioTecnico

    a, _ = _linhas(dados_e2e)
    p = a.prestacao
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 800})
    pg.goto("/viagens/prestacoes/")
    equipe = pg.locator(f"#equipe-{p.pk}")
    menu = equipe.get_by_role("button", name=re.compile("^Ações da prestação"))
    antes = list(PrestacaoServidor.objects.order_by("pk").values())
    menu.click()
    equipe.get_by_role("menuitem", name="Resumo do ofício").click()
    dialogo = pg.locator("#dialogo-resumo")
    expect(dialogo).to_be_visible()
    expect(dialogo.locator(".registro-hero")).to_contain_text(p.oficio.numero_formatado)
    _axe_estavel(pg)
    if os.environ.get("MIGRACAO_CAPTURAS"):
        destino = Path(os.environ["MIGRACAO_CAPTURAS"])
        destino.mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(destino / f"prestacao-resumo-{largura}.png"))
    pg.keyboard.press("Escape")
    expect(dialogo).to_be_hidden()
    assert list(PrestacaoServidor.objects.order_by("pk").values()) == antes

    equipe.locator(".registro__link").click()
    nav = pg.get_by_role("navigation", name="Páginas da prestação")
    expect(nav.locator('[aria-current="page"]')).to_have_text("Equipe")
    _axe_estavel(pg)
    if os.environ.get("MIGRACAO_CAPTURAS"):
        pg.screenshot(path=str(destino / f"prestacao-equipe-{largura}.png"), full_page=True)
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")
    # Abrir a folha da equipe não grava nada.
    assert list(PrestacaoServidor.objects.order_by("pk").values()) == antes
    nav.get_by_role("link", name="Diário de bordo", exact=True).click()
    expect(nav.locator('[aria-current="page"]')).to_have_text("Diário de bordo")
    assert pg.locator(".documento > section").first.get_attribute("id") == "trechos"
    d = DiarioBordo.objects.get(prestacao=p)
    linha = d.linhas.order_by("ordem").first()
    pg.locator(f"#l-{linha.pk}-km_inicial").fill("10000")
    pg.locator(f"#l-{linha.pk}-km_final").fill("10440")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    nav.get_by_role("link", name="Relatório técnico", exact=True).click()
    expect(nav.locator('[aria-current="page"]')).to_have_text("Relatório técnico")
    pg.get_by_label("Objetivo da participação").fill("Relato integrado da equipe.")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    nav.get_by_role("link", name="Documentos", exact=True).click()
    expect(nav.locator('[aria-current="page"]')).to_have_text("Documentos")
    expect(pg.locator("#despacho input[type=file]")).to_be_visible()
    expect(pg.locator(f"#ps-{a.pk}")).to_contain_text(a.servidor.nome)
    _axe_estavel(pg)
    if os.environ.get("MIGRACAO_CAPTURAS"):
        pg.locator(f"#ps-{a.pk}").screenshot(
            path=str(destino / f"prestacao-documentos-servidor-{largura}.png"))
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")
    nav.get_by_role("link", name="Equipe", exact=True).click()
    expect(pg.locator(f"#ps-{a.pk}")).to_be_visible()
    linha.refresh_from_db()
    assert linha.km_final == 10440
    assert RelatorioTecnico.objects.get(prestacao=p).atividade == "Relato integrado da equipe."
    assert pg.erros_console == []


def test_folhas_recompostas_em_consulta(logado, dados_e2e):
    a, _ = _linhas(dados_e2e)
    pg = logado
    pg.context.clear_cookies()
    entrar(pg, "consulta")
    for folha in ("diario", "relatorio", "documentos"):
        pg.goto(f"/viagens/prestacoes/equipe/{a.prestacao_id}/{folha}/")
        expect(pg.get_by_role("navigation", name="Páginas da prestação")).to_be_visible()
        expect(pg.get_by_role("heading", level=1)).to_have_count(1)
        expect(pg.locator('form[data-autosave], input[type=file]')).to_have_count(0)
        expect(pg.get_by_role("button", name="Finalizar", exact=True)).to_have_count(0)
        _axe_estavel(pg)
    assert pg.erros_console == []
