"""Regras puras das palestras: opções de status, o que cada status pede, etapas, resposta
padrão com marcadores, links, formatos (telefone, CEP, protocolo) e período."""

from __future__ import annotations

from datetime import date, time

import pytest

from gestao.palestras import dominio

HOJE = date(2026, 10, 5)


def test_opcoes_de_status_sem_atendida_antes_do_evento():
    assert "pendente" not in dominio.opcoes_de_status("pendente", None, HOJE)
    assert "atendida" not in dominio.opcoes_de_status("agendada", date(2026, 10, 9), HOJE)
    assert "atendida" in dominio.opcoes_de_status("agendada", date(2026, 10, 5), HOJE)
    assert "atendida" in dominio.opcoes_de_status("agendada", None, HOJE)


def _conferir(**kw):
    base = {"atual": "pendente", "novo": "agendada", "hoje": HOJE, "data_inicio": None,
            "data_fim": None, "data_informada": None, "tem_palestrante": False,
            "palestrante_informado": False, "publico": None, "publico_informado": None}
    base.update(kw)
    return dominio.conferir_andamento(**base)


def test_o_que_cada_status_pede():
    assert _conferir(novo="pendente") == [dominio.MSG_ESCOLHA]
    assert _conferir() == [dominio.MSG_DATA, dominio.MSG_PALESTRANTE]
    assert _conferir(data_informada=date(2026, 10, 9), palestrante_informado=True) == []
    assert _conferir(data_informada=date(2026, 10, 9), data_fim=date(2026, 10, 8),
                     tem_palestrante=True) == [dominio.MSG_DATA_DEPOIS_DO_FIM]
    assert _conferir(novo="atendida", data_inicio=date(2026, 10, 9)) == [
        dominio.MSG_ANTES_DO_EVENTO, dominio.MSG_PUBLICO]
    assert _conferir(novo="atendida", data_informada=date(2026, 10, 1),
                     publico_informado=50) == []
    assert _conferir(novo="em_andamento") == []
    assert _conferir(novo="cancelada") == []


def test_etapas():
    assert [(e.titulo, e.estado) for e in dominio.etapas("aguardando_retorno")] == [
        ("Recebida", "concluido"), ("Aguardando retorno", "atual"), ("Agendada", "pendente"),
        ("Atendida", "pendente")]
    assert all(e.estado == "concluido" for e in dominio.etapas("atendida"))
    assert all(e.estado == "pendente" for e in dominio.etapas("cancelada"))


def test_resposta_padrao_e_links():
    texto = dominio.preencher_resposta(
        "Olá, {solicitante}! {Data} às {horario}. {desconhecido}{tema} {x y}",
        {"solicitante": "Escola X", "data": "09/10/2026", "horario": "", "tema": "Golpes"})
    assert texto == "Olá, Escola X! 09/10/2026 às . Golpes {x y}"
    assert dominio.link_email("a@b.invalid", "Assunto", "Olá mundo") == (
        "mailto:a@b.invalid?subject=Assunto&body=Ol%C3%A1%20mundo")
    assert dominio.link_email("", "a", "b") == ""
    assert dominio.link_whatsapp("(41) 99999-8888", "oi") == "https://wa.me/5541999998888?text=oi"
    assert dominio.link_whatsapp("123", "oi") == ""


def test_formatos():
    assert dominio.formatar_telefone("41999998888") == "(41) 99999-8888"
    assert dominio.formatar_telefone("4133334444") == "(41) 3333-4444"
    assert dominio.formatar_telefone("") == ""
    with pytest.raises(dominio.RegraViolada):
        dominio.formatar_telefone("1234")
    assert dominio.formatar_cep("80000000") == "80000-000"
    with pytest.raises(dominio.RegraViolada):
        dominio.formatar_cep("800")
    assert dominio.formatar_protocolo("email", "123") == ""
    assert dominio.formatar_protocolo("protocolo", "123456789") == "12.345.678-9"
    with pytest.raises(dominio.RegraViolada, match="Informe o número"):
        dominio.formatar_protocolo("protocolo", "")
    with pytest.raises(dominio.RegraViolada, match="9 dígitos"):
        dominio.formatar_protocolo("protocolo", "12")


def test_periodo_e_quando():
    with pytest.raises(dominio.RegraViolada, match="data inicial"):
        dominio.conferir_periodo(None, date(2026, 10, 1))
    with pytest.raises(dominio.RegraViolada, match="anterior"):
        dominio.conferir_periodo(date(2026, 10, 2), date(2026, 10, 1))
    assert dominio.periodo_do_evento(date(2026, 10, 9), date(2026, 10, 10), time(14), "") == (
        "09/10/2026 a 10/10/2026 · 14:00")
    assert dominio.periodo_do_evento(date(2026, 10, 9), None, None, "10/10 às 13h") == (
        "09/10/2026")
    assert dominio.periodo_do_evento(None, None, None, "à definir") == "à definir"
    assert dominio.quando(date(2026, 10, 1), None, HOJE) == dominio.SeloQuando("Realizado",
                                                                                "sucesso")
    assert dominio.quando(date(2026, 10, 5), date(2026, 10, 6), HOJE).texto == "Acontecendo"
    assert dominio.quando(date(2026, 10, 9), None, HOJE).texto == "Previsto"
    assert dominio.quando(None, None, HOJE) is None
