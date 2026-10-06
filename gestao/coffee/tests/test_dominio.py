"""Regras puras do Coffee Break (CB1)."""

from __future__ import annotations

from datetime import date

import pytest

from gestao.coffee import dominio


def test_cnpj_com_ou_sem_pontuacao():
    assert dominio.normalizar_cnpj("12.345.678/0001-95") == "12345678000195"
    assert dominio.normalizar_cnpj("") == ""
    with pytest.raises(ValueError, match="14 dígitos"):
        dominio.normalizar_cnpj("123")
    assert dominio.formatar_cnpj("12345678000195") == "12.345.678/0001-95"


def test_nome_curto_sem_tipo_da_empresa():
    assert dominio.nome_curto("Doces & Salgados Ltda") == "DOCES & SALGADOS"
    assert dominio.nome_curto("Buffet Exemplo - EIRELI") == "BUFFET EXEMPLO"
    assert dominio.nome_curto("Café Bom S.A.") == "CAFÉ BOM"


def test_referencia_documental_so_com_o_que_existe():
    assert dominio.referencia_documental("123/2025", "4567", "2") == (
        "123/2025 – GMS 4567 - TERMO ADITIVO Nº 2")
    assert dominio.referencia_documental("123/2025") == "123/2025"


def test_fim_efetivo_e_selo_de_vigencia():
    assert dominio.fim_efetivo(date(2026, 3, 1), [date(2026, 12, 31)]) == date(2026, 12, 31)
    assert dominio.fim_efetivo(None, []) is None
    hoje = date(2026, 10, 5)
    assert dominio.selo_vigencia(date(2026, 12, 31), hoje, True).nota == (
        "Vigente até 31/12/2026 (estimada)")
    assert dominio.selo_vigencia(date(2026, 1, 1), hoje).texto == "Vencido"


def test_separar_municipios():
    assert dominio.separar_municipios("Curitiba, São José dos Pinhais/PR; Londrina e Maringá\n"
                                      "curitiba") == [
        "Curitiba", "São José dos Pinhais", "Londrina", "Maringá"]
