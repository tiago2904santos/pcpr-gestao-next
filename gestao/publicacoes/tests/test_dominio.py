"""Regras puras das publicações: status e filas, novo status, publicação automática,
datas, tempo até publicar e leitura de horários (paridade com a referência)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from gestao.publicacoes import dominio


def test_status_e_filas():
    assert [v for v, *_ in dominio.STATUS] == ["pendente", "em_andamento", "publicada",
                                               "cancelada"]
    assert set(dominio.ROTULOS) == dominio.ABERTOS | dominio.ENCERRADOS
    assert {c for c, _r, _s in dominio.FILAS} == {"pendentes", "andamento", "publicadas",
                                                  "canceladas"}


def test_novo_status_tem_que_mudar():
    with pytest.raises(dominio.RegraViolada, match="Escolha o novo status") as exc:
        dominio.conferir_novo_status("pendente", "pendente")
    assert exc.value.campo == "novo_status"
    with pytest.raises(dominio.RegraViolada):
        dominio.conferir_novo_status("pendente", "outro")
    dominio.conferir_novo_status("publicada", "cancelada")


def test_publicacao_automatica_usa_o_agora_e_nunca_antes_da_pauta():
    agora = datetime(2026, 10, 5, 14, 37, 12)
    assert dominio.publicacao_automatica(date(2026, 10, 1), None, None, agora) == (
        date(2026, 10, 5), time(14, 37))
    # Pauta com data futura (registrada antes): a publicação fica na data da pauta.
    assert dominio.publicacao_automatica(date(2026, 10, 9), None, time(9, 0), agora) == (
        date(2026, 10, 9), time(9, 0))
    assert dominio.publicacao_automatica(date(2026, 10, 1), date(2026, 10, 2), None,
                                         agora) == (date(2026, 10, 2), None)


def test_datas():
    with pytest.raises(dominio.RegraViolada, match="Informe a data em que"):
        dominio.conferir_datas("publicada", date(2026, 10, 1), None)
    with pytest.raises(dominio.RegraViolada, match="não pode ser anterior"):
        dominio.conferir_datas("pendente", date(2026, 10, 2), date(2026, 10, 1))
    dominio.conferir_datas("pendente", date(2026, 10, 1), None)


def test_tempo_ate_publicar_e_formato():
    d = dominio.tempo_ate_publicar(date(2026, 10, 1), time(9, 0), date(2026, 10, 1),
                                   time(10, 25))
    assert d == timedelta(hours=1, minutes=25) and dominio.formatar_duracao(d) == "1h25"
    assert dominio.formatar_duracao(timedelta(days=2, hours=3, minutes=5)) == "2d 3h"
    assert dominio.tempo_ate_publicar(date(2026, 10, 1), time(11, 0), date(2026, 10, 1),
                                      time(10, 0)) is None
    assert dominio.tempo_ate_publicar(date(2026, 10, 1), None, date(2026, 10, 1),
                                      time(10, 0)) is None
    assert dominio.formatar_duracao(None) == ""
    assert dominio.media([timedelta(hours=1), timedelta(hours=3)]) == timedelta(hours=2)
    assert dominio.media([]) is None


def test_textos_e_horas():
    assert dominio.quando_publicada(date(2026, 2, 3), time(14, 30)) == (
        "Publicada em 03/02/2026 às 14:30")
    assert dominio.quando_publicada(None, time(1, 0)) == ""
    assert [dominio.sim_nao(v) for v in (True, False, None)] == ["Sim", "Não", ""]
    assert dominio.ler_hora("17h03") == time(17, 3) and dominio.ler_hora("16h") == time(16)
    assert dominio.ler_hora("17") is None and dominio.ler_hora("24:00") is None
