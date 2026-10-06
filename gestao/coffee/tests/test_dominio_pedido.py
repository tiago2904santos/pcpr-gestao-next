"""Regras puras do pedido de coffee break (CB2): lote pelo município, valor, situação
financeira, vigência, retroativo, antecedência e número da OS."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from gestao.coffee import dominio_pedido as d

DATA = date(2026, 10, 20)


def _lote(i, municipios=(), exercicio="2026", fim=date(2026, 12, 31), restante=100, cidades=()):
    return d.LoteCandidato(i, f"Lote {i} ({exercicio})", exercicio, frozenset(municipios), fim,
                           restante, tuple(cidades))


def test_lote_que_lista_o_municipio_com_as_preferencias():
    vencido = _lote(1, {10}, fim=date(2026, 1, 1), restante=999)
    outro_ano = _lote(2, {10}, exercicio="2025", restante=999)
    pouco = _lote(3, {10}, restante=10)
    muito = _lote(4, {10}, restante=500)
    assert d.escolher_lote(10, None, None, DATA, [vencido, outro_ano, pouco, muito]).lote_id == 4
    assert d.escolher_lote(10, None, None, DATA, [vencido, outro_ano]).lote_id == 2
    assert d.escolher_lote(10, None, None, DATA, [vencido]).lote_id == 1


def test_lote_pela_cidade_mais_proxima_e_nenhum():
    curitiba = (1, "Curitiba", -25.4284, -49.2733)
    londrina = (2, "Londrina", -23.3045, -51.1696)
    lotes = [_lote(1, {1}, cidades=[curitiba]), _lote(2, {2}, cidades=[londrina])]
    e = d.escolher_lote(99, -25.53, -49.20, DATA, lotes)  # perto de Curitiba
    assert e.lote_id == 1 and e.por_proximidade and e.cidade.startswith("Curitiba, a ")
    assert d.escolher_lote(99, None, None, DATA, lotes) is None
    assert d.escolher_lote(99, -25.5, -49.2, DATA, []) is None


def test_valor_e_moeda():
    assert d.valor(40, Decimal("21.0700")) == Decimal("842.80")
    assert d.valor(3, Decimal("0.005")) == Decimal("0.02")  # meio para cima
    assert d.moeda(Decimal("1234.5")) == "R$ 1.234,50" and d.moeda(None) == "—"
    assert d.quantidade_efetiva(300, 280) == 280 and d.quantidade_efetiva(300, None) == 300


def test_consumo_e_situacao_financeira():
    assert d.percentual_consumido(480, 1000) == 48 and d.tom_do_consumo(48) == "sucesso"
    assert d.tom_do_consumo(70) == "aviso" and d.tom_do_consumo(90) == "perigo"
    assert d.situacao(d.Marcos()) == "aguardando_nota"
    assert d.situacao(d.Marcos(nota=True, protocolo=True)) == "aguardando_atesto"
    assert d.situacao(d.Marcos(nota=True, envio_empresa=True)) == "concluida"
    assert d.situacao(d.Marcos(cancelada=True, envio_empresa=True)) == "cancelada"
    assert not d.financeiro_iniciado(d.Marcos()) and d.financeiro_iniciado(d.Marcos(nota=True))


def test_vigencia_retroativo_e_antecedencia():
    with pytest.raises(ValueError, match="Contrato vencido em 01/01/2026"):
        d.conferir_vigencia(date(2026, 1, 1), DATA, "12/2025", "Lote 1 (2026)")
    d.conferir_vigencia(None, DATA, "x", "y")
    with pytest.raises(ValueError, match="registro retroativo"):
        d.conferir_retroativo(date(2026, 10, 1), DATA, False, "")
    with pytest.raises(ValueError, match="Justifique"):
        d.conferir_retroativo(date(2026, 10, 1), DATA, True, " ")
    d.conferir_retroativo(date(2026, 10, 1), DATA, True, "Evento já ocorrido")
    hoje = date(2026, 10, 5)
    assert "amanhã (06/10/2026)" in d.aviso_antecedencia(date(2026, 10, 6), hoje, 2, "12/2025")
    assert d.aviso_antecedencia(date(2026, 10, 9), hoje, 2, "12/2025") == ""


def test_numero_da_os():
    assert d.formatar_numero("41", 2026) == "41/2026"
    assert d.formatar_numero("041/2025", 2026) == "41/2025"
    assert d.formatar_numero("", 2026) == ""
    with pytest.raises(ValueError, match="1 ou mais"):
        d.formatar_numero("0", 2026)
    assert d.sequencia("41/2026") == (2026, 41) and d.sequencia("x") is None


def test_ordem_dos_marcos():
    assert d.erros_dos_marcos("", "12.345.678-9", None, None, None) == {
        "protocolo_pagamento": "Informe a nota fiscal antes do protocolo de pagamento."}
    e = d.erros_dos_marcos("1", "p", date(2026, 5, 10), date(2026, 5, 1), date(2026, 4, 1))
    assert e["ordem_bancaria_em"] == "A ordem bancária não pode ser anterior ao atesto."
    assert "não pode ser anterior à emissão" in e["envio_empresa_em"]
    assert d.erros_dos_marcos("1", "", None, date(2026, 5, 1), None) == {
        "ordem_bancaria_em": "Informe o atesto antes da ordem bancária."}


def test_protocolo_stepper_proximo_marco_e_faturada():
    assert d.formatar_protocolo("123456789") == "12.345.678-9"
    assert d.formatar_protocolo("") == ""
    with pytest.raises(ValueError, match=r"00.000.000-0"):
        d.formatar_protocolo("12345")
    valores = {"nota_fiscal": "8957", "protocolo_pagamento": "", "atesto_em": None}
    assert d.proximo_marco(valores, False) == ("protocolo_pagamento", "Protocolo de pagamento",
                                               "texto")
    assert d.proximo_marco(valores, True) is None
    estados = dict(d.etapas(valores, False))
    assert estados["Nota fiscal"] == "concluido" and estados["Protocolo"] == "atual"
    assert d.texto_faturada(300, None, 280).endswith("20 voltaram ao saldo do lote.")
    assert "10 a mais saíram" in d.texto_faturada(300, None, 310)
    assert d.texto_faturada(300, 280, None).startswith("Quantidade faturada removida")
    assert d.texto_faturada(300, 280, 280) == ""
