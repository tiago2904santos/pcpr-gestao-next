from __future__ import annotations

import pytest
from django.db import transaction

from gestao.plataforma import outbox
from gestao.plataforma.models import MensagemOutbox

pytestmark = pytest.mark.django_db(transaction=True)

RECEBIDAS: list[dict] = []


@outbox.assinante("teste.ok")
def _ok(payload):
    RECEBIDAS.append(payload)


@outbox.assinante("teste.falha")
def _falha(payload):
    raise RuntimeError("serviço externo fora do ar")


def test_publicar_exige_transacao():
    with pytest.raises(outbox.OutboxForaDeTransacao):
        outbox.publicar("teste.ok", {}, chave="x")


def test_mensagem_some_junto_com_rollback():
    with pytest.raises(ZeroDivisionError), transaction.atomic():
        outbox.publicar("teste.ok", {"a": 1}, chave="rollback-1")
        1 / 0  # noqa: B018
    assert not MensagemOutbox.objects.filter(chave_idempotencia="rollback-1").exists()


def test_entrega_e_idempotencia_da_publicacao():
    RECEBIDAS.clear()
    with transaction.atomic():
        outbox.publicar("teste.ok", {"oficio": 7}, chave="ok-7")
        outbox.publicar("teste.ok", {"oficio": 7}, chave="ok-7")  # duplicada: ignorada
    assert MensagemOutbox.objects.filter(chave_idempotencia="ok-7").count() == 1
    assert outbox.processar_lote() == 1
    assert RECEBIDAS == [{"oficio": 7}]
    m = MensagemOutbox.objects.get(chave_idempotencia="ok-7")
    assert m.situacao == MensagemOutbox.Situacao.PROCESSADA and m.processada_em


def test_falha_agenda_nova_tentativa_e_desiste_apos_limite():
    with transaction.atomic():
        outbox.publicar("teste.falha", {}, chave="falha-1")
    outbox.processar_lote()
    m = MensagemOutbox.objects.get(chave_idempotencia="falha-1")
    assert m.situacao == MensagemOutbox.Situacao.PENDENTE
    assert m.tentativas == 1 and "fora do ar" in m.ultimo_erro
    assert outbox.processar_lote() == 0  # backoff: ainda não disponível

    MensagemOutbox.objects.filter(pk=m.pk).update(tentativas=outbox.MAX_TENTATIVAS - 1,
                                                  disponivel_em=m.criada_em)
    outbox.processar_lote()
    m.refresh_from_db()
    assert m.situacao == MensagemOutbox.Situacao.FALHOU
