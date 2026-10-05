"""Avisos diários da prestação de contas no sino da equipe de viagens (paridade com
`viagens_prestacoes/avisos.py` da referência). Saem pela rotina diária (plataforma.rotinas),
uma vez cada — o título leva o servidor, o ofício e a data, e o que já está no sino não se
repete. Vão para a equipe de viagens da unidade do ofício (decisão do agente, como os
outros avisos da prestação).

- Prazo de saque vencido / saque vence em N dias — sem comprovante anexado;
- Prestação vencida — passou dos 3 dias úteis depois do fim do saque;
- Documentos gerados (diário e RT prontos, falta o assinado voltar) e documentos assinados
  recebidos (os dois assinados anexados);
- A equipe chegou de viagem (até 36 h depois da chegada).
Fora: "amanhã sai a viagem" (fala do link do diário no celular, que não existe aqui).
"""

from __future__ import annotations

from datetime import date, timedelta

from django.urls import reverse
from django.utils import timezone

from gestao.plataforma.models import Notificacao
from gestao.plataforma.notificacoes import TITULO_MAX, _cabe, notificar, usuarios_do_grupo

from . import anexos
from .dominio import prestacao as dominio
from .models import Oficio, PrestacaoContas, PrestacaoServidor, Trecho

HORAS_AVISO_CHEGADA = 36


def _avisar_uma_vez(oficio: Oficio, titulo: str, mensagem: str, link: str) -> bool:
    if Notificacao.objects.filter(titulo=_cabe(titulo, TITULO_MAX), link=link).exists():
        return False
    return bool(notificar(usuarios_do_grupo("OPERADOR_VIAGENS")
                          .filter(lotacao__unidade=oficio.unidade_id), titulo, mensagem, link))


def _link(oficio: Oficio) -> str:
    return reverse("viagens:prestacoes") + f"?q={oficio.numero_formatado}"


def _plural_dias(n: int) -> str:
    return "hoje" if n == 0 else f"em {n} dia{'s' if n > 1 else ''}"


def avisar_prazos(hoje: date | None = None) -> int:
    hoje = hoje or timezone.localdate()
    enviados = 0
    servidores = list(
        PrestacaoServidor.objects.filter(finalizada_em__isnull=True, arquivada_em__isnull=True,
                                         removida_em__isnull=True,
                                         prestacao__oficio__situacao=Oficio.Situacao.EMITIDO)
        .select_related("servidor", "prestacao__oficio"))
    situacao = anexos.situacao({ps.prestacao_id for ps in servidores})
    for ps in servidores:
        oficio = ps.prestacao.oficio
        quem = f"{ps.servidor.nome} (Ofício {oficio.numero_formatado})"
        link = _link(oficio)
        prazo = ps.prazo_limite_saque
        if prazo and not situacao.comprovantes.get(ps.pk):
            faltam = (prazo - hoje).days
            if faltam < 0:
                enviados += _avisar_uma_vez(
                    oficio, f"Prazo de saque vencido: {quem} em {prazo:%d/%m}",
                    "Não há comprovante de saque ou transferência anexado.", link)
            elif faltam <= dominio.DIAS_AVISO_SAQUE:
                enviados += _avisar_uma_vez(
                    oficio, f"Saque vence {_plural_dias(faltam)}: {quem} ({prazo:%d/%m})",
                    "Lembre o servidor de sacar ou transferir as diárias.", link)
        limite = dominio.prazo_para_prestar(prazo)
        if limite and hoje > limite:
            enviados += _avisar_uma_vez(
                oficio, f"Prestação vencida: {quem} em {limite:%d/%m}",
                "Passaram os 3 dias úteis depois do fim do prazo de saque.", link)
        p = ps.prestacao_id
        diario_ass, rt_ass = p in situacao.db_assinados, ps.pk in situacao.rt_assinados
        if diario_ass and rt_ass:
            enviados += _avisar_uma_vez(
                oficio, f"Documentos assinados recebidos: {quem}",
                "Diário de bordo e relatório técnico assinados estão anexados.", link)
        elif ((diario_ass or p in situacao.diarios)
              and (rt_ass or p in situacao.relatorios)):
            enviados += _avisar_uma_vez(
                oficio, f"Documentos gerados: {quem}",
                "Diário e relatório técnico prontos: envie ao servidor para assinar.", link)
    return enviados


def avisar_chegadas(hoje: date | None = None) -> int:
    """"A equipe chegou de viagem": hora de começar a prestação (até 36 h depois)."""
    agora = timezone.now()
    enviados = 0
    recentes = (Trecho.objects.filter(oficio__situacao=Oficio.Situacao.EMITIDO,
                                      chegada_em__lte=agora,
                                      chegada_em__gte=agora - timedelta(hours=HORAS_AVISO_CHEGADA))
                .select_related("oficio").order_by("oficio_id", "-ordem"))
    vistos: set[int] = set()
    for trecho in recentes:
        if trecho.oficio_id in vistos:
            continue
        vistos.add(trecho.oficio_id)
        oficio = trecho.oficio
        if oficio.trechos.filter(ordem__gt=trecho.ordem).exists():
            continue  # ainda não é a volta
        if not PrestacaoContas.objects.filter(oficio=oficio).exists():
            continue
        quando = timezone.localtime(trecho.chegada_em)
        enviados += _avisar_uma_vez(
            oficio, f"A equipe do Ofício {oficio.numero_formatado} chegou de viagem "
                    f"({quando:%d/%m %H:%M})",
            "Hora de começar a prestação de contas: diário de bordo, relatório técnico e "
            "comprovantes.", _link(oficio))
    return enviados
