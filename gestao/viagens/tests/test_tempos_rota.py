"""Caracterização numérica da regra confirmada, sem Django ou provedores."""

from __future__ import annotations

from decimal import Decimal

import pytest

from gestao.viagens.dominio.tempos_rota import (
    arredondar_a_15,
    minutos_da_api,
    tempo_adicional_sugerido,
    tempo_de_viagem,
)


@pytest.mark.parametrize("minutos,esperado", [
    (-30, 0), (-0.5, 0), (0, 0), (5, 0), (5.49, 0), (5.5, 15), (6, 15),
    (14, 15), (15, 15), (20, 15), (20.5, 15), (20.5001, 30), (21, 30),
    (35, 30), (35.5, 45), (36, 45), (50.5, 45), (50.5001, 60),
])
def test_arredondamento_preserva_resto_cinco_e_empate_para_par(minutos, esperado):
    assert arredondar_a_15(minutos) == esperado


@pytest.mark.parametrize("segundos,esperado", [
    (None, 0), (0, 0), (-90, 0), (29, 0), (30, 0), (31, 1),
    (90, 2), (150, 2), (151, 3), (3600, 60), (Decimal("3630"), 60),
])
def test_api_arredonda_segundos_a_minuto_antes_da_mistura(segundos, esperado):
    assert minutos_da_api(segundos) == esperado


@pytest.mark.parametrize("km,api,esperado", [
    (0, 0, 15), (-12, 0, 0), (-100, 0, 0), (62, 60, 60),
    (74, 60, 75), (136, 120, 120), (300, 180, 240),
    (62, 0, 60), (62, None, 60), (62, 120, 75),
    (Decimal("136"), Decimal("120"), 120), (Decimal("62"), None, 60),
])
def test_viagem_pesos_calibracao_e_ausencia_de_api(km, api, esperado):
    assert tempo_de_viagem(km, api) == esperado


@pytest.mark.parametrize("minutos,esperado", [
    (-10, 0), (0, 0), (29, 0), (29.999, 0), (30, 15), (60, 15), (120, 15),
    (123, 15), (123.001, 30), (150, 30), (180, 30), (212.999, 30),
    (213, 45), (240, 45), (270, 45), (360, 60),
    (Decimal("29.999"), 0), (Decimal("30"), 15), (Decimal("240"), 45),
])
def test_adicional_limite_meia_hora_e_um_sexto_arredondado(minutos, esperado):
    assert tempo_adicional_sugerido(minutos) == esperado


def test_quatro_horas_sugere_45_e_nao_o_30_da_regra_anterior():
    assert tempo_adicional_sugerido(4 * 60) == 45


def test_peso_sem_api_gera_51_min_e_resto_seis_sobe_para_60():
    assert arredondar_a_15(51) == 60
    assert tempo_de_viagem(62, None) == 60


@pytest.mark.parametrize("minutos", ["5.5", "20.5", "20.5001", "35.5", "240"])
def test_decimal_arredonda_com_mesma_regra_de_empate_dos_floats(minutos):
    assert arredondar_a_15(Decimal(minutos)) == arredondar_a_15(float(minutos))


def test_pipeline_numerico_do_segmento_usa_segundos_km_e_campos_separados():
    api = minutos_da_api(10_800)
    viagem = tempo_de_viagem(Decimal("300.00"), api)
    adicional = tempo_adicional_sugerido(viagem)
    assert (api, viagem, adicional) == (180, 240, 45)
    assert viagem + adicional == 285
