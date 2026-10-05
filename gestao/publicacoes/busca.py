"""Pautas na busca global: título, fonte ou unidade."""

from __future__ import annotations

from django.db.models import Q
from django.urls import reverse

from gestao.plataforma.busca import Fonte, Resultado, registrar_fonte

from . import policies
from .models import Publicacao


def _pautas(usuario, termo: str, limite: int) -> list[Resultado]:
    qs = (Publicacao.objects.select_related("unidade")
          .filter(Q(titulo__unaccent__icontains=termo) | Q(fonte__unaccent__icontains=termo)
                  | Q(unidade__nome__unaccent__icontains=termo))
          .order_by("-data", "-pk")[:limite])
    return [Resultado(p.titulo, reverse("publicacoes:pauta", args=[p.pk]),
                      f"{p.get_status_display()} · {p.data:%d/%m/%Y}"
                      + (f" · {p.unidade.nome}" if p.unidade else ""), "newspaper") for p in qs]


def registrar() -> None:
    registrar_fonte(Fonte("pautas", "Pautas", policies.pode_acessar, _pautas, ordem=31))
