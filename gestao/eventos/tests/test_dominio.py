"""Regras puras da solicitação de evento: transições, envio à DG, despacho, atendida só
depois do evento, cancelamento, selo de tempo, pedido em cima da hora e etapas."""

from __future__ import annotations

from datetime import date

import pytest

from gestao.eventos import dominio

HOJE = date(2026, 10, 5)


def test_transicoes():
    dominio.conferir_transicao("rascunho", "aguardando_despacho")
    dominio.conferir_transicao("deferida", "aguardando_despacho")  # reaberta
    with pytest.raises(dominio.RegraViolada, match="Transição de Rascunho para Atendida"):
        dominio.conferir_transicao("rascunho", "atendida")
    with pytest.raises(dominio.RegraViolada):
        dominio.conferir_transicao("atendida", "aguardando_despacho")


def _envio(**kw):
    base = {"preenchidos": {c: True for c, _r in dominio.CAMPOS_DO_ENVIO}, "servicos": 1,
            "equipes": {"Alfa": 2}, "tipo_operacao": "diaria", "unidade_movel": False,
            "unidade_movel_designada": False}
    base.update(kw)
    return dominio.DadosDoEnvio(**base)


def test_envio():
    assert dominio.erros_do_envio("rascunho", _envio()) == []
    assert dominio.erros_do_envio("deferida", _envio()) == [dominio.MSG_SO_RASCUNHO_OU_DEVOLVIDA]
    erros = dominio.erros_do_envio("devolvida", _envio(
        preenchidos={"data_solicitacao": True}, servicos=0, equipes={"Alfa": None, "Bravo": 0},
        tipo_operacao="", unidade_movel=True))
    assert erros[0].startswith("Preencha os campos obrigatórios antes de enviar: Início do evento")
    assert erros[0].endswith("Tipo de operação.")
    assert dominio.MSG_SERVICO in erros and dominio.MSG_UNIDADE_MOVEL in erros
    assert "Informe a quantidade de servidores de Alfa, Bravo para enviar à DG." in erros
    assert dominio.MSG_EQUIPE in dominio.erros_do_envio("rascunho", _envio(equipes={}))


def test_despacho():
    assert dominio.conferir_despacho("aguardando_despacho", "atender", "") == "deferida"
    assert dominio.conferir_despacho("aguardando_despacho", "devolver", "Corrigir local") == (
        "devolvida")
    with pytest.raises(dominio.RegraViolada, match="observação é obrigatória"):
        dominio.conferir_despacho("aguardando_despacho", "nao_atender", " ")
    with pytest.raises(dominio.RegraViolada, match="deve corrigir"):
        dominio.conferir_despacho("aguardando_despacho", "devolver", "")
    with pytest.raises(dominio.RegraViolada, match="Selecione a decisão"):
        dominio.conferir_despacho("aguardando_despacho", "", "")
    with pytest.raises(dominio.RegraViolada, match="já foi finalizada"):
        dominio.conferir_despacho("atendida", "atender", "")
    with pytest.raises(dominio.RegraViolada, match="Somente solicitações aguardando"):
        dominio.conferir_despacho("rascunho", "atender", "")


def test_concluir_e_cancelar():
    assert dominio.pode_concluir("deferida", date(2026, 10, 4), HOJE) == ""
    assert "após 05/10/2026" in dominio.pode_concluir("deferida", HOJE, HOJE)
    assert dominio.pode_concluir("aguardando_despacho", date(2026, 10, 1), HOJE)
    dominio.conferir_cancelamento("deferida", "Chuva")
    with pytest.raises(dominio.RegraViolada, match="motivo do cancelamento"):
        dominio.conferir_cancelamento("devolvida", "")
    with pytest.raises(dominio.RegraViolada, match="em andamento"):
        dominio.conferir_cancelamento("rascunho", "x")


def test_selo_e_em_cima_da_hora():
    assert dominio.selo_de_tempo(date(2026, 10, 6), None, "aguardando_despacho", HOJE) == (
        dominio.Selo("Evento amanhã", "perigo"))
    assert dominio.selo_de_tempo(date(2026, 10, 11), None, "rascunho", HOJE) == dominio.Selo(
        "Evento em 6 dias", "aviso")
    assert dominio.selo_de_tempo(date(2026, 10, 20), None, "deferida", HOJE).texto == "Previsto"
    assert dominio.selo_de_tempo(date(2026, 10, 1), date(2026, 10, 2), "deferida",
                                 HOJE).texto == "Realizado"
    assert dominio.selo_de_tempo(date(2026, 10, 4), date(2026, 10, 6), "deferida",
                                 HOJE).texto == "Acontecendo"
    assert dominio.em_cima_da_hora(date(2026, 10, 1), date(2026, 10, 5)) == (
        "Pedido em cima da hora (4 dias antes)")
    assert dominio.em_cima_da_hora(HOJE, HOJE) == "Pedido em cima da hora (no dia do evento)"
    assert dominio.em_cima_da_hora(date(2026, 9, 1), HOJE) == ""


def test_etapas_e_protocolo():
    assert [e.estado for e in dominio.etapas("rascunho")] == ["atual", "pendente", "pendente",
                                                             "pendente"]
    assert [e.estado for e in dominio.etapas("devolvida")][:2] == ["concluido", "atual"]
    assert dominio.etapas("cancelada")[3].titulo == "Cancelada"
    assert all(e.estado == "concluido" for e in dominio.etapas("atendida"))
    assert dominio.formatar_protocolo("123456789") == "12.345.678-9"
    with pytest.raises(dominio.RegraViolada):
        dominio.formatar_protocolo("12")
