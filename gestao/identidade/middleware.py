"""Entrada direta no PREVIEW (DEMO_MODE): abrir qualquer página do sistema já autentica o
usuário de demonstração, com uma sessão normal (`django.contrib.auth.login`).

Só é instalado por `config.settings.preview` com DEMO_MODE e, mesmo assim, só age se
`ambiente.demo_ativo()` for verdadeiro. Exceções:
- a própria tela de login (continua sendo a tela real do produto);
- depois de "Sair": um cookie marca a saída e a entrada automática para até o próximo login,
  para que o fluxo login → sistema → sair → login seja testável.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import HttpRequest, HttpResponse
from django.urls import reverse

from gestao.plataforma import ambiente

COOKIE_SAIU = "pcpr_demo_saiu"


class EntradaDemoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not ambiente.demo_ativo():
            return self.get_response(request)
        entrar, sair = reverse("identidade:entrar"), reverse("identidade:sair")
        livre = request.path in (entrar, sair) or request.path.startswith(
            (settings.STATIC_URL, "/saude"))
        if (not livre and not request.user.is_authenticated
                and not request.COOKIES.get(COOKIE_SAIU)):
            usuario = authenticate(request, demo=True)
            if usuario is not None:
                login(request, usuario)
        resposta = self.get_response(request)
        if request.method == "POST" and request.path == sair:
            resposta.set_cookie(COOKIE_SAIU, "1", httponly=True, samesite="Lax",
                                secure=request.is_secure())
        elif request.method == "POST" and request.path == entrar and request.user.is_authenticated:
            resposta.delete_cookie(COOKIE_SAIU, samesite="Lax")
        return resposta
