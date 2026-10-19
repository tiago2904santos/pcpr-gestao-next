"""Busca de seleção contextual; não dá acesso à manutenção de servidores."""

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404, HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from gestao.cadastros.fontes import fonte_local

from . import policies
from .forms import QUEM_DIRIGE


@require_GET
def buscar(request: HttpRequest) -> JsonResponse:
    solicitacao = None
    if pedido := request.GET.get("solicitacao"):
        if not pedido.isascii() or not pedido.isdecimal() or len(pedido) > 18:
            raise Http404("Solicitação não encontrada.")
        solicitacao = get_object_or_404(
            policies.solicitacoes_visiveis(request.user), pk=int(pedido))
    if not policies.pode_buscar_motoristas(request.user, solicitacao):
        raise PermissionDenied("Você não pode selecionar o motorista desta solicitação.")
    termo = " ".join((request.GET.get("q") or "").split())[:120]
    consulta = fonte_local.consultar("servidor").filter(QUEM_DIRIGE).distinct()
    if termo:
        consulta = consulta.filter(Q(nome__unaccent__icontains=termo)
                                   | Q(cargo__nome__unaccent__icontains=termo)
                                   | Q(unidade__nome__unaccent__icontains=termo)
                                   | Q(unidade__sigla__unaccent__icontains=termo))
    return JsonResponse({"resultados": [
        {"id": str(servidor.pk), "titulo": servidor.nome, "meta": servidor.descricao}
        for servidor in consulta.order_by("nome", "pk")[:15]]})
