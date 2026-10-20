"""A porta pública dos links pessoais (`/p/<token>/`): sem login, confere o link e entrega à
página do escopo registrada pelo contexto dono (ex.: o km do diário, em Viagens).

Link desconhecido, vencido ou revogado: a mesma página "Link indisponível" (404). Quem erra
tokens demais leva 429 sem nem consultar o banco.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_not_required
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from gestao.plataforma import recursos
from gestao.plataforma.middleware import ip_do_cliente

from . import links
from .models import LinkAcesso

TENTATIVAS_INVALIDAS_POR_HORA = 20


def cabecalhos(resposta: HttpResponse) -> HttpResponse:
    resposta["Referrer-Policy"] = "no-referrer"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    resposta["Cache-Control"] = "no-store"
    return resposta


def indisponivel(request: HttpRequest, status: int = 404) -> HttpResponse:
    return cabecalhos(render(request, "automacao/publico/indisponivel.html",
                             {"limite": status == 429}, status=status))


def _chave(request: HttpRequest) -> str:
    return f"link-acesso-invalido:{links.origem(ip_do_cliente(request) or '')}"


def _contar(chave: str) -> int:
    if cache.add(chave, 1, 3600):
        return 1
    try:
        return cache.incr(chave)
    except ValueError:
        cache.set(chave, 1, 3600)
        return 1


@login_not_required
@never_cache
@require_http_methods(["GET", "POST"])
def abrir(request: HttpRequest, token: str, resto: str = "") -> HttpResponse:
    if (cache.get(_chave(request)) or 0) >= TENTATIVAS_INVALIDAS_POR_HORA:
        return indisponivel(request, 429)
    link = links.do_token(token)
    pagina = links.pagina(link.escopo) if link else None
    # Automações desligadas (ADR 0050): só o link de KM, que vai no envio manual, segue aberto.
    if (link is not None and link.escopo != LinkAcesso.Escopo.KM
            and not recursos.ligado(recursos.AUTOMACAO)):
        pagina = None
    if link is None or pagina is None:
        _contar(_chave(request))
        return indisponivel(request)
    links.registrar_uso(link)
    request.link_acesso = link  # type: ignore[attr-defined]
    return cabecalhos(pagina.view(request, link, resto))
