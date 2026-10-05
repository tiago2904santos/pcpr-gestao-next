"""Fonte da Agenda: os deadlines dos atendimentos à imprensa (paridade com a fonte
"imprensa" da agenda da referência). O atendimento encerrado (atendido ou não responder)
entra como encerrado — escondido por padrão."""

from __future__ import annotations

from datetime import date

from django.urls import reverse
from django.utils import timezone

from gestao.plataforma.agenda import Compromisso, Fonte, registrar_fonte

from . import dominio, policies
from .models import Atendimento


def _deadlines(usuario, inicio: date, fim: date) -> list[Compromisso]:
    hoje = timezone.localdate()
    saida = []
    for a in (Atendimento.objects.filter(deadline__gte=inicio, deadline__lte=fim)
              .select_related("veiculo", "responsavel").order_by("deadline", "pk")):
        if a.deadline is None:  # filtrado acima
            continue
        selo = dominio.selo_do_deadline(a.deadline, a.situacao, hoje)
        saida.append(Compromisso(
            fonte="imprensa", chave=f"imprensa-{a.pk}", titulo=f"Deadline — {a.titulo}",
            inicio=a.deadline, prazo=True, encerrado=not a.aberto,
            situacao=a.get_situacao_display() if not a.aberto or selo is None
            else ("Vencido" if selo.tom == "perigo" else a.get_situacao_display()),
            tom=selo.tom if selo else a.tom,
            url=reverse("imprensa:atendimento", args=[a.pk]),
            detalhes=(("Jornalista", a.jornalista),
                      ("Veículo", a.veiculo.nome if a.veiculo else ""),
                      ("Pedido", a.pedido_resumo),
                      ("Responsável", a.responsavel.nome if a.responsavel else ""),
                      ("Situação", a.get_situacao_display()))))
    return saida


def registrar() -> None:
    registrar_fonte(Fonte("imprensa", "Deadlines da imprensa", policies.pode_acessar,
                          _deadlines, ordem=30))
