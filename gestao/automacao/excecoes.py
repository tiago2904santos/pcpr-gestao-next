"""Fila de exceções: o que a automação não resolve sozinha vai para uma pessoa.

Uma exceção por (tipo, assunto) — abrir de novo a mesma reabre a existente em vez de
duplicar. Resolver sempre diz o que foi feito (`resolucao`), e as ações que mexem no
assunto (reenviar, associar, descartar) ficam nos serviços de cada um.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from gestao.plataforma.notificacoes import notificar

from . import policies
from .models import ExcecaoAutomacao

ABERTA = ExcecaoAutomacao.Situacao.ABERTA


def _cabe(texto: str, limite: int = 255) -> str:
    texto = " ".join((texto or "").split())
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


def abrir(tipo: str, chave: str, resumo: str, *, comunicacao=None, recebimento=None,
          unidade_id: int | None = None, avisar: bool = True) -> ExcecaoAutomacao:
    """Dentro da transação de quem achou o problema. Avisa no sino só quando a exceção
    nasce ou é reaberta (repetir o mesmo problema não repete o aviso)."""
    excecao, criada = ExcecaoAutomacao.objects.get_or_create(
        chave=chave[:200], defaults={
            "tipo": tipo, "resumo": _cabe(resumo), "comunicacao": comunicacao,
            "recebimento": recebimento, "unidade_id": unidade_id})
    reaberta = False
    if not criada and excecao.situacao != ABERTA:
        excecao.situacao, excecao.resumo = ABERTA, _cabe(resumo)
        excecao.resolvida_em = None
        excecao.resolvida_por = None
        excecao.resolucao = ""
        excecao.save()
        reaberta = True
    if avisar and (criada or reaberta):
        _avisar(excecao)
    return excecao


def quem_opera(unidade_id: int | None):
    """Quem opera a automação na unidade, mais quem administra (vê todas)."""
    grupos = "groups__permissions__"
    operar = Q(**{f"{grupos}codename": "operar_automacao",
                  f"{grupos}content_type__app_label": "automacao"})
    administrar = Q(**{f"{grupos}codename": "administrar_automacao",
                       f"{grupos}content_type__app_label": "automacao"})
    da_unidade = Q(lotacao__unidade=unidade_id) if unidade_id else Q(pk__in=[])
    return (get_user_model().objects.filter(is_active=True)
            .filter((operar & da_unidade) | administrar).distinct())


def _avisar(excecao: ExcecaoAutomacao) -> None:
    from django.urls import reverse

    notificar(quem_opera(excecao.unidade_id), f"Automação: {excecao.get_tipo_display()}",
              excecao.resumo,
              reverse("automacao:excecao", args=[excecao.pk]))


@transaction.atomic
def assumir(usuario, pk: int) -> ExcecaoAutomacao:
    excecao = ExcecaoAutomacao.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_operar_objeto(usuario, excecao))
    if excecao.situacao != ABERTA:
        raise ValueError("Esta exceção já foi tratada.")
    excecao.responsavel, excecao.assumida_em = usuario, timezone.now()
    excecao.save(update_fields=["responsavel", "assumida_em"])
    return excecao


def encerrar(excecao: ExcecaoAutomacao, usuario, resolucao: str, *,
             descartar: bool = False) -> ExcecaoAutomacao:
    """Dentro da transação da ação que resolveu (que já conferiu a permissão)."""
    if excecao.situacao != ABERTA:
        return excecao
    excecao.situacao = (ExcecaoAutomacao.Situacao.DESCARTADA if descartar
                        else ExcecaoAutomacao.Situacao.RESOLVIDA)
    excecao.resolucao = _cabe(resolucao)
    excecao.resolvida_por, excecao.resolvida_em = usuario, timezone.now()
    if excecao.responsavel_id is None:
        excecao.responsavel = usuario
    excecao.save()
    return excecao


def encerrar_do_assunto(*, comunicacao=None, recebimento=None, usuario=None,
                        resolucao: str) -> int:
    """Fecha as exceções abertas de uma comunicação/recebimento que se resolveu."""
    qs = ExcecaoAutomacao.objects.select_for_update().filter(situacao=ABERTA)
    if comunicacao is not None:
        qs = qs.filter(comunicacao=comunicacao)
    if recebimento is not None:
        qs = qs.filter(recebimento=recebimento)
    total = 0
    for excecao in qs:
        encerrar(excecao, usuario, resolucao)
        total += 1
    return total
