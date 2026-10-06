"""Lembretes diários das solicitações de evento (paridade com `solicitacoes/lembretes.py`
da referência), no sino. Saem pela rotina diária (`plataforma.rotinas`), cada um uma vez só
por solicitação, tipo e data de referência (`Lembrete`): se a data muda, vale de novo.

- o responsável, do dia seguinte ao fim do evento deferido: confirmar o atendimento;
- a DG, quando um pedido aguarda despacho e o evento começa em até 7 dias;
- o responsável, quando a devolução para correção está parada há mais de 3 dias.

Só entram eventos e devoluções dos últimos 30 dias: na primeira rodada, os antigos
esquecidos não viram uma enxurrada de avisos (continuam na fila "Confirmar atendimento").
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.urls import reverse
from django.utils import timezone

from gestao.plataforma.notificacoes import notificar, usuarios_do_grupo

from . import dominio
from .models import Lembrete, Movimento, Solicitacao

DIAS_ANTES_DO_EVENTO = 7
DIAS_DEVOLUCAO_PARADA = 3
JANELA_DIAS = 30


def _registrar(s: Solicitacao, tipo: str, referencia: date) -> bool:
    """Grava o lembrete; False se ele já tinha sido enviado."""
    try:
        with transaction.atomic():
            _l, criado = Lembrete.objects.get_or_create(solicitacao=s, tipo=tipo,
                                                        referencia=referencia)
    except IntegrityError:  # outra rodada gravou no mesmo instante
        return False
    return criado


def _pendentes_de_confirmacao(hoje: date):
    janela = hoje - timedelta(days=JANELA_DIAS)
    return (Solicitacao.objects.filter(status=dominio.DEFERIDA)
            .filter(Q(data_fim_evento__lt=hoje, data_fim_evento__gte=janela)
                    | Q(data_fim_evento__isnull=True, data_inicio_evento__lt=hoje,
                        data_inicio_evento__gte=janela))
            .select_related("municipio", "criado_por"))


def _despachos_proximos(hoje: date):
    return (Solicitacao.objects.filter(
        status=dominio.AGUARDANDO, data_inicio_evento__gte=hoje,
        data_inicio_evento__lte=hoje + timedelta(days=DIAS_ANTES_DO_EVENTO))
        .select_related("municipio", "tipo_evento"))


def _devolucoes_paradas(hoje: date) -> Iterator[tuple[Solicitacao, date]]:
    limite = hoje - timedelta(days=DIAS_DEVOLUCAO_PARADA)
    candidatas = (Solicitacao.objects.filter(status=dominio.DEVOLVIDA)
                  .annotate(devolvida_em=Max("movimentos__em", filter=Q(
                      movimentos__acao=Movimento.Acao.DEVOLUCAO)))
                  .select_related("municipio", "criado_por"))
    for s in candidatas:
        em = getattr(s, "devolvida_em", None)
        if em is None:
            continue
        dia = timezone.localdate(em)
        if hoje - timedelta(days=JANELA_DIAS) <= dia < limite:
            yield s, dia


def _quando(faltam: int) -> str:
    return "hoje" if faltam == 0 else "amanhã" if faltam == 1 else f"em {faltam} dias"


def enviar_lembretes(hoje: date | None = None) -> dict[str, int]:
    """Avisa o que estiver pendente; devolve {tipo: quantidade}."""
    hoje = hoje or timezone.localdate()
    enviados = dict.fromkeys(Lembrete.Tipo.values, 0)

    def avisar(s: Solicitacao, tipo: str, referencia: date, destinatarios, titulo: str,
               mensagem: str, ancora: str = "") -> None:
        if not _registrar(s, tipo, referencia):
            return
        notificar(destinatarios, titulo, mensagem,
                  reverse("eventos:solicitacao", args=[s.pk]) + ancora)
        enviados[tipo] += 1

    for s in _pendentes_de_confirmacao(hoje):
        ultimo = s.data_fim_evento or s.data_inicio_evento
        if ultimo is None:  # filtrado acima
            continue
        local = s.municipio.nome if s.municipio else "município a definir"
        avisar(s, Lembrete.Tipo.CONFIRMAR_ATENDIMENTO, ultimo, [s.criado_por],
               f"Solicitação #{s.pk}: confirme o atendimento",
               f"O evento em {local} terminou em {ultimo:%d/%m/%Y}. Se foi atendido, marque a "
               "solicitação como atendida.", "#encerramento")

    gestores = list(usuarios_do_grupo("GESTOR_DG"))
    for s in _despachos_proximos(hoje):
        if s.data_inicio_evento is None:  # filtrado acima
            continue
        tipo = s.tipo_evento.nome if s.tipo_evento else "Evento"
        local = s.municipio.nome if s.municipio else "município a definir"
        avisar(s, Lembrete.Tipo.DESPACHO_PROXIMO, s.data_inicio_evento, gestores,
               f"Solicitação #{s.pk} aguarda despacho: evento "
               f"{_quando((s.data_inicio_evento - hoje).days)}",
               f"{tipo} em {local} começa em {s.data_inicio_evento:%d/%m/%Y}.", "#despacho")

    for s, dia in _devolucoes_paradas(hoje):
        avisar(s, Lembrete.Tipo.DEVOLUCAO_PARADA, dia, [s.criado_por],
               f"Solicitação #{s.pk} aguarda a sua correção",
               f"A Diretoria-Geral devolveu a solicitação em {dia:%d/%m/%Y}. Faça os ajustes "
               "pedidos e reenvie para o despacho.")
    return enviados
