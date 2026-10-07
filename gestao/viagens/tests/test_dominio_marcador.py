"""Marcas do documento (Retificado × Complementar) no menu do ofício (LP-30, D7).

Regra da referência: as marcas são mutuamente exclusivas — ligar uma tira a outra; o mesmo
item liga e desliga. "Retificado" só muda o rótulo na Autorização (dominio.assunto), então
numa Convalidação o menu não oferece ligá-la (desligar, sim, para limpar o dado).
"""

from __future__ import annotations

import pytest

from gestao.viagens.dominio.assunto import Marcador, alternar_marcador, marcas_do_menu


@pytest.mark.parametrize(("atual", "marca", "resultado"), [
    ("", "complementar", Marcador.COMPLEMENTAR),
    ("complementar", "complementar", Marcador.NENHUM),
    ("retificado", "complementar", Marcador.COMPLEMENTAR),   # exclusão mútua
    ("", "retificado", Marcador.RETIFICADO),
    ("retificado", "retificado", Marcador.NENHUM),
    ("complementar", "retificado", Marcador.RETIFICADO),     # exclusão mútua
])
def test_alternar_liga_desliga_e_exclui_a_outra(atual, marca, resultado):
    assert alternar_marcador(atual, marca) is resultado


def test_alternar_exige_uma_marca():
    with pytest.raises(ValueError, match="marca"):
        alternar_marcador("", "")


def _resumo(opcoes):
    return [(o.marca.value, o.ligar, o.tira.value) for o in opcoes]


def test_menu_sem_marca_na_autorizacao_oferece_as_duas():
    assert _resumo(marcas_do_menu("", autorizacao=True)) == [
        ("retificado", True, ""), ("complementar", True, "")]


def test_menu_diz_qual_marca_sai_ao_ligar_a_outra():
    assert _resumo(marcas_do_menu("retificado", autorizacao=True)) == [
        ("retificado", False, ""), ("complementar", True, "retificado")]
    assert _resumo(marcas_do_menu("complementar", autorizacao=True)) == [
        ("retificado", True, "complementar"), ("complementar", False, "")]


def test_convalidacao_nao_oferece_ligar_retificado_mas_deixa_desligar():
    assert _resumo(marcas_do_menu("", autorizacao=False)) == [("complementar", True, "")]
    assert _resumo(marcas_do_menu("retificado", autorizacao=False)) == [
        ("retificado", False, ""), ("complementar", True, "retificado")]
