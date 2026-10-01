from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from gestao.plataforma.navegacao import navegacao_para
from gestao.viagens import policies as viagens_policies
from gestao.viagens import queries as viagens_queries
from gestao.viagens.services import buscar_por_texto

# Módulos do sistema de referência ainda não migrados (Fase 19: um módulo por vez).
FUTUROS = [
    {"rotulo": "Eventos Sociais", "icone": "calendar-days",
     "descricao": "Solicitações de eventos sociais e despacho da Diretoria-Geral."},
    {"rotulo": "Coffee Break", "icone": "receipt",
     "descricao": "Lotes contratados, solicitações e fluxo de pagamento."},
    {"rotulo": "ASCOM", "icone": "send",
     "descricao": "Palestras, publicações e atendimento à imprensa."},
]


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
def notificacoes(request: HttpRequest) -> HttpResponse:
    return render(request, "painel/notificacoes.html", {
        "migalhas": [("Início", reverse("painel:inicio")), ("Notificações", "")]})


@require_GET
def busca(request: HttpRequest) -> JsonResponse:
    """Resultados da paleta de comandos: ofícios visíveis ao usuário."""
    termo = (request.GET.get("q") or "").strip()
    resultados = []
    if len(termo) >= 2:
        qs = buscar_por_texto(viagens_policies.oficios_visiveis(request.user), termo)
        for o in qs.select_related("unidade").order_by("-ano", "-numero")[:8]:
            resultados.append({
                "titulo": f"Ofício {o.numero_formatado}",
                "meta": f"{o.get_situacao_display()} · {o.motivo[:60]}",
                "url": reverse("viagens:editar" if o.editavel else "viagens:detalhe",
                               args=[o.pk]),
                "grupo": "Ofícios", "icone": "file-text",
            })
    return JsonResponse({"resultados": resultados})


