"""Lista do agrupador Viagem: filtros, contexto HTMX e permissões reais."""

import re
from datetime import timedelta

import pytest
from django.utils import timezone
from playwright.sync_api import expect

from gestao.cadastros.models import TipoViagem
from gestao.viagens import viagem
from gestao.viagens.models import Oficio, Viagem
from tests.e2e.conftest import entrar
from tests.e2e.test_justificativas_identidade import _axe_estavel

pytestmark = pytest.mark.e2e


def _preparar(c):
    op = c.usuarios["operador"]
    tipo = TipoViagem.objects.create(nome="Ação institucional de atendimento e apoio à comunidade")
    v = viagem.criar(op)
    v = viagem.salvar_dados(op, v.pk, tipos=[tipo], data_inicio=timezone.localdate() + timedelta(days=5),
                           data_fim=timezone.localdate() + timedelta(days=8),
                           vinculos={"oficios": [Oficio.objects.get(pk=c.ids["oficio_emitido"])]})
    vazia = viagem.criar(op)
    return v, vazia


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_busca_atualiza_contadores_barra_e_preserva_foco(logado, dados_e2e, largura):
    v, vazia = _preparar(dados_e2e)
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 500})
    pg.goto("/viagens/viagens/")
    expect(pg.locator(".registro-operacional")).to_have_count(2)
    expect(pg.locator(".identidade-documental")).to_contain_text(["#" + str(vazia.pk), v.data_inicio.strftime("%d/%m")])
    expect(pg.locator("#resultados .barra-acoes__status")).to_contain_text("2 viagens")
    busca = pg.get_by_role("searchbox", name="Buscar")
    with pg.expect_response(lambda r: "/viagens/viagens/?" in r.url and r.request.headers.get("hx-request") == "true") as resposta:
        busca.fill("Ação institucional")
    assert resposta.value.status == 200
    expect(pg).to_have_url(re.compile("q="))
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    expect(pg.locator("#resultados .barra-acoes__status")).to_contain_text("1 viagem no filtro")
    expect(pg.locator("#abas-filtro a[aria-current] .aba__contagem")).to_have_text("1")
    expect(busca).to_be_focused()
    expect(pg.locator(".registro-operacional__recursos")).to_contain_text("1 ofício")
    assert pg.locator(".barra-acoes--colecao").evaluate("e => getComputedStyle(e).position") == "static"
    _axe_estavel(pg)
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    with pg.expect_response(lambda r: "/viagens/viagens/?" in r.url and r.request.headers.get("hx-request") == "true"):
        busca.fill("Busca inexistente")
    expect(pg.get_by_role("heading", name="Nenhuma viagem encontrada")).to_be_visible()
    expect(pg.locator("#resultados .barra-acoes__status")).to_contain_text("0 viagens")
    expect(pg.locator("#abas-filtro a[aria-current] .aba__contagem")).to_have_text("0")
    pg.get_by_role("link", name="Limpar filtros").click()
    expect(pg.locator(".registro-operacional")).to_have_count(2)
    pg.locator(".registro__link", has_text=v.titulo).press("Enter")
    expect(pg.locator("#frase-viagem")).to_contain_text(v.titulo)
    assert pg.erros_console == []


def test_paginacao_filtro_canceladas_e_consulta(logado, dados_e2e, monkeypatch):
    from gestao.viagens import views_viagem

    monkeypatch.setattr(views_viagem, "POR_PAGINA", 1)
    v, vazia = _preparar(dados_e2e)
    viagem.salvar_dados(dados_e2e.usuarios["operador"], vazia.pk,
                       tipos=list(v.tipos.all()))
    pg = logado
    pg.goto("/viagens/viagens/?aba=futuras&q=A%C3%A7%C3%A3o")
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    pg.get_by_role("link", name="Próxima página", exact=True).click()
    expect(pg).to_have_url(re.compile("pagina=2"))
    expect(pg.get_by_role("searchbox", name="Buscar")).to_have_value("Ação")
    expect(pg.locator("#abas-filtro a[aria-current]")).to_contain_text("Que vão acontecer")
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    _axe_estavel(pg)
    # O Ofício emitido vinculado só pode ser cancelado pelo gestor; preservar a regra.
    viagem.cancelar(dados_e2e.usuarios["gestor"], v.pk, "Cenário sintético de cancelamento.")
    pg.goto("/viagens/viagens/?aba=canceladas")
    expect(pg.locator(".registro__selos")).to_contain_text("Cancelada")
    pg.context.clear_cookies()
    entrar(pg, "consulta")
    pg.goto("/viagens/viagens/?aba=canceladas")
    expect(pg.get_by_role("button", name="Nova viagem")).to_have_count(0)
    pg.locator(".registro__link").press("Enter")
    expect(pg.locator("#form-viagem")).to_have_count(0)
    assert Viagem.objects.get(pk=v.pk).cancelada
    assert pg.erros_console == []


def test_vinte_registros_barra_e_ultima_pagina(logado, dados_e2e, tmp_path):
    unidade = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"]).unidade
    Viagem.objects.bulk_create([
        Viagem(unidade=unidade, criado_por=dados_e2e.usuarios["operador"],
               titulo=f"Atendimento institucional com nome extenso — registro {i}",
               data_inicio=timezone.localdate() + timedelta(days=5)) for i in range(21)
    ])
    pg = logado
    pg.set_viewport_size({"width": 390, "height": 500})
    pg.goto("/viagens/viagens/?q=Atendimento")
    expect(pg.locator(".registro-operacional")).to_have_count(20)
    expect(pg.locator(".barra-acoes--acompanha")).to_have_count(1)
    ultimo = pg.locator(".registro__link").last
    ultimo.focus()
    expect(ultimo).to_be_in_viewport()
    retangulo = ultimo.bounding_box()
    barra = pg.locator(".barra-acoes--colecao").bounding_box()
    assert retangulo["y"] + retangulo["height"] <= barra["y"]
    _axe_estavel(pg)
    pg.screenshot(path=str(tmp_path / "vinte-viagens-mobile.png"), full_page=True)
    pg.get_by_role("link", name="Próxima página", exact=True).click()
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    expect(pg.locator(".barra-acoes__status")).to_contain_text("21 viagens")
    _axe_estavel(pg)
    assert pg.erros_console == []


@pytest.mark.parametrize("largura", [360, 1440])
def test_consulta_paginada_mantem_contagem_sem_barra_sobreposta(pagina, dados_e2e, largura, tmp_path):
    unidade = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"]).unidade
    Viagem.objects.bulk_create([
        Viagem(unidade=unidade, criado_por=dados_e2e.usuarios["operador"],
               titulo=f"Consulta da viagem institucional {i}") for i in range(21)
    ])
    pg = pagina
    pg.set_viewport_size({"width": largura, "height": 500})
    entrar(pg, "consulta")
    pg.goto("/viagens/viagens/?q=Consulta")
    expect(pg.locator(".registro-operacional")).to_have_count(20)
    expect(pg.get_by_role("button", name="Nova viagem")).to_have_count(0)
    barra = pg.locator(".barra-acoes--colecao")
    barra.scroll_into_view_if_needed()
    _axe_estavel(pg)
    pg.screenshot(path=str(tmp_path / f"consulta-paginada-{largura}.png"), full_page=True)
    expect(barra.get_by_role("status")).to_be_visible()
    expect(barra.get_by_role("status")).to_contain_text("21 viagens")
    assert barra.evaluate("e => getComputedStyle(e).position") == "static"
    pg.get_by_role("link", name="Próxima página", exact=True).click()
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    expect(pg.get_by_role("searchbox", name="Buscar")).to_have_value("Consulta")
    assert pg.erros_console == []
