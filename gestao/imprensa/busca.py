"""Atendimentos à imprensa na busca global: jornalista, veículo, pedido ou contato."""

from __future__ import annotations

from django.db.models import Q
from django.urls import reverse

from gestao.plataforma.busca import Fonte, Resultado, registrar_fonte

from . import policies
from .models import Atendimento


def _atendimentos(usuario, termo: str, limite: int) -> list[Resultado]:
    qs = (Atendimento.objects.select_related("veiculo")
          .filter(Q(jornalista__unaccent__icontains=termo) | Q(veiculo__nome__icontains=termo)
                  | Q(pedido__unaccent__icontains=termo) | Q(contato__icontains=termo))
          .order_by("-data", "-pk")[:limite])
    return [Resultado(a.titulo, reverse("imprensa:atendimento", args=[a.pk]),
                      f"{a.get_situacao_display()} · {a.data:%d/%m/%Y} · {a.pedido_resumo[:50]}",
                      "megaphone") for a in qs]


def registrar() -> None:
    registrar_fonte(Fonte("imprensa", "Atendimentos à imprensa", policies.pode_acessar,
                          _atendimentos, ordem=30))
