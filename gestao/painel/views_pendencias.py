"""Pendências (aba da Agenda, ao lado do Calendário): o que espera o operador, de todos os
módulos — envios aos servidores, documentos para terminar, prestação de contas, solicitações
de evento, coffee break e exceções da automação. As seções e as permissões vêm de
`plataforma.pendencias` (cada contexto registra a sua); a tela só monta."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from gestao.plataforma import pendencias
from gestao.plataforma.pendencias import VISIVEIS


@require_GET
def pendencias_view(request: HttpRequest) -> HttpResponse:
    montadas = pendencias.montar(request.user, timezone.localdate())
    pedida = request.GET.get("secao") or ""
    secao = pedida if any(m.secao.slug == pedida for m in montadas) else ""
    escolhidas = [m for m in montadas if not secao or m.secao.slug == secao]
    return render(request, "painel/pendencias.html", {
        "abas": [("", "Todas", sum(m.total for m in montadas))]
                + [(m.secao.slug, m.secao.titulo, m.total) for m in montadas],
        "secao": secao, "total": sum(m.total for m in escolhidas),
        "titulo_resultados": escolhidas[0].secao.titulo if secao else "Tudo o que está pendente",
        # Na visão geral, as seções com algo vêm primeiro; as em dia, num resumo no fim.
        "com_pendencias": [m for m in escolhidas if m.total or m.erro or secao],
        "em_dia": [] if secao else [m for m in escolhidas if not m.total and not m.erro],
        "visiveis": None if secao else VISIVEIS,
        "voltar": request.get_full_path(),
        "migalhas": [("Início", reverse("painel:inicio")), ("Agenda", reverse("painel:agenda")),
                     ("Pendências", "")]})
