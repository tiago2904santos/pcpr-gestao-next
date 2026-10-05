"""Fonte da Agenda: as pautas, no dia da pauta (paridade com a fonte "pauta" da agenda da
referência). Pauta é compromisso, não prazo: a situação é o status; a cancelada entra como
encerrada (escondida por padrão)."""

from __future__ import annotations

from datetime import date

from django.urls import reverse

from gestao.plataforma.agenda import Compromisso, Fonte, registrar_fonte

from . import policies
from .models import Publicacao


def _pautas(usuario, inicio: date, fim: date) -> list[Compromisso]:
    saida = []
    for p in (Publicacao.objects.filter(data__gte=inicio, data__lte=fim)
              .select_related("jornalista", "unidade").order_by("data", "inicio_pauta", "pk")):
        saida.append(Compromisso(
            fonte="pauta", chave=f"pauta-{p.pk}", titulo=f"Pauta — {p.titulo}", inicio=p.data,
            hora=f"{p.inicio_pauta:%H:%M}" if p.inicio_pauta else "",
            situacao=p.get_status_display(), tom=p.tom,
            encerrado=p.status == Publicacao.Status.CANCELADA,
            meu=p.criado_por_id == getattr(usuario, "pk", None),
            pessoas=(p.jornalista.nome,),
            url=reverse("publicacoes:pauta", args=[p.pk]),
            detalhes=(("Jornalista", p.jornalista.nome),
                      ("Unidade", p.unidade.nome if p.unidade else ""),
                      ("Fonte", p.fonte), ("Status", p.get_status_display()),
                      ("Publicação", p.quando_publicada))))
    return saida


def registrar() -> None:
    registrar_fonte(Fonte("pauta", "Pautas", policies.pode_acessar, _pautas, ordem=31))
