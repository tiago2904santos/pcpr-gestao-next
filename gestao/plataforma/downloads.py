"""Manifesto de downloads: cada item mantém sua autorização no endpoint original."""

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render


def responder_fila(request, itens: list[dict]):
    dados = {"fila": itens}
    if request.headers.get("X-Requested-With") == "fetch":
        resposta: HttpResponse = JsonResponse(dados)
    else:
        resposta = render(request, "downloads/fila.html", {"manifesto": dados})
    resposta["Cache-Control"] = "no-store"
    return resposta
