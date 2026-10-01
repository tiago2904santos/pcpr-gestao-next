from django.http import JsonResponse
from django.shortcuts import render

from gestao.plataforma.navegacao import modulos


def inicio(request):
    return render(request, "painel/inicio.html", {"modulos_disponiveis": modulos()})


def notificacoes(request):
    return render(request, "painel/notificacoes.html", {})


def busca(request):
    return JsonResponse({"resultados": []})
