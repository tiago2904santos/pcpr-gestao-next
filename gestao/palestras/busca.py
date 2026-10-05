"""Palestras e eventos na busca global: solicitante, local, município ou palestrante."""

from __future__ import annotations

from django.db.models import Q
from django.urls import reverse

from gestao.plataforma.busca import Fonte, Resultado, registrar_fonte

from . import policies
from .models import Palestra


def _palestras(usuario, termo: str, limite: int) -> list[Resultado]:
    ids = Palestra.objects.filter(
        Q(solicitante__unaccent__icontains=termo) | Q(local__unaccent__icontains=termo)
        | Q(municipio__nome__unaccent__icontains=termo)
        | Q(palestrantes__nome__unaccent__icontains=termo)).values("pk")
    qs = (Palestra.objects.select_related("municipio").filter(pk__in=ids)
          .order_by("-data_solicitacao", "-pk")[:limite])
    return [Resultado(f"{p.titulo} — {p.solicitante}", reverse("palestras:palestra", args=[p.pk]),
                      " · ".join(x for x in (p.get_status_display(), p.periodo) if x),
                      "presentation") for p in qs]


def registrar() -> None:
    registrar_fonte(Fonte("palestras", "Palestras e eventos", policies.pode_acessar,
                          _palestras, ordem=32))
