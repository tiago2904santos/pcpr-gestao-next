"""E2E: itinerário 2.0 (ADR 0016) — rota e resumo, chegada calculada, UF que filtra os
municípios, arrastar e soltar (mouse e teclado), calendário único das saídas e sede editável.
Nos testes o provedor de rotas é a estimativa offline e o mapa não baixa mosaicos."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from playwright.sync_api import expect

from gestao.viagens.models import Roteiro

pytestmark = pytest.mark.e2e


def _cidade(pg, indice: int, texto: str, escolha: str) -> None:
    campo = pg.locator(f"input[name='destino-{indice}-cidade']")
    campo.fill(texto)
    pg.get_by_role("option", name=escolha, exact=True).click()


def _ordem(pg) -> list[str]:
    return [c.input_value() for c in pg.locator("[data-parada]:visible input[name$='-cidade']")
            .all()]


def test_rota_preenche_tempos_e_chegada_e_a_ordem_muda_arrastando(logado):
    pg = logado
    pg.goto("/viagens/roteiros/novo/")
    _cidade(pg, 0, "Ponta Gr", "Ponta Grossa/PR")
    pg.get_by_role("button", name="Adicionar destino").click()
    expect(pg.locator("input[name='destino-1-cidade']")).to_be_focused()
    _cidade(pg, 1, "Londri", "Londrina/PR")

    # Rota: km por trecho, tempos sugeridos e resumo; o mapa aparece (sem mosaicos no teste).
    expect(pg.locator("[data-total-km]")).to_contain_text("km")
    expect(pg.locator("#id_destino-0-tempo_viagem")).to_have_value(re.compile(r"^\d{2}:\d{2}$"))
    expect(pg.locator(".itin__trecho-km").first).to_contain_text("km")
    expect(pg.locator(".itin__mapa.leaflet-container")).to_be_visible()
    expect(pg.locator(".itin-pino")).to_have_count(3)

    # Chegada ao vivo: saída + tempo de viagem + adicional.
    pg.locator("#id_destino-0-saida_0").fill("10/11/2030")
    pg.locator("#id_destino-0-saida_1").fill("08:00")
    pg.locator("#id_destino-0-tempo_viagem").fill("02:00")
    pg.locator("#id_destino-0-tempo_adicional").fill("00:30")
    expect(pg.locator("[data-chegada]").first).to_have_text("10/11/2030 10:30")

    # Arrastar o 2º destino para cima: a ordem muda, as datas ficam na posição.
    pg.locator("#id_destino-1-saida_0").fill("11/11/2030")
    pg.locator("#id_destino-1-saida_1").fill("09:00")
    alca = pg.locator("[data-parada]:visible").nth(1).locator("[data-alca]")
    alca.scroll_into_view_if_needed()
    caixa = alca.bounding_box()
    alvo = pg.locator("[data-parada]:visible").first.bounding_box()
    pg.mouse.move(caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] / 2)
    pg.mouse.down()
    pg.mouse.move(caixa["x"] + 6, alvo["y"] + 12, steps=12)
    pg.mouse.up()
    assert _ordem(pg) == ["Londrina/PR", "Ponta Grossa/PR"]
    expect(pg.locator(".itin__trecho").first.locator("input[name$='-saida_0']")) \
        .to_have_value("10/11/2030")
    expect(pg.locator(".itin__trecho-rota").first).to_contain_text("Curitiba/PR")
    expect(pg.locator(".itin__trecho-rota").first).to_contain_text("Londrina/PR")

    # Teclado: setas na alça também reordenam.
    pg.locator("[data-parada]:visible").first.locator("[data-alca]").focus()
    pg.keyboard.press("ArrowDown")
    assert _ordem(pg) == ["Ponta Grossa/PR", "Londrina/PR"]
    expect(pg.locator("pc-itinerario > p[aria-live='polite']")).to_contain_text("posição 2")
    assert pg.erros_console == []  # type: ignore[attr-defined]


def test_uf_filtra_municipios_e_troca_de_uf_limpa_a_cidade(logado):
    pg = logado
    pg.goto("/viagens/roteiros/novo/")
    _cidade(pg, 0, "Ponta Gr", "Ponta Grossa/PR")
    parada = pg.locator("[data-parada]:visible").first
    parada.get_by_role("combobox", name="UF").click()
    pg.get_by_role("option", name="SC", exact=True).click()
    expect(pg.locator("input[name='destino-0-cidade']")).to_have_value("")
    pg.locator("input[name='destino-0-cidade']").fill("Join")
    expect(pg.get_by_role("option", name="Joinville/SC")).to_be_visible()
    pg.locator("input[name='destino-0-cidade']").fill("Ponta Gr")
    expect(pg.get_by_role("option", name="Ponta Grossa/PR")).to_have_count(0)


def test_calendario_unico_preenche_as_saidas_de_todos_os_trechos(logado):
    pg = logado
    pg.goto("/viagens/roteiros/novo/")
    _cidade(pg, 0, "Ponta Gr", "Ponta Grossa/PR")
    pg.get_by_label("Quantidade de servidores").fill("2")
    botao = pg.get_by_role("button", name="Preencher datas de saída")
    botao.click()
    painel = pg.get_by_role("dialog", name="Datas de saída dos trechos")
    expect(painel).to_be_visible()
    expect(painel.locator(".itin__chip")).to_have_count(2)  # ida + volta
    painel.locator("[data-mes='1']").click()
    dias = painel.locator("td[data-dia]:not(.calendario__fora)")
    dias.nth(9).click()   # ida no dia 10
    dias.nth(11).click()  # volta no dia 12 (o próximo trecho fica selecionado sozinho)
    expect(painel.locator(".itin__marca-dia")).to_have_count(2)
    pg.keyboard.press("Escape")
    expect(painel).to_be_hidden()
    expect(botao).to_be_focused()
    ida = pg.locator("#id_destino-0-saida_0").input_value()
    volta = pg.locator("#id_retorno-saida_0").input_value()
    assert ida.startswith("10/") and volta.startswith("12/")
    expect(pg.locator("#id_destino-0-saida_1")).to_have_value("08:00")
    expect(pg.locator("[data-volta]")).to_contain_text(volta)
    pg.get_by_role("button", name="Salvar roteiro").click()
    expect(pg.locator(".toast")).to_contain_text("cadastrado")
    roteiro = Roteiro.objects.latest("pk")
    for trecho in roteiro.trechos.order_by("ordem"):
        assert trecho.tempo_viagem_min and trecho.distancia_km
        assert trecho.chegada_em == trecho.saida_em + timedelta(
            minutes=trecho.tempo_viagem_min + trecho.tempo_adicional_min)


def test_sede_pode_ser_trocada(logado):
    pg = logado
    pg.goto("/viagens/roteiros/novo/")
    sede = pg.locator("input[name='sede-cidade']")
    sede.fill("Londri")
    pg.get_by_role("option", name="Londrina/PR", exact=True).click()
    _cidade(pg, 0, "Maring", "Maringá/PR")
    expect(pg.locator(".itin__trecho-rota").first).to_contain_text("Londrina/PR")
    expect(pg.locator(".itin__trecho--volta .itin__trecho-rota")).to_contain_text(
        re.compile(r"Maringá/PR.*Londrina/PR", re.S))
