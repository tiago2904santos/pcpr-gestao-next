"""Painel de Eventos Sociais (E3): indicadores, próximos eventos, últimas solicitações, a
série mensal e o despacho da DG — tudo sobre as solicitações que a pessoa vê."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from . import painel, pedir_coffee, policies, queries


@require_GET
def painel_eventos(request: HttpRequest) -> HttpResponse:
    if not policies.pode_criar(request.user):
        raise PermissionDenied
    hoje = timezone.localdate()
    try:
        meses = int(request.GET.get("meses") or 12)
    except ValueError:
        meses = 12
    if meses not in painel.PERIODOS:
        meses = 12
    r = painel.resumo(request.user, hoje)
    base = queries.base(request.user)
    proximos = painel.proximos(base, hoje).order_by("data_inicio_evento", "pk")[:7]
    ultimas = base.order_by("-criado_em", "-pk")[:6]

    def linhas(qs) -> list[queries.Linha]:
        saida = [queries.linha(s, hoje) for s in qs]
        for linha in saida:  # o "Pedir coffee break" do ⋮, como na lista
            linha.coffee = pedir_coffee.url(request.user, linha.s)
        return saida

    return render(request, "eventos/painel.html", {
        "r": r, "menos": abs(r.diferenca),
        "proximos": linhas(proximos), "ultimas": linhas(ultimas),
        "pode_despachar": policies.pode_despachar(request.user),
        "grafico": painel.serie_mensal(request.user, hoje, meses), "meses": meses,
        "periodos": painel.PERIODOS,
        "despacho": painel.despacho(request.user, hoje, r.aguardando),
        "pode_gerir_cadastros": request.user.has_perm("eventos.change_textodespacho"),
        "migalhas": [("Início", reverse("painel:inicio")), ("Eventos Sociais", "")],
    })
