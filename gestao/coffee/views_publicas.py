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

from gestao.plataforma.middleware import ip_do_cliente

from . import dominio_certidoes, link_fornecedor
from .models import EnvioFornecedor
from .pedidos import PedidoInvalido

TENTATIVAS_INVALIDAS_POR_HORA = 20
SESSAO = "coffee_fornecedor_recebido"


def _ip(request: HttpRequest) -> str:
    return ip_do_cliente(request) or ""


def _cabecalhos(resposta: HttpResponse) -> HttpResponse:
    resposta["Referrer-Policy"] = "no-referrer"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    return resposta


def _chave_invalidos(request: HttpRequest) -> str:
    return f"coffee-link-invalido:{link_fornecedor.origem(_ip(request))}"


def _indisponivel(request: HttpRequest, status: int = 404) -> HttpResponse:
    return _cabecalhos(render(request, "coffee/publico/indisponivel.html", status=status))


def _contar(chave: str) -> int:
    """Soma uma tentativa na janela de uma hora e devolve o total."""
    if cache.add(chave, 1, 3600):
        return 1
    try:
        return cache.incr(chave)
    except ValueError:  # expirou entre o add e o incr
        cache.set(chave, 1, 3600)
        return 1


def _data(texto: str):
    try:
        return datetime.strptime((texto or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


@login_not_required
@never_cache
@require_http_methods(["GET", "POST"])
def envio(request: HttpRequest, token: str) -> HttpResponse:
    # Quem já errou tokens demais nem chega a consultar o banco.
    if (cache.get(_chave_invalidos(request)) or 0) >= TENTATIVAS_INVALIDAS_POR_HORA:
        return _indisponivel(request, 429)
    link = link_fornecedor.do_token(token)
    if link is None:
        _contar(_chave_invalidos(request))
        return _indisponivel(request)
    erro, status = "", 200
    if request.method == "POST":
        # Toda tentativa conta (também as recusadas: PDF ruim, CNPJ de outro, vencida).
        quem = link_fornecedor.origem(_ip(request))
        if max(_contar(f"coffee-link-envio:{link.pk}"),
               _contar(f"coffee-link-envio-origem:{quem}")) > link_fornecedor.LIMITE_POR_HORA:
            return _cabecalhos(render(request, "coffee/publico/indisponivel.html",
                                      {"limite": True}, status=429))
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
