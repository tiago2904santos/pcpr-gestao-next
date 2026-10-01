from __future__ import annotations

import pytest

from gestao.cadastros.validacoes import (
    cpf_valido,
    formatar_cpf,
    formatar_placa,
    normalizar_placa,
    placa_valida,
    sem_acentos,
    somente_digitos,
)
from gestao.viagens.tests.cenarios import cpf_ficticio


@pytest.mark.parametrize("cpf", ["529.982.247-25", "52998224725", cpf_ficticio(123456700)])
def test_cpf_valido(cpf):
    assert cpf_valido(cpf)


@pytest.mark.parametrize("cpf", ["", "111.111.111-11", "529.982.247-24", "123"])
def test_cpf_invalido(cpf):
    assert not cpf_valido(cpf)


def test_formatacoes():
    assert formatar_cpf("52998224725") == "529.982.247-25"
    assert formatar_cpf("123") == "123"
    assert somente_digitos("26.655.434-6") == "266554346"
    assert normalizar_placa("abc-1d23") == "ABC1D23"
    assert formatar_placa("AYS4579") == "AYS-4579"
    assert formatar_placa("ABC1D23") == "ABC1D23"
    assert sem_acentos("Paraná São José") == "Parana Sao Jose"


@pytest.mark.parametrize(("placa", "ok"), [("AYS-4579", True), ("ABC1D23", True),
                                            ("AB12345", False), ("ABCD123", False)])
def test_placa(placa, ok):
    assert placa_valida(placa) is ok
