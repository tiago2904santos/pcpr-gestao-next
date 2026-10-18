"""Regras puras da automação: telefone E.164 (com o 9º dígito), status que não regride,
espera entre tentativas, janela de 24 h e palavras-chave."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gestao.automacao import dominio


@pytest.mark.parametrize("entrada,saida", [
    ("41999990001", "5541999990001"), ("(41) 99999-0001", "5541999990001"),
    ("5541999990001", "5541999990001"), ("4133330000", "554133330000"),
    ("41899990001", ""), ("0199990001", ""), ("4199999", ""), ("", ""), (None, ""),
    ("41999999999", ""), ("4100000000", ""),
])
def test_e164_do_brasil(entrada, saida):
    assert dominio.e164_do_brasil(entrada) == saida


def test_variantes_do_nono_digito():
    assert dominio.variantes("5541999990001") == {"5541999990001", "554199990001"}
    assert dominio.mesmo_numero("554199990001", "5541999990001")
    assert not dominio.mesmo_numero("5541999990001", "5541999990002")
    assert not dominio.mesmo_numero("", "5541999990001")


@pytest.mark.parametrize("atual,recebido,esperado", [
    ("", "enviada", "enviada"), ("aceita", "entregue", "entregue"),
    ("lida", "entregue", "lida"), ("entregue", "enviada", "entregue"),
    ("enviada", "falhou", "falhou"), ("entregue", "falhou", "entregue"),
    ("lida", "falhou", "lida"), ("falhou", "entregue", "entregue"),
    ("falhou", "enviada", "falhou"),
])
def test_entrega_nunca_regride(atual, recebido, esperado):
    assert dominio.proxima_entrega(atual, recebido) == esperado


def test_espera_cresce_e_respeita_o_provedor():
    assert [dominio.espera(n).total_seconds() for n in (1, 2, 3)] == [120, 480, 1920]
    assert dominio.espera(1, 60) == timedelta(seconds=60)
    assert dominio.espera(1, 99999) == timedelta(hours=1)


def test_janela_de_24h():
    agora = datetime(2026, 10, 18, 12, tzinfo=UTC)
    assert dominio.janela_aberta(agora - timedelta(hours=23), agora)
    assert not dominio.janela_aberta(agora - timedelta(hours=24), agora)
    assert not dominio.janela_aberta(None, agora)


@pytest.mark.parametrize("texto,intencao", [
    ("SAIR", "sair"), (" parar. ", "sair"), ("Aceito", "aceito"), ("aceito!", "aceito"),
    ("Olá", "ajuda"), ("não quero sair", ""), ("segue o comprovante", ""), ("", ""),
])
def test_intencao(texto, intencao):
    assert dominio.intencao(texto) == intencao


def test_nome_seguro():
    assert dominio.nome_seguro("../../etc/passwd", ".pdf") == "passwd.pdf"
    assert dominio.nome_seguro("C:\\x\\comprovante.exe", ".pdf") == "comprovante.pdf"
    assert dominio.nome_seguro("", ".png") == "arquivo.png"


def test_chave_do_recebimento_cabe_em_200_para_ids_de_ate_300():
    assert dominio.chave_recebimento("whatsapp", "wamid.CURTO", 1) == "receb:whatsapp:wamid.CURTO:1"
    longo = "wamid." + "x" * 294
    chave = dominio.chave_recebimento("whatsapp", longo, 0)
    assert len(chave) <= 200 and chave.startswith("receb#sha256:whatsapp:")
    imitacao = "sha256:" + chave.split(":")[2]  # id curto que imita a forma com hash
    assert dominio.chave_recebimento("whatsapp", imitacao, 0) != chave
    assert chave == dominio.chave_recebimento("whatsapp", longo, 0)  # estável
    assert chave != dominio.chave_recebimento("whatsapp", longo, 1)
    emoji = dominio.chave_recebimento("whatsapp", "wamid.😀", 0)
    assert emoji.startswith("receb#sha256:whatsapp:") and emoji.isascii()
