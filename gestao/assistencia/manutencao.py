"""Retenção da assistência: o conteúdo (orientações escritas, textos sugeridos, avisos e
texto aplicado) sai depois do prazo (`ASSISTENCIA_RETENCAO_DIAS`, padrão 30). Fica o
registro de que houve o pedido e a sugestão (estado, uso, modelo, tokens, custo estimado,
decisão) — e o texto que a pessoa aceitou continua no registro de negócio, com a trilha dele.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .models import ConteudoPedido, ConteudoSugestao


def purgar(agora=None) -> dict[str, int]:
    agora = agora or timezone.now()
    with transaction.atomic():
        pedidos = ConteudoPedido.objects.filter(expira_em__lte=agora).delete()[0]
        sugestoes = ConteudoSugestao.objects.filter(expira_em__lte=agora).delete()[0]
    return {"orientacoes": pedidos, "sugestoes": sugestoes}


def diaria(hoje=None) -> str:
    from .orcamento import GLOBAL, garantir, liberar_reservas_presas

    garantir(GLOBAL)  # a linha do mês nasce aqui (as telas só leem)
    presas = liberar_reservas_presas()
    return f"retenção da assistência {purgar()}; {presas} reserva(s) presa(s) liberada(s)"
