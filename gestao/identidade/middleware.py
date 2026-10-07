"""Middlewares de identidade.

0. Entrada obrigatória (o LoginRequiredMiddleware do Django, com uma diferença): sem sessão,
   a NAVEGAÇÃO vai para a tela de login, como sempre; um pedido ASSÍNCRONO (HTMX, fetch,
   JSON) recebe 401 com o caminho de volta — antes ele seguia o redirecionamento e a tela de
   login inteira aparecia dentro de um menu ou da lista (QA Lote 3, I1). O front avisa "Sua
   sessão terminou — entre de novo" (app.js; menu.js no próprio menu); o HTMX recarrega a
   página no login (`HX-Redirect`), voltando depois para onde a pessoa estava.

1. Troca de senha obrigatória (paridade com `TrocaDeSenhaObrigatoriaMiddleware` da
   referência): quem entrou com uma senha cadastrada por outra pessoa (`deve_trocar_senha`)
   só navega depois de escolher uma só dela. Sair e a própria troca continuam livres.

2. Entrada direta no PREVIEW (DEMO_MODE): abrir qualquer página do sistema já autentica o
usuário de demonstração, com uma sessão normal (`django.contrib.auth.login`).

Só é instalado por `config.settings.preview` com DEMO_MODE e, mesmo assim, só age se
`ambiente.demo_ativo()` for verdadeiro. Exceções:
- a própria tela de login (continua sendo a tela real do produto);
- depois de "Sair": um cookie marca a saída e a entrada automática para até o próximo login,
  para que o fluxo login → sistema → sair → login seja testável.
"""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.middleware import LoginRequiredMiddleware
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, resolve_url
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from gestao.plataforma import ambiente

COOKIE_SAIU = "pcpr_demo_saiu"
SESSAO_TERMINOU = "Sua sessão terminou — entre de novo."


def pedido_assincrono(request: HttpRequest) -> bool:
    """HTMX, fetch/XHR (o navegador marca `Sec-Fetch-Dest: empty`) ou quem pede JSON."""
    return bool(request.headers.get("HX-Request") or request.headers.get("X-Requested-With")
                or request.headers.get("Sec-Fetch-Dest") == "empty"
                or "application/json" in request.headers.get("Accept", ""))


def _pagina_de_origem(request: HttpRequest) -> str:
    """Onde a pessoa estava (a página, não o fragmento pedido), se for deste site."""
    for origem in (request.headers.get("HX-Current-URL"), request.headers.get("Referer")):
        if origem and url_has_allowed_host_and_scheme(
                origem, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            partes = urlsplit(origem)
            return partes.path + (f"?{partes.query}" if partes.query else "")
    return request.get_full_path()


class EntradaObrigatoriaMiddleware(LoginRequiredMiddleware):
    def handle_no_permission(self, request, view_func):
        if not pedido_assincrono(request):
            return super().handle_no_permission(request, view_func)
        entrar = redirect_to_login(_pagina_de_origem(request),
                                   resolve_url(self.get_login_url(view_func)),
                                   self.get_redirect_field_name(view_func))["Location"]
        resposta = JsonResponse({"mensagem": SESSAO_TERMINOU, "entrar": entrar}, status=401)
        resposta["X-Sessao-Expirada"] = "1"
        if request.headers.get("HX-Request"):
            resposta["HX-Redirect"] = entrar
        resposta["Cache-Control"] = "no-store"
        return resposta


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


MENSAGEM = ("Defina uma senha só sua para continuar — a atual foi cadastrada por outra "
            "pessoa.")


class TrocaDeSenhaObrigatoriaMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        usuario = getattr(request, "user", None)
        if (usuario is not None and usuario.is_authenticated
                and getattr(usuario, "deve_trocar_senha", False)):
            livres = {reverse("identidade:alterar_senha"), reverse("identidade:sair")}
            if request.path not in livres and not request.path.startswith(settings.STATIC_URL):
                if request.method == "GET":
                    messages.warning(request, MENSAGEM)
                return redirect("identidade:alterar_senha")
        return self.get_response(request)
