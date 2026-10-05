"""Regras puras do atendimento à imprensa: situações e filas, andamento, deadline, leitura
de horários e fontes alinhadas por bloco (paridade com a referência)."""

from __future__ import annotations

from datetime import date, time

import pytest

from gestao.imprensa import dominio


def test_filas_cobrem_as_situacoes_e_abertas_excluem_encerradas():
    assert len(dominio.SITUACOES) == 9
    assert set(dominio.ROTULOS) == dominio.ABERTAS | dominio.ENCERRADAS
    assert not dominio.ABERTAS & dominio.ENCERRADAS
    filas = {c: s for c, _r, s in dominio.FILAS}
    assert filas["abertos"] == dominio.ABERTAS
    assert filas["atendidos"] == {"atendido"} and filas["nao_responder"] == {"nao_responder"}


def test_andamento_exige_situacao_nova_e_texto_para_atendido():
    with pytest.raises(dominio.RegraViolada, match="Escolha a nova situação"):
        dominio.conferir_andamento("em_andamento", "em_andamento", "", "", "")
    with pytest.raises(dominio.RegraViolada, match="Escolha"):
        dominio.conferir_andamento("em_andamento", "inexistente", "", "", "")
    with pytest.raises(dominio.RegraViolada, match="Para marcar como atendido"):
        dominio.conferir_andamento("em_andamento", "atendido", "  ", "", "")
    # Basta um dos três: a anotação agora, a resposta registrada ou o andamento anterior.
    dominio.conferir_andamento("em_andamento", "atendido", "Nota enviada", "", "")
    dominio.conferir_andamento("em_andamento", "atendido", "", "Resposta", "")
    dominio.conferir_andamento("em_andamento", "atendido", "", "", "Fonte respondeu")
    dominio.conferir_andamento("atendido", "nao_responder", "", "", "")


def test_deadline_nao_antes_do_pedido_e_selo():
    assert dominio.conferir_deadline(date(2026, 10, 5), date(2026, 10, 4))
    assert not dominio.conferir_deadline(date(2026, 10, 5), date(2026, 10, 5))
    assert not dominio.conferir_deadline(date(2026, 10, 5), None)
    hoje = date(2026, 10, 5)
    vencido = dominio.selo_do_deadline(date(2026, 10, 3), "em_andamento", hoje)
    assert vencido and vencido.tom == "perigo" and vencido.texto == "Deadline vencido em 03/10"
    assert dominio.selo_do_deadline(hoje, "aguardando_fonte", hoje) == dominio.SeloPrazo(
        "Deadline hoje", "aviso")
    futuro = dominio.selo_do_deadline(date(2026, 10, 9), "em_andamento", hoje)
    assert futuro and futuro.texto == "Deadline 09/10/2026" and futuro.tom == "neutro"
    assert dominio.selo_do_deadline(date(2026, 10, 3), "atendido", hoje) is None
    assert dominio.selo_do_deadline(None, "em_andamento", hoje) is None


@pytest.mark.parametrize(("texto", "esperado"), [
    ("17h03", time(17, 3)), ("16h", time(16, 0)), ("17:03", time(17, 3)),
    ("9H40", time(9, 40)), ("17.03", time(17, 3)), ("17:03:00", time(17, 3)),
    (" 08h05 ", time(8, 5)), ("", None), (None, None), ("17", None), ("17:", None),
    ("25h00", None), ("12h61", None), ("meio-dia", None),
])
def test_ler_hora(texto, esperado):
    assert dominio.ler_hora(texto) == esperado


def test_fontes_alinhadas_por_bloco():
    fontes = dominio.fontes_alinhadas("Del. Fulano\n\nAscom   DPCAP\n\n\nIML",
                                      "09h12\n\n09h40", "09h30")
    assert fontes == [dominio.Fonte("Del. Fulano", "09h12", "09h30"),
                      dominio.Fonte("Ascom DPCAP", "09h40", ""),
                      dominio.Fonte("IML", "", "")]
    assert dominio.fontes_alinhadas("", "09h", "10h") == []


def test_limpeza_de_texto():
    assert dominio.uma_linha("  Ana \n  Paula ") == "Ana Paula"
    assert dominio.multilinha("  a  \n\n\n\n b \n\n") == "a\n\nb"
    assert dominio.resumo("x" * 100).endswith("…") and len(dominio.resumo("x" * 100)) == 88
    assert dominio.percentual(1, 3) == 33 and dominio.percentual(0, 0) == 0
