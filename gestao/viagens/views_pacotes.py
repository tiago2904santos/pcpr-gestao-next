"""Baixar documentos (janela única, componentes/dialogo_baixar.html): GET devolve os
documentos para marcar (JSON, pedido ao abrir — as listas não pagam por isso); POST monta o
pacote. Regra em `pacotes.py`."""

from __future__ import annotations

from collections.abc import Callable

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from . import pacotes, policies
from .models import Oficio, TermoAutorizacao


def _voltar(request: HttpRequest, padrao: str) -> str:
    voltar = request.POST.get("voltar") or ""
    if (voltar.startswith("/") and not voltar.startswith("//")
            and url_has_allowed_host_and_scheme(voltar, allowed_hosts={request.get_host()})):
        return voltar
    return padrao


def _responder(request: HttpRequest, itens: Callable[[], list[pacotes.Item]], *,
               nome_base: str, padrao: str) -> HttpResponse:
    if request.method == "GET":
        resposta: HttpResponse = JsonResponse(
            {"itens": [i.para_tela() for i in itens()]})
        resposta["Cache-Control"] = "no-store"
        return resposta
    formato = request.POST.get("formato", "pdf")
    if formato not in pacotes.FORMATOS:
        raise Http404
    try:
        conteudo, nome, tipo = pacotes.montar(
            itens(), request.POST.getlist("itens"), formato=formato,
            versao=request.POST.get("versao", "assinado"),
            saida=request.POST.get("saida", "separados"), nome_base=nome_base)
    except KeyError:
        raise Http404 from None
    except pacotes.PacoteInvalido as exc:
        messages.error(request, str(exc))
        return redirect(_voltar(request, padrao))
    resposta = HttpResponse(conteudo, content_type=tipo)
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    resposta["Cache-Control"] = "no-store"  # dados pessoais (RG, CPF) e documentos oficiais
    return resposta


def _oficio(request: HttpRequest, pk: int) -> Oficio:
    oficio = get_object_or_404(Oficio, pk=pk)
    if not policies.pode_ver(request.user, oficio):
        raise Http404
    policies.exigir(policies.edita_oficios(request.user),
                    "Você não tem permissão para baixar estes documentos.")
    return oficio


def _lista_do_oficio(oficio: Oficio) -> str:
    return f"{reverse('viagens:oficios')}?resumo={oficio.pk}"


@require_http_methods(["GET", "POST"])
def baixar_oficio(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio(request, pk)
    if oficio.situacao == Oficio.Situacao.CANCELADO:
        messages.error(request, "Reative o ofício antes de baixar documentos.")
        return redirect(_voltar(request, _lista_do_oficio(oficio)))
    return _responder(request, lambda: pacotes.itens_do_oficio(oficio),
                      nome_base=f"oficio-{oficio.numero:02d}-{oficio.ano}",
                      padrao=_lista_do_oficio(oficio))


@require_http_methods(["GET", "POST"])
def baixar_justificativa(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio(request, pk)
    padrao = reverse("viagens:justificativas")
    if oficio.situacao == Oficio.Situacao.CANCELADO:
        messages.error(request, "Reative o ofício antes de baixar documentos.")
        return redirect(_voltar(request, padrao))
    return _responder(request, lambda: pacotes.itens_da_justificativa(oficio),
                      nome_base=f"oficio-{oficio.numero:02d}-{oficio.ano}", padrao=padrao)


@require_http_methods(["GET", "POST"])
def baixar_termo(request: HttpRequest, pk: int) -> HttpResponse:
    termo = get_object_or_404(TermoAutorizacao, pk=pk)
    if not policies.pode_ver_termo(request.user, termo):
        raise Http404
    padrao = reverse("viagens:editar_termo", args=[termo.pk])
    if termo.cancelado:
        messages.error(request, "Reative o termo antes de baixar documentos.")
        return redirect(_voltar(request, padrao))
    policies.exigir(policies.pode_editar_termo(request.user, termo),
                    "Você não tem permissão para baixar estes documentos.")
    return _responder(request, lambda: pacotes.itens_do_termo(termo),
                      nome_base=f"termo-{termo.pk}", padrao=padrao)
