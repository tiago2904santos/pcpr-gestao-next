"""Folha/lote reais: autosave, versão, equipe, rascunhos e navegação por teclado."""

import re
from datetime import timedelta

import pytest
from django.utils import timezone
from playwright.sync_api import expect

from gestao.cadastros.models import Municipio, Servidor, TipoViagem, Viatura
from gestao.viagens import viagem
from gestao.viagens.models import Oficio, Viagem
from tests.e2e.conftest import entrar
from tests.e2e.test_justificativas_identidade import _axe_estavel

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
@pytest.mark.parametrize("estado", ["consulta", "cancelada"])
def test_leitura_preserva_dados_e_hierarquia(pagina, dados_e2e, largura, estado, tmp_path):
    v = _viagem(dados_e2e)
    titulo = "Atendimento institucional e apoio às comunidades em diferentes municípios"
    Viagem.objects.filter(pk=v.pk).update(titulo=titulo, motivo="Motivo da viagem para leitura integral.")
    if estado == "cancelada":
        viagem.cancelar(dados_e2e.usuarios["operador"], v.pk, "Cenário sintético de leitura.")
    pg = pagina
    pg.set_viewport_size({"width": largura, "height": 700})
    entrar(pg, "consulta" if estado == "consulta" else "operador")
    pg.goto(f"/viagens/viagens/{v.pk}/")
    expect(pg.locator("#form-viagem")).to_have_count(0)
    dados = pg.locator("#dados")
    expect(dados.locator("dt")).to_have_text(["Tipo", "Período", "Destinos"])
    expect(dados.locator("dd").nth(0)).to_have_text(titulo)
    expect(dados.locator("dd").nth(1)).to_contain_text(v.data_inicio.strftime("%d/%m/%Y"))
    expect(dados.locator("dd").nth(2)).to_contain_text("Londrina/PR")
    expect(dados).to_contain_text("Motivo da viagem para leitura integral.")
    assert dados.locator("dt").first.evaluate("e=>getComputedStyle(e).color") != dados.locator("dd").first.evaluate("e=>getComputedStyle(e).color")
    assert dados.locator("dd").evaluate_all("es=>es.every(e=>e.scrollWidth<=e.clientWidth)")
    _axe_estavel(pg)
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")
    dados.screenshot(path=str(tmp_path / f"viagens-leitura-{estado}-{largura}.png"))
    assert pg.erros_console == []


def _viagem(c):
    op = c.usuarios["operador"]
    tipo = TipoViagem.objects.create(nome="Unidade Móvel")
    v = viagem.criar(op)
    return viagem.salvar_dados(op, v.pk, tipos=[tipo],
                              data_inicio=timezone.localdate() + timedelta(days=8),
                              destinos=[Municipio.objects.get(nome="Londrina", uf="PR")])


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_autosave_regioes_menu_e_conflito(logado, dados_e2e, largura):
    v = _viagem(dados_e2e)
    segundo = TipoViagem.objects.create(nome="PCPR na Comunidade")
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 500})
    pg.goto(f"/viagens/viagens/{v.pk}/")
    expect(pg.locator(".itin--operacional")).to_be_visible()
    pg.locator("#tipos-gatilho").press("Enter")
    pg.get_by_role("checkbox", name=segundo.nome, exact=True).check()
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    expect(pg.locator(".registro-hero h1")).to_contain_text(segundo.nome)
    expect(pg.locator("#frase-viagem")).to_contain_text(segundo.nome)
    pg.keyboard.press("Escape")
    pg.get_by_role("textbox", name="Motivo", exact=True).fill("Motivo sintético persistido.")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    v.refresh_from_db()
    assert v.motivo == "Motivo sintético persistido."
    assert pg.locator(".barra-acoes").evaluate("e=>getComputedStyle(e).position") == "static"
    menu = pg.get_by_role("button", name="Mais ações da viagem (cabeçalho)")
    menu.focus()
    menu.press("Enter")
    expect(pg.get_by_role("menuitem", name="Gerar documentos", exact=True)).to_be_focused()
    pg.keyboard.press("Escape")
    expect(menu).to_be_focused()
    _axe_estavel(pg)
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    viagem.salvar_dados(dados_e2e.usuarios["operador"], v.pk, tipos=list(v.tipos.all()),
                       motivo="Outra janela gravou.")
    pg.get_by_role("textbox", name="Motivo", exact=True).fill("Texto desta janela.")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Outra pessoa alterou")
    v.refresh_from_db()
    assert v.motivo == "Outra janela gravou."
    expect(pg.get_by_role("textbox", name="Motivo", exact=True)).to_have_value("Texto desta janela.")
    assert pg.erros_console == []


def _selecionar_pessoa(pg, nome_campo, servidor):
    campo = pg.locator(f'pc-multiescolha[data-nome="{nome_campo}"]')
    campo.locator("input[role=combobox]").fill(servidor.nome)
    pg.get_by_role("option", name=re.compile(re.escape(servidor.nome))).first.click()
    expect(campo.locator(f'input[type=hidden][value="{servidor.pk}"]')).to_have_count(1)


@pytest.mark.parametrize("largura", [360, 1440])
def test_lote_erro_adicionar_remover_preserva_e_gera_rascunho(logado, dados_e2e, largura, tmp_path):
    v = _viagem(dados_e2e)
    motorista, servidor = list(Servidor.objects.filter(ativo=True).order_by("pk")[:2])
    viatura = Viatura.objects.filter(ativo=True).first()
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 700})
    pg.goto(f"/viagens/viagens/{v.pk}/gerar-documentos/")
    expect(pg.locator(".registro-hero")).not_to_contain_text(".html")
    with pg.expect_response(lambda r: r.request.method == "POST") as erro:
        pg.get_by_role("button", name="Gerar documentos", exact=True).click()
    assert erro.value.status == 422
    expect(pg.get_by_role("alert")).to_contain_text("Monte ao menos um ofício")
    assert not Oficio.objects.filter(viagem=v).exists()
    _selecionar_pessoa(pg, "equipe_0", servidor)
    _selecionar_pessoa(pg, "motorista_0", motorista)
    transporte = pg.locator("#oficio-1 pc-transporte")
    transporte.get_by_role("combobox").fill(viatura.placa)
    pg.get_by_role("option", name=re.compile(re.escape(viatura.placa_formatada))).first.click()
    expect(transporte.locator("[data-viatura-cartao]")).to_be_visible()
    pg.get_by_role("button", name="Adicionar ofício", exact=True).click()
    expect(pg.locator("#oficio-2")).to_be_visible()
    assert not Oficio.objects.filter(viagem=v).exists()
    expect(pg.locator('input[type=hidden][name="equipe_0"]')).to_have_value(str(servidor.pk))
    expect(pg.locator('select[name="viatura_0"]')).to_have_value(str(viatura.pk))
    pg.get_by_role("button", name="Remover este ofício", exact=True).click()
    expect(pg.locator("#oficio-2")).to_have_count(0)
    expect(pg.locator('input[type=hidden][name="motorista_0"]')).to_have_value(str(motorista.pk))
    _axe_estavel(pg)
    assert pg.locator(".barra-acoes").evaluate("e=>getComputedStyle(e).position") == "static"
    pg.screenshot(path=str(tmp_path / f"viagens-lote-preenchido-{largura}.png"), full_page=True)
    for nome in ["termos", "ordem", "plano"]:
        pg.locator(f'input[name="{nome}"]').uncheck()
    with pg.expect_response(lambda r: r.request.method == "POST") as gerado:
        pg.get_by_role("button", name="Gerar documentos", exact=True).click()
    assert gerado.value.status == 302
    expect(pg.locator("#documentos")).to_contain_text("Ofício")
    pg.wait_for_load_state("networkidle")
    oficio = Oficio.objects.get(viagem=v)
    assert oficio.situacao == Oficio.Situacao.RASCUNHO
    assert set(oficio.viajantes.values_list("servidor_id", flat=True)) == {servidor.pk, motorista.pk}
    assert oficio.viatura_id == viatura.pk
    assert Viagem.objects.get(pk=v.pk).situacao == Viagem.Situacao.GERADOS
    assert pg.erros_console == ["Failed to load resource: the server responded with a status of 422 (Unprocessable Content)"]
    pg.goto("/viagens/viagens/")
    pg.wait_for_load_state("networkidle")
