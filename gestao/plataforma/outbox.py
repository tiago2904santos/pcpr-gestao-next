"""Outbox transacional.

Uso (sempre dentro de `transaction.atomic()`):

    publicar("oficio.emitido", {"oficio_id": 1}, chave="oficio.emitido:1:v1")

e, em algum módulo carregado no `ready()` do app:

    @assinante("oficio.emitido")
    def gerar_pdf(payload): ...

O worker `manage.py processar_outbox` entrega cada mensagem ao assinante.
Assinantes DEVEM ser idempotentes: a entrega é "pelo menos uma vez".
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from django.db import connection, transaction
from django.utils import timezone

from .models import MensagemOutbox

log = logging.getLogger(__name__)

Assinante = Callable[[dict[str, Any]], None]
_ASSINANTES: dict[str, Assinante] = {}
MAX_TENTATIVAS = 8


class OutboxForaDeTransacao(RuntimeError):
    pass


def assinante(topico: str) -> Callable[[Assinante], Assinante]:
    def registrar(func: Assinante) -> Assinante:
        if topico in _ASSINANTES and _ASSINANTES[topico] is not func:
            raise ValueError(f"Tópico já possui assinante: {topico}")
        _ASSINANTES[topico] = func
        return func

    return registrar


def publicar(topico: str, payload: dict[str, Any], *, chave: str) -> MensagemOutbox:
    if not connection.in_atomic_block:
        raise OutboxForaDeTransacao(
            "publicar() precisa rodar na mesma transação da mudança de negócio."
        )
    mensagem, _ = MensagemOutbox.objects.get_or_create(
        chave_idempotencia=chave,
        defaults={"topico": topico, "payload": payload, "disponivel_em": timezone.now()},
    )
    transaction.on_commit(_notificar_worker)
    return mensagem


def _notificar_worker() -> None:
    with connection.cursor() as cur:
        cur.execute("NOTIFY outbox")


def _backoff(tentativas: int) -> timedelta:
    return timedelta(seconds=min(2**tentativas * 5, 3600))


def processar_lote(limite: int = 20) -> int:
    """Processa até `limite` mensagens disponíveis. Retorna quantas tratou."""
    tratadas = 0
    for _ in range(limite):
        with transaction.atomic():
            mensagem = (
                MensagemOutbox.objects.select_for_update(skip_locked=True)
                .filter(situacao=MensagemOutbox.Situacao.PENDENTE,
                        disponivel_em__lte=timezone.now())
                .order_by("disponivel_em", "id")
                .first()
            )
            if mensagem is None:
                break
            tratadas += 1
            func = _ASSINANTES.get(mensagem.topico)
            mensagem.tentativas += 1
            try:
                if func is None:
                    raise LookupError(f"Nenhum assinante para '{mensagem.topico}'")
                with transaction.atomic():  # savepoint: falha não desfaz o registro da tentativa
                    func(mensagem.payload)
            except Exception as exc:
                log.exception("Falha na mensagem %s (%s)", mensagem.pk, mensagem.topico)
                mensagem.ultimo_erro = f"{type(exc).__name__}: {exc}"[:2000]
                if mensagem.tentativas >= MAX_TENTATIVAS:
                    mensagem.situacao = MensagemOutbox.Situacao.FALHOU
                else:
                    mensagem.disponivel_em = timezone.now() + _backoff(mensagem.tentativas)
            else:
                mensagem.situacao = MensagemOutbox.Situacao.PROCESSADA
                mensagem.processada_em = timezone.now()
                mensagem.ultimo_erro = ""
            mensagem.save()
    return tratadas
