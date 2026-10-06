"""Fonte da busca global (Ctrl+K) do Coffee Break (CB7a): as OS pelo número, pelo evento,
pela nota fiscal ou pelo protocolo de pagamento — só para quem tem o módulo."""

from __future__ import annotations

from django.db.models import Q
from django.urls import reverse

from gestao.plataforma.busca import Fonte, Resultado, registrar_fonte

from . import policies
from .models import Solicitacao


def _ordens(usuario, termo: str, limite: int) -> list[Resultado]:
    qs = (Solicitacao.objects.filter(
        Q(numero__icontains=termo) | Q(descricao__unaccent__icontains=termo)
        | Q(nota_fiscal__icontains=termo) | Q(protocolo_pagamento__icontains=termo))
        .select_related("municipio").order_by("-data_solicitacao", "-pk")[:limite])
    return [Resultado(f"OS {s.numero or '—'} · {' '.join(s.descricao.split())[:60]}",
                      reverse("coffee:solicitacao", args=[s.pk]),
                      " · ".join(p for p in (s.situacao_rotulo,
                                             f"{s.data_evento:%d/%m/%Y}" if s.data_evento
                                             else "", s.municipio.nome) if p), "receipt")
            for s in qs]


def registrar() -> None:
    registrar_fonte(Fonte("coffee", "Coffee break", policies.pode_acessar, _ordens, ordem=40))
