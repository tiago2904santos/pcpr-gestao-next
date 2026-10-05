"""Fonte da Agenda: as palestras e eventos com data (paridade com a fonte "demanda" da
agenda da referência). A cancelada entra como encerrada (escondida por padrão)."""

from __future__ import annotations

from datetime import date

from django.db.models import Q
from django.urls import reverse

from gestao.plataforma.agenda import Compromisso, Fonte, registrar_fonte

from . import policies
from .models import Palestra


def _palestras(usuario, inicio: date, fim: date) -> list[Compromisso]:
    saida = []
    consulta = (Palestra.objects.filter(data_inicio_evento__lte=fim)
                .filter(Q(data_fim_evento__gte=inicio)
                        | Q(data_fim_evento__isnull=True, data_inicio_evento__gte=inicio))
                .select_related("municipio").prefetch_related("palestrantes", "temas")
                .order_by("data_inicio_evento", "hora_inicio", "pk"))
    for p in consulta:
        if p.data_inicio_evento is None:  # filtrado acima
            continue
        saida.append(Compromisso(
            fonte="palestra", chave=f"palestra-{p.pk}",
            titulo=f"{p.titulo} — {p.solicitante}", inicio=p.data_inicio_evento,
            fim=p.data_fim_evento, hora=f"{p.hora_inicio:%H:%M}" if p.hora_inicio else "",
            situacao=p.get_status_display(), tom=p.tom,
            encerrado=p.status == Palestra.Status.CANCELADA,
            url=reverse("palestras:palestra", args=[p.pk]),
            detalhes=(("Solicitante", p.solicitante), ("Local", p.local),
                      ("Palestrantes", ", ".join(x.nome for x in p.palestrantes.all())),
                      ("Temas", ", ".join(t.nome for t in p.temas.all())),
                      ("Status", p.get_status_display()))))
    return saida


def registrar() -> None:
    registrar_fonte(Fonte("palestra", "Palestras e eventos", policies.pode_acessar,
                          _palestras, ordem=32))
