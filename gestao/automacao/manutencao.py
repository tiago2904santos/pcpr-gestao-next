"""Manutenção da automação: o que vence sozinho e o que a retenção apaga.

- `expirar_vencidas`: agendadas que passaram da validade viram "expirada" mesmo com as
  chaves desligadas (é registro, não efeito) — senão, ao religar, sairia aviso velho;
- `reconciliar`: status que chegaram para mensagem que não conhecemos (depois de 1 h, sem a
  resposta do envio ter aparecido) vão para a fila de exceções;
- `purgar`: texto das mensagens, nome de perfil, corpo bruto dos webhooks e arquivos em
  quarentena saem depois do prazo de retenção (`AUTOMACAO_RETENCAO_DIAS`, padrão 30) — e a
  mídia que o simulador guardou e ninguém baixou (o download apaga a que consome). O
  registro de que houve a mensagem fica.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import CharField, Exists, OuterRef, Q, Value
from django.db.models.functions import Concat
from django.utils import timezone

from . import excecoes
from .models import (
    Comunicacao,
    ContadorDeLimite,
    ConteudoComunicacao,
    ConteudoRecebimento,
    EntradaWebhook,
    ExcecaoAutomacao,
    Recebimento,
    StatusEntrega,
)

S = Comunicacao.Situacao


@transaction.atomic
def expirar_vencidas() -> int:
    agora = timezone.now()
    return (Comunicacao.objects.filter(situacao__in=(S.AGENDADA, S.AGUARDANDO_APROVACAO),
                                       expira_em__lte=agora)
            .update(situacao=S.EXPIRADA, atualizada_em=agora,
                    motivo="Passou do prazo sem sair (chave desligada ou aguardando)."))


@transaction.atomic
def reconciliar() -> int:
    limite = timezone.now() - timedelta(hours=1)
    total = 0
    # Status órfão que já tem exceção (aberta OU resolvida) não entra de novo: sem isso os
    # mesmos 50 voltavam a cada passada e a exceção resolvida reabria 5 minutos depois.
    ja_tem = ExcecaoAutomacao.objects.filter(
        chave=Concat(Value("orfao:"), OuterRef("mensagem_id"), output_field=CharField()))
    for s in (StatusEntrega.objects
              .filter(comunicacao__isnull=True, registrado_em__lt=limite,
                      status__in=("enviada", "entregue", "lida", "falhou"))
              .exclude(Exists(ja_tem))
              .order_by("mensagem_id").distinct("mensagem_id")[:50]):
        excecoes.abrir(ExcecaoAutomacao.Tipo.STATUS_ORFAO, f"orfao:{s.mensagem_id}",
                       "A Meta informou o status de uma mensagem que o sistema não reconhece "
                       f"({s.status}). Confira se houve envio por fora do sistema.",
                       avisar=False)
        total += 1
    return total


def purgar(agora=None) -> dict[str, int]:
    agora = agora or timezone.now()
    from .entrega import retencao

    limite = agora - retencao()
    with transaction.atomic():
        textos = ConteudoComunicacao.objects.filter(expira_em__lte=agora).delete()[0]
        recebidos = ConteudoRecebimento.objects.filter(expira_em__lte=agora).delete()[0]
        from .models_api import RegistroIdempotencia

        respostas = RegistroIdempotencia.objects.filter(criado_em__lte=agora - timedelta(
            days=7)).delete()[0]
        # A da reserva guarda só ids (a repetição remonta a resposta): passa do lease, some.
        respostas += RegistroIdempotencia.objects.filter(
            rota__endswith="/reservar", criado_em__lte=agora - timedelta(hours=1)).delete()[0]
        ContadorDeLimite.objects.filter(inicio__lt=agora - timedelta(days=1)).delete()
        corpos = EntradaWebhook.objects.filter(
            ~Q(corpo=b""), recebida_em__lte=limite,
            situacao__in=(EntradaWebhook.Situacao.PROCESSADA, EntradaWebhook.Situacao.ERRO)
        ).update(corpo=b"")
    arquivos = 0
    for r in Recebimento.objects.filter(registrado_em__lte=limite).exclude(arquivo=""):
        r.arquivo.delete(save=False)  # a cópia que entrou no registro fica no registro
        Recebimento.objects.filter(pk=r.pk).update(arquivo="")
        arquivos += 1
    return {"textos": textos, "recebidos": recebidos, "corpos": corpos, "arquivos": arquivos,
            "respostas_api": respostas, "midia_simulada": _purgar_midia_simulada(limite)}


def _purgar_midia_simulada(limite) -> int:
    """Mídia do simulador que nunca foi baixada (remetente em quarentena, tentativas
    esgotadas): sai com o mesmo prazo de retenção dos arquivos recebidos."""
    from django.core.files.storage import default_storage

    from gestao.integracoes.whatsapp.adaptadores import PREFIXO_SIMULADO

    try:
        _, nomes = default_storage.listdir(PREFIXO_SIMULADO)
    except (FileNotFoundError, NotImplementedError):
        return 0
    total = 0
    for nome in nomes:
        caminho = PREFIXO_SIMULADO + nome
        try:
            if default_storage.get_modified_time(caminho) > limite:
                continue
        except (NotImplementedError, OSError):
            continue
        default_storage.delete(caminho)
        total += 1
    return total


def diaria(hoje=None) -> str:
    from . import ferramentas

    vencidas = expirar_vencidas()
    pedidos = ferramentas.expirar_vencidos()
    orfaos = reconciliar()
    apagados = purgar()
    return (f"{vencidas} expirada(s), {pedidos} aprovação(ões) vencida(s), {orfaos} órfão(s), "
            f"retenção {apagados}")
