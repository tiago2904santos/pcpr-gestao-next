"""Central de notificações (paridade com a da referência): todas / não lidas / lidas, 25 por
página, "Abrir" (marca como lida e vai ao registro) e "Marcar todas como lidas"."""

from __future__ import annotations

from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from gestao.plataforma.models import Notificacao

POR_PAGINA = 25


def _eu(request: HttpRequest) -> int:
    """Quem pede (o LoginRequiredMiddleware garante a sessão; a central é sempre pessoal)."""
    return int(request.user.pk or 0)
FILTROS = [("", "Todas", "bell"), ("nao-lidas", "Não lidas", "circle-dot"),
           ("lidas", "Lidas", "check-circle-2")]


@require_GET
def central(request: HttpRequest) -> HttpResponse:
    base = Notificacao.objects.filter(usuario_id=_eu(request))
    filtro = request.GET.get("filtro", "")
    if filtro not in {f for f, _, _ in FILTROS}:
        filtro = ""
    qs = base.filter(lida=filtro == "lidas") if filtro else base
    pagina = Paginator(qs.order_by("-criada_em", "-pk"), POR_PAGINA).get_page(
        request.GET.get("pagina"))
    nao_lidas = base.filter(lida=False).count()
    total = base.count()
    return render(request, "painel/notificacoes.html", {
        "page_obj": pagina, "filtro": filtro, "filtros": FILTROS,
        "querystring_base": f"filtro={filtro}&" if filtro else "",
        "contagens": {"": total, "nao-lidas": nao_lidas, "lidas": total - nao_lidas},
        "migalhas": [("Início", reverse("painel:inicio")), ("Notificações", "")]})


@require_GET
def abrir(request: HttpRequest, pk: int) -> HttpResponse:
    """Só as próprias (outra pessoa: 404). Marca como lida e vai ao link, se for interno."""
    aviso = get_object_or_404(Notificacao, pk=pk, usuario_id=_eu(request))
    if not aviso.lida:
        Notificacao.objects.filter(pk=aviso.pk).update(lida=True)
    if aviso.link and url_has_allowed_host_and_scheme(aviso.link,
                                                       allowed_hosts={request.get_host()}):
        return redirect(aviso.link)
    return redirect("painel:notificacoes")


@require_POST
def marcar_lidas(request: HttpRequest) -> HttpResponse:
    Notificacao.objects.filter(usuario_id=_eu(request), lida=False).update(lida=True)
    return redirect("painel:notificacoes")
