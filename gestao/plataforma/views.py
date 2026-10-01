"""Páginas de erro (403/404/500) e verificação de saúde."""

from __future__ import annotations

from django.contrib.auth.decorators import login_not_required
from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


def _erro(
    request: HttpRequest, status: int, titulo: str, mensagem: str, icone: str
) -> HttpResponse:
    contexto = {"status": status, "titulo": titulo, "mensagem": mensagem, "icone": icone}
    return render(request, "erros/erro.html", contexto, status=status)


def erro_403(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return _erro(request, 403, "Acesso não permitido",
                 "Seu perfil não tem permissão para abrir esta página. Se precisar de acesso, "
                 "fale com o administrador da sua unidade.", "lock")


def erro_404(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return _erro(request, 404, "Página não encontrada",
                 "O endereço pode ter mudado ou o registro foi removido. Confira o link ou "
                 "volte para o início.", "search")


def erro_500(request: HttpRequest) -> HttpResponse:
    # Sem contexto de usuário/menu: a falha pode estar justamente neles.
    return render(request, "erros/500.html", status=500)


@login_not_required
@require_GET
def saude(request: HttpRequest) -> JsonResponse:
    """Liveness + readiness: aplicação no ar e banco respondendo."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        banco = "ok"
    except Exception:  # pragma: no cover - depende de falha real do banco
        banco = "indisponivel"
    status = 200 if banco == "ok" else 503
    return JsonResponse({"status": "ok" if status == 200 else "erro", "banco": banco},
                        status=status)
