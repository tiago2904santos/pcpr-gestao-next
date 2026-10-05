"""Conferência do hodômetro do diário de bordo (domínio puro; textos da referência)."""

from __future__ import annotations

from gestao.viagens.dominio import diario as d


def test_tolerancia_20_por_cento_minimo_10():
    assert d.tolerancia_km(30) == 10
    assert d.tolerancia_km(100) == 20
    assert d.tolerancia_km(101) == 21  # arredonda para cima


def test_numero_do_km_aceita_pontos_e_texto():
    assert d.numero_do_km("12.345") == 12345
    assert d.numero_do_km("12345 km") == 12345
    assert d.numero_do_km("") is None and d.numero_do_km(None) is None


def test_sem_avisos_quando_tudo_bate():
    c = d.conferir([d.Linha("A → B", 1000, 1100, 100), d.Linha("B → A", 1100, 1205, 100)])
    assert c.avisos == [] and c.rodados == [100, 105]
    assert c.total_rodado == 205 and c.total_previsto == 200


def test_hodometro_voltou_para_tras():
    c = d.conferir([d.Linha("A → B", 1000, 1100, None), d.Linha("B → A", 1050, 1150, None)])
    assert c.avisos == ["B → A: o km de saída (1.050) é menor que o de chegada do trecho "
                        "anterior (1.100) — o hodômetro voltou para trás."]


def test_rodado_fora_da_tolerancia():
    c = d.conferir([d.Linha("Curitiba/PR → Londrina/PR", 10000, 10500, 380)])
    assert c.avisos == ["Curitiba/PR → Londrina/PR: 500 km rodados, e a distância prevista é "
                        "de 380 km (diferença de 120 km)."]
    assert d.conferir([d.Linha("x", 0, 450, 380)]).avisos == []  # 70 ≤ 76


def test_saida_menor_que_o_ultimo_km_da_viatura():
    ultimo = d.UltimoKm(20000, "01/10/2026", "7/2026")
    c = d.conferir([d.Linha("A → B", 19000, 19100, None)], ultimo)
    assert c.avisos == ["O km de saída (19.000) é menor que o último km registrado desta "
                        "viatura (20.000, em 01/10/2026, Ofício 7/2026)."]


def test_preenchido():
    assert not d.preenchido([])
    assert not d.preenchido([d.Linha("x", 1, None, None)])
    assert d.preenchido([d.Linha("x", 1, 2, None)])
