"""A página pública do link do fornecedor (sem login): a OS em poucas linhas, a situação da
nota e das certidões e o envio dos PDFs. Nada de dado da equipe aparece; o token não volta
em tela. Link desconhecido, vencido ou revogado: a mesma página "Link indisponível" (404);
tentativas demais de tokens inválidos ou de envios: 429."""

from __future__ import annotations

from datetime import datetime

from django.contrib.auth.decorators import login_not_required
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from . import dominio_certidoes, link_fornecedor
from .models import EnvioFornecedor
from .pedidos import PedidoInvalido

TENTATIVAS_INVALIDAS_POR_HORA = 20
SESSAO = "coffee_fornecedor_recebido"


def _ip(request: HttpRequest) -> str:
    return request.META.get("REMOTE_ADDR", "")


def _cabecalhos(resposta: HttpResponse) -> HttpResponse:
    resposta["Referrer-Policy"] = "no-referrer"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    return resposta


def _indisponivel(request: HttpRequest) -> HttpResponse:
    chave = f"coffee-link-invalido:{link_fornecedor.origem(_ip(request))}"
    tentativas = cache.get(chave, 0) + 1
    cache.set(chave, tentativas, 3600)
    status = 429 if tentativas > TENTATIVAS_INVALIDAS_POR_HORA else 404
    return _cabecalhos(render(request, "coffee/publico/indisponivel.html", status=status))


def _data(texto: str):
    try:
        return datetime.strptime((texto or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


@login_not_required
@never_cache
@require_http_methods(["GET", "POST"])
def envio(request: HttpRequest, token: str) -> HttpResponse:
    link = link_fornecedor.do_token(token)
    if link is None:
        return _indisponivel(request)
    erro, status = "", 200
    if request.method == "POST":
        try:
            e = link_fornecedor.receber(
                link, request.POST.get("tipo") or "", request.FILES.get("arquivo"),
                tipo_certidao=request.POST.get("tipo_certidao") or "",
                validade_informada=_data(request.POST.get("validade") or ""), ip=_ip(request))
        except PedidoInvalido as exc:
            erro = str(exc)
            status = 429 if exc.args and exc.args[0] == link_fornecedor.MSG_LIMITE else 422
        else:
            request.session[SESSAO] = {"rotulo": str(e).split(" — ")[0],
                                       "avisos": e.avisos.splitlines()}
            return _cabecalhos(redirect(request.path))
    s = link.solicitacao
    return _cabecalhos(render(request, "coffee/publico/envio.html", {
        "s": s, "fornecedor": s.lote.contrato.fornecedor,
        "validade": timezone.localtime(link.expira_em),
        "situacao": link_fornecedor.situacao(link), "erro": erro,
        "recebido": request.session.pop(SESSAO, None),
        "tipos_certidao": dominio_certidoes.TIPOS, "tipos": EnvioFornecedor.Tipo,
    }, status=status))
