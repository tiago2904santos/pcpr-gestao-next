"""Relatório técnico (domínio puro): diária recebida, custeio, data do documento,
marcadores e o que conta como preenchido."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from gestao.viagens.dominio import relatorio as r


def test_ler_valor_com_observacao():
    assert r.ler_valor("R$ 87,00 (saque)") == (Decimal("87.00"), "(saque)")
    assert r.ler_valor("1.234,5") == (Decimal("1234.50"), "")
    assert r.ler_valor("  ") == (None, "")
    for errado in ("abc", "350,00,00"):
        with pytest.raises(r.ValorInvalido):
            r.ler_valor(errado)


def test_recebido_nunca_acima_do_liberado():
    assert r.conferir_recebido(None, Decimal("100")) == ""
    assert r.conferir_recebido(Decimal("87"), Decimal("88.50")) == ""
    assert "maior que zero" in r.conferir_recebido(Decimal("0"), None)
    assert r.conferir_recebido(Decimal("90"), Decimal("88.50")).startswith(
        "O valor recebido não pode passar do liberado (R$ 88,50).")


def test_custeio():
    assert r.custeio("combustivel", "Cartão Prime") == "Cartão Prime"
    assert r.custeio("translado", r.OUTRO, "  Uber  da sede ") == "Uber da sede"
    assert r.custeio("translado", r.OUTRO, "") is None  # "Outro" vazio não apaga
    assert r.custeio("passagem", "valor estranho") is None


def test_data_do_documento():
    # Retorno sex 02/10/2026: limite = qua 07/10.
    assert r.data_do_documento(date(2026, 9, 30), date(2026, 10, 2)) == date(2026, 10, 2)
    assert r.data_do_documento(date(2026, 10, 5), date(2026, 10, 2)) == date(2026, 10, 5)
    assert r.data_do_documento(date(2026, 10, 20), date(2026, 10, 2)) == date(2026, 10, 7)
    assert r.data_do_documento(date(2026, 10, 20), None) == date(2026, 10, 20)


def test_marcadores_e_preenchido():
    assert r.aplicar_marcadores("Evento em {destino}, {periodo}. {x}",
                                {"destino": "Londrina/PR", "periodo": "07 a 09/10"}) == (
        "Evento em Londrina/PR, 07 a 09/10. {x}")
    assert not r.preenchido({"motivo": "a", "atividade": " ", "conclusao": "c"})
    assert r.preenchido({"motivo": "a", "atividade": "b", "conclusao": "c"})


def test_sugerir_conclusao_e_medidas():
    ctx = r.Contexto(evento="PCPR na Comunidade", destino="Londrina/PR",
                     periodo="07/10 a 09/10/2026", atividades=("Palestra", "Atendimento"))
    conclusao = r.sugerir("conclusao", ctx, {"atividade": "Apoiar a ação"})
    assert conclusao.startswith("A participação no evento “PCPR na Comunidade”, em "
                                "Londrina/PR, no período de 07/10 a 09/10/2026, foi realizada")
    assert "(Palestra e Atendimento) foram desenvolvidas." in conclusao
    assert "O objetivo da participação — Apoiar a ação — foi atingido." in conclusao
    medidas = r.sugerir("medidas", ctx, {"conclusao": "Houve uma pendência com o local."})
    assert medidas.startswith("Recomenda-se ao órgão: registrar e divulgar internamente os "
                              "resultados do evento “PCPR na Comunidade”")
    assert "acompanhar a pendência apontada na conclusão" in medidas
    sem_nada = r.sugerir("conclusao", r.Contexto(), {})
    assert sem_nada.startswith("A viagem, foi") is False and sem_nada.startswith("A viagem foi")
    with pytest.raises(ValueError):
        r.sugerir("motivo", ctx, {})
    assert r.listar(["a", "b", "c", "d", "e", "f"]) == "a, b, c, d e outras 2"
