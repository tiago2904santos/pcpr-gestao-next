"""Preparação do Ofício: tempos editáveis, chegada calculada e gravação nas larguras reais."""
import re

import pytest
from playwright.sync_api import expect

from gestao.viagens.models import Oficio

from .conftest import rodar_axe

pytestmark = [pytest.mark.e2e, pytest.mark.visual, pytest.mark.a11y]


@pytest.mark.parametrize("largura", [360, 390, 768, 1024, 1440])
def test_tempos_chegada_e_gravacao_na_preparacao(logado, dados_e2e, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.emulate_media(reduced_motion="reduce")
    pk = dados_e2e.ids["oficio_rascunho"]
    pg.goto(f"/viagens/oficios/{pk}/editar/")
    trecho = pg.locator("[data-trecho]").first
    autosave = pg.locator("#form-oficio").get_attribute("data-autosave")
    with pg.expect_response(lambda r: autosave in r.url and r.request.method == "POST") as salvo:
        pg.locator("#id_retorno-saida_0").fill("11/11/2030")
        pg.locator("#id_retorno-saida_1").fill("08:00")
        pg.locator("#id_destino-0-saida_0").fill("10/11/2030")
        pg.locator("#id_destino-0-saida_1").fill("08:00")
        pg.locator("#id_destino-0-tempo_viagem").fill("02:00")
        pg.locator("#id_destino-0-tempo_adicional").fill("00:30")
    assert salvo.value.json()["salvo"], salvo.value.json()
    expect(trecho.locator("[data-chegada]")).to_have_text("10/11/2030 10:30")
    with pg.expect_response(lambda r: autosave in r.url and r.request.method == "POST") as salvo:
        trecho.get_by_role("button", name=re.compile("Aumentar 15 minutos: Tempo adicional")).press("Enter")
    assert salvo.value.json()["salvo"]
    expect(trecho.locator("[data-chegada]")).to_have_text("10/11/2030 10:45")
    pg.wait_for_load_state("networkidle")
    salvo_trecho = Oficio.objects.get(pk=pk).trechos.order_by("ordem").first()
    assert salvo_trecho.tempo_viagem_min == 120
    assert salvo_trecho.tempo_adicional_min == 45
    assert salvo_trecho.chegada_em.hour == 13  # 10h45 Brasília em UTC
    pg.locator("#itin-t-trechos").evaluate("e=>e.scrollIntoView({block:'start'})")
    assert not rodar_axe(pg)
    assert not pg.erros_console
    assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth")
