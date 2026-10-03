"""Consultas dos cadastros de apoio (o CRUD completo é do próximo módulo)."""

from __future__ import annotations

from django.contrib.auth.decorators import permission_required
from django.contrib.postgres.lookups import Unaccent
from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Q, Value, When
from django.db.models.functions import Lower
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_GET

from .models import Municipio, Servidor, TabelaDiaria, Viatura


def _migalhas(rotulo: str):
    return [("Início", reverse("painel:inicio")), ("Viagens", reverse("viagens:painel")),
            ("Cadastros", ""), (rotulo, "")]


@require_GET
@permission_required("cadastros.view_servidor", raise_exception=True)
def servidores(request: HttpRequest) -> HttpResponse:
    termo = (request.GET.get("q") or "").strip()
    qs = Servidor.objects.select_related("cargo", "unidade").order_by("nome")
    if termo:
        qs = qs.filter(Q(nome__unaccent__icontains=termo) | Q(cpf__contains=termo)
                       | Q(rg__contains=termo))
    pagina = Paginator(qs, 25).get_page(request.GET.get("pagina"))
    return render(request, "cadastros/servidores.html", {
        "page_obj": pagina, "termo": termo,
        "querystring_base": f"{urlencode({'q': termo})}&" if termo else "",
        "migalhas": _migalhas("Servidores")})


@require_GET
@permission_required("cadastros.view_viatura", raise_exception=True)
def viaturas(request: HttpRequest) -> HttpResponse:
    return render(request, "cadastros/viaturas.html", {
        "viaturas": Viatura.objects.select_related("combustivel", "unidade")
        .prefetch_related("motoristas"),
        "migalhas": _migalhas("Viaturas")})


@require_GET
@permission_required("cadastros.view_tabeladiaria", raise_exception=True)
def diarias(request: HttpRequest) -> HttpResponse:
    from decimal import ROUND_HALF_UP, Decimal

    linhas = []
    for t in TabelaDiaria.objects.all():
        def pct(p, t=t):
            return (t.valor_24h * p / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        linhas.append({"tabela": t, "p15": pct(15), "p30": pct(30)})
    return render(request, "cadastros/diarias.html", {
        "linhas": linhas, "migalhas": _migalhas("Tabela de diárias")})


@require_GET
def buscar_municipios(request: HttpRequest) -> JsonResponse:
    """Autocompletar "Cidade/UF": prefixo sem acento/caixa, Paraná primeiro; `?uf=SC`
    restringe ao estado escolhido no itinerário."""
    termo = (request.GET.get("q") or "").strip()
    nome, _, uf = termo.partition("/")
    uf = uf or (request.GET.get("uf") or "")  # filtro do seletor de estado (itinerário)
    qs = Municipio.objects.annotate(n=Unaccent(Lower("nome"))).filter(
        n__startswith=Unaccent(Lower(Value(nome.strip()))))
    if uf.strip():
        qs = qs.filter(uf__iexact=uf.strip()[:2])
    prioridade = Case(When(uf="PR", then=0), default=1, output_field=IntegerField())
    resultados = qs.annotate(prioridade=prioridade).order_by("prioridade", "nome")[:12]
    return JsonResponse({"resultados": [
        {"id": f"{m.nome}/{m.uf}", "titulo": f"{m.nome}/{m.uf}", "meta": ""} for m in resultados
    ]})
