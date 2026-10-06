"""Painel do Coffee Break e o registro das entregas (CB6a): a entrada do módulo com os
números, os alertas (saldo, vigência, certidões) e "O que fazer hoje"; registrar a entrega
de uma OS (a partir do dia do evento) e baixar a foto ou o documento anexado."""

from __future__ import annotations

import re

from django.contrib import messages
from django.db.models import Max
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import dominio_painel as regras
from . import entregas, painel, pedidos, policies
from .models import Entrega, Solicitacao
from .views_pedidos import _base, _exigir, _linha

RASCUNHO = "coffee_entrega_rascunho"
TIPOS_DE_ARQUIVO = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg"}


@require_GET
def painel_coffee(request: HttpRequest) -> HttpResponse:
    _exigir(request)
    hoje = timezone.localdate()
    p = painel.montar(hoje)
    recentes = _base().annotate(ultimo=Max("movimentos__em")).order_by("-criado_em", "-pk")[:5]
    return render(request, "coffee/painel.html", {
        "p": p, "ind": p.indicadores, "hoje": hoje,
        "recentes": [_linha(s, hoje) for s in recentes],
        "msg_nada": regras.MSG_NADA_PENDENTE, "dias_parada": regras.DIAS_PARADA,
        "pode_gerir": policies.pode_gerir_cadastros(request.user),
        "migalhas": [("Início", reverse("painel:inicio")), ("Coffee Break", "")],
    })


def _avaliacao(texto: str | None) -> int | None:
    texto = (texto or "").strip()
    return int(texto) if texto.isdecimal() and len(texto) == 1 else None


@require_POST
def registrar_entrega(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(request)
    get_object_or_404(Solicitacao, pk=pk)
    tipo = (request.POST.get("tipo") or "")[:20]
    avaliacao = _avaliacao(request.POST.get("avaliacao"))
    recebido_por = (request.POST.get("recebido_por") or "")[:150]
    observacao = (request.POST.get("observacao") or "")[:4000]
    dados = {"tipo": tipo, "avaliacao": avaliacao, "recebido_por": recebido_por,
             "observacao": observacao}
    try:
        e = entregas.registrar(request.user, pk, tipo=tipo, avaliacao=avaliacao,
                               recebido_por=recebido_por, observacao=observacao,
                               anexo=request.FILES.get("anexo"))
    except pedidos.PedidoInvalido as exc:
        messages.error(request, str(exc))
        request.session[RASCUNHO] = {**dados, "pk": pk, "campo": exc.campo or ""}
    else:
        messages.success(request, entregas.mensagem(e))
    return redirect(reverse("coffee:solicitacao", args=[pk]) + "#entregas")


@require_GET
def arquivo_entrega(request: HttpRequest, pk: int) -> StreamingHttpResponse:
    from django.http import FileResponse, Http404

    _exigir(request)
    e = get_object_or_404(Entrega.objects.select_related("solicitacao"), pk=pk)
    if not e.anexo:
        raise Http404
    caminho = str(e.anexo.name)
    extensao = caminho[caminho.rfind("."):].lower()
    if extensao not in TIPOS_DE_ARQUIVO:
        raise Http404
    nome = re.sub(r"[^\w .-]", "-", f"Entrega {e.solicitacao} {e.registrado_em:%Y-%m-%d}")[:120]
    try:
        conteudo = e.anexo.open("rb")
    except OSError:
        raise Http404 from None
    resposta = FileResponse(conteudo, as_attachment=True, filename=nome + extensao,
                            content_type=TIPOS_DE_ARQUIVO[extensao])
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Cache-Control"] = "private, no-store"
    return resposta


def contexto_da_folha(request: HttpRequest, s: Solicitacao) -> dict:
    """O que a seção de entregas da folha precisa (a lista, se pode registrar e o rascunho
    de um envio recusado)."""
    hoje = timezone.localdate()
    rascunho = request.session.get(RASCUNHO)
    if rascunho and rascunho.get("pk") == s.pk:
        request.session.pop(RASCUNHO, None)
    else:
        rascunho = None
    return {
        "entregas": list(s.entregas.select_related("registrado_por")),
        "pode_registrar_entrega": entregas.pode_registrar(s, hoje),
        "tipos_entrega": regras.TIPOS_ENTREGA,
        "rascunho_entrega": rascunho or {"tipo": "sem_ocorrencia", "avaliacao": None,
                                         "recebido_por": "", "observacao": "", "campo": ""},
    }
