"""O webhook da Cloud API (sem login, sem CSRF): a autenticação é a assinatura HMAC do corpo
bruto com o App Secret (`X-Hub-Signature-256`). O corpo é gravado antes do 200 e processado
depois pelo worker — a Meta pede resposta em até ~250 ms e reentrega por 7 dias.

Sem App Secret configurado (simulado, PREVIEW) não há o que conferir: tudo é recusado.
"""

from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_not_required
from django.http import HttpRequest, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from gestao.integracoes.whatsapp import config, webhook

from . import entrada

log = logging.getLogger("gestao.automacao")


def _sem_cache(resposta: HttpResponse) -> HttpResponse:
    resposta["Cache-Control"] = "no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    return resposta


@csrf_exempt  # chamada servidor-a-servidor da Meta; autenticada pela assinatura do corpo
@login_not_required
@never_cache
@require_http_methods(["GET", "POST"])
def whatsapp(request: HttpRequest) -> HttpResponse:
    c = config.carregar()
    if request.method == "GET":
        desafio = webhook.desafio(request.GET.dict(), c.verify_token if c.real else "")
        if desafio is None:
            return _sem_cache(HttpResponse(status=403))
        return _sem_cache(HttpResponse(desafio, content_type="text/plain; charset=utf-8"))
    corpo = request.body
    if not c.real or not webhook.assinatura_valida(
            corpo, request.headers.get("X-Hub-Signature-256"), c.app_secret):
        log.warning("webhook do WhatsApp recusado: assinatura ausente ou inválida "
                    "(%d bytes)", len(corpo))
        return _sem_cache(HttpResponse(status=401))
    if len(corpo) > webhook.TAMANHO_MAXIMO:
        return _sem_cache(HttpResponse(status=413))
    entrada.registrar_entrada(corpo, origem="meta")
    return _sem_cache(HttpResponse(status=200))
