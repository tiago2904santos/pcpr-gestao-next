from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from gestao.plataforma import busca as busca_global
from gestao.plataforma.navegacao import navegacao_para
from gestao.viagens import policies as viagens_policies
from gestao.viagens import queries as viagens_queries

# Módulos do sistema de referência ainda não migrados (Fase 19: um módulo por vez).
# Todos os módulos da referência já têm entrada aqui (o Coffee Break desde a CB2).
FUTUROS: list[dict[str, str]] = []


@require_GET
def inicio(request: HttpRequest) -> HttpResponse:
    modulos = navegacao_para(request)["modulos"]
    for m in modulos:
        if m["chave"] == "viagens":
            ind = viagens_queries.indicadores_do_painel(
                viagens_policies.oficios_visiveis(request.user))
            m["indicadores"] = [("No mês", ind["oficios_mes"], False),
                                ("Rascunhos", ind["rascunhos"], bool(ind["rascunhos"])),
                                ("Em 30 dias", ind["viagens_30_dias"], False)]
    return render(request, "painel/inicio.html", {"modulos": modulos, "futuros": FUTUROS})


@require_GET
def busca(request: HttpRequest) -> JsonResponse:
    """Resultados da paleta de comandos: as fontes que cada módulo registrou
    (`plataforma.busca`), só as que a pessoa pode ver."""
    return JsonResponse({"resultados": busca_global.buscar(request.user,
                                                           request.GET.get("q") or "")})


