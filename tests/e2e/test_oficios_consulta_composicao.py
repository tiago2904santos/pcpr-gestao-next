"""Conteúdos extremos em Resumo/Lista sem comprometer foco, fluxo ou geometria."""

from copy import copy
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.db.models.functions import Length
from playwright.sync_api import expect

from gestao.cadastros.models import ConfiguracaoInstitucional, Municipio, Servidor
from gestao.viagens.models import Oficio, Trecho, Viajante

from .conftest import rodar_axe

pytestmark = [pytest.mark.e2e, pytest.mark.visual, pytest.mark.a11y]


@pytest.mark.parametrize("largura,quantidade,longo", [
    (360, 1, False), (1440, 1, False), (360, 2, True),
    (1440, 2, True), (360, 6, True), (1440, 6, True),
])
def test_coluna_de_leitura_independe_da_conferencia(logado, dados_e2e, largura, quantidade, longo):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    oficio = Oficio.objects.get(pk=dados_e2e.ids["oficio_rascunho"])
    motivo = ("Visita institucional para conferência de equipamentos e apoio às equipes. "
              * 15 if longo else "Vistoria institucional.")
    Oficio.objects.filter(pk=oficio.pk).update(motivo=motivo)
    base = oficio.trechos.first()
    assert base is not None
    cidades_longas = list(Municipio.objects.annotate(tamanho=Length("nome")).order_by(
        "-tamanho", "codigo_ibge"
    )[:5])
    pontos = ([base.origem, base.destino] if quantidade == 1 else
              [base.origem, *cidades_longas[:quantidade - 1], base.origem])
    icone = "car"
    if quantidade > 1:
        meio = Oficio.MeioTransporte.AEREO if quantidade == 2 else Oficio.MeioTransporte.ONIBUS_LINHA
        Oficio.objects.filter(pk=oficio.pk).update(
            tipo_transporte=Oficio.TipoTransporte.OUTRO, viatura=None,
            transporte_meio=meio, transporte_descricao="Deslocamento sintético de teste",
        )
        icone = "plane" if quantidade == 2 else "bus"
    # Apenas a fixture sintética: tempos válidos, com chegada no dia seguinte.
    oficio.trechos.all().delete()
    for i in range(quantidade):
        saida = base.saida_em + timedelta(days=i * 2)
        Trecho.objects.create(
            oficio=oficio, ordem=i, origem=pontos[i], destino=pontos[i + 1],
            saida_em=saida, chegada_em=saida + timedelta(hours=26),
            tempo_viagem_min=1560,
        )
    if quantidade == 6:
        usados = oficio.viajantes.values_list("servidor_id", flat=True)
        for i, servidor in enumerate(Servidor.objects.filter(unidade=oficio.unidade).exclude(
            pk__in=usados
        )):
            Viajante.objects.create(oficio=oficio, servidor=servidor, ordem=i + 1)
        ConfiguracaoInstitucional.objects.filter(unidade=oficio.unidade).update(
            chefia_nome="", destinatario_nome="",
        )
    pg.goto(f"/viagens/oficios/?resumo={oficio.pk}")
    janela = pg.locator("#dialogo-resumo")
    expect(janela).to_be_visible()
    expect(janela.locator(".percurso-registro__trecho")).to_have_count(quantidade)
    assert janela.locator(".percurso-registro__fio use").evaluate_all(
        "(els,icone)=>els.every(e=>e.getAttribute('href').endsWith('#i-'+icone))", icone,
    )
    assert janela.locator(".equipe-transporte__transporte use").evaluate(
        "(e,icone)=>e.getAttribute('href').endsWith('#i-'+icone)", icone,
    )
    if quantidade > 1:
        expect(janela.locator(".percurso-registro")).to_contain_text(cidades_longas[0].nome)
    # O motivo mora no cartão Registro institucional; o roteiro abre a coluna de leitura.
    expect(janela.locator(".missao-registro")).to_have_count(0)
    expect(janela.locator("#resumo-roteiro")).to_be_visible()
    assert janela.evaluate("e => e.scrollWidth <= e.clientWidth + 1")
    assert not rodar_axe(pg)
    janela.locator(".percurso-registro__trecho").last.scroll_into_view_if_needed()
    expect(janela.locator("#resumo-rodape")).to_be_in_viewport()
    pasta = Path("artifacts/oficios-consulta-composicao")
    pasta.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(pasta / f"resumo-{largura}-{quantidade}-trechos.png"))
    pg.keyboard.press("Escape")
    expect(janela).not_to_be_visible()
    assert pg.erros_console == []


@pytest.mark.parametrize("largura", [360, 1440])
def test_lista_poucos_muitos_numeros_e_paginacao(logado, dados_e2e, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    base = Oficio.objects.get(pk=dados_e2e.ids["oficio_rascunho"])
    grupo = "Grupo sintético de composição"
    novos = []
    for i in range(40):
        oficio = copy(base)
        oficio.pk = None
        oficio.ano = 2028
        oficio.numero = [1, 3, 165, 1250][i] if i < 4 else 1300 + i
        oficio.motivo = f"{grupo} {i}"
        oficio.diarias_total = Decimal("0")
        novos.append(oficio)
    Oficio.objects.bulk_create(novos)
    pasta = Path("artifacts/oficios-consulta-composicao")
    pasta.mkdir(parents=True, exist_ok=True)
    for quantidade in [0, 1, 3, 20, 40]:
        Oficio.objects.filter(ano=2028).update(motivo="Fora do recorte sintético")
        Oficio.objects.filter(pk__in=[o.pk for o in novos[:quantidade]]).update(motivo=grupo)
        pg.goto(f"/viagens/oficios/?q={grupo}")
        expect(pg.locator(".registro-operacional")).to_have_count(min(quantidade, 20))
        assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth")
        violacoes = rodar_axe(pg)
        assert not violacoes, [(v["id"], [n["target"] for n in v["nodes"]][:4]) for v in violacoes]
        for linha in pg.locator(".registro-operacional").all():
            placa = linha.locator(".placa").bounding_box()
            acao = linha.locator("[data-menu-botao]").bounding_box()
            assert placa and acao
            assert abs(placa["y"] + placa["height"] / 2 - acao["y"] - acao["height"] / 2) <= 2
            assert linha.locator(".placa").evaluate("e => e.scrollWidth <= e.clientWidth + 1")
        pg.screenshot(path=str(pasta / f"lista-{largura}-{quantidade}-registros.png"), full_page=True)
        if quantidade == 40:
            pg.get_by_role("link", name="Próxima página", exact=True).click()
            expect(pg.locator(".paginacao")).to_contain_text("21–40 de 40")
    assert pg.erros_console == []
