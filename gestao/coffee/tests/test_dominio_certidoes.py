"""Regras puras das certidões (CB5a)."""

from __future__ import annotations

from datetime import date

import pytest

from gestao.coffee import dominio_certidoes as d

HOJE = date(2026, 10, 6)


def test_validade_lida_do_texto():
    assert d.validade_do_texto("Certidão ... Válida até 17/03/2027.") == date(2027, 3, 17)
    assert d.validade_do_texto("Validade:14/09/2026 a 13/10/2026") == date(2026, 10, 13)
    assert d.validade_do_texto("Emitida em 01/09/2026. Válida por 90 (noventa) dias.") == (
        date(2026, 11, 30))
    assert d.validade_do_texto("sem data nenhuma") is None


def test_tipo_cnpj_e_conferencia():
    texto = ("CERTIDÃO NEGATIVA DE DÉBITOS TRABALHISTAS (CNDT) — CNPJ 11.222.333/0001-81 — "
             "Válida até 01/01/2027")
    assert d.tipos_do_texto(texto) == ["trabalhista"]
    assert d.cnpj_aparece("11222333000181", texto)
    assert d.cnpj_aparece("11222333000181", "CNPJ base: 11.222.333")  # só a raiz na certidão
    c = d.conferir(texto, "trabalhista", "11222333000181", "X", "11.222.333/0001-81")
    assert c.validade == date(2027, 1, 1) and c.aviso == ""
    with pytest.raises(ValueError, match="parece ser a certidão Trabalhista, não a FGTS"):
        d.conferir(texto, "fgts", "11222333000181", "X", "x")
    with pytest.raises(ValueError, match=r"não é de Buffet: o CNPJ 44\.555"):
        d.conferir(texto, "trabalhista", "44555666000172", "Buffet", "44.555.666/0001-72")
    with pytest.raises(ValueError, match="parece uma imagem"):
        d.conferir("", "fgts", "1", "X", "x")
    assert d.conferir("", "fgts", "1", "X", "x", date(2026, 12, 1)).aviso == d.MSG_IMAGEM
    with pytest.raises(ValueError, match="Não achei a validade"):
        d.conferir("Certidão de regularidade do FGTS — CNPJ 11222333000181", "fgts",
                   "11222333000181", "X", "x")


def test_situacao():
    assert d.situacao(None, HOJE)[0] == "faltando"
    assert d.situacao(date(2026, 10, 1), HOJE)[0] == "vencida"
    assert d.situacao(date(2026, 10, 21), HOJE)[0] == "vencendo"
    assert d.situacao(date(2026, 10, 22), HOJE) == ("vigente", "Válida até 22/10/2026", "sucesso")
