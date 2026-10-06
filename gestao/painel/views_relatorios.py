"""O relatório consolidado (R1): a tela e a planilha, com os mesmos números."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from . import consolidado


def _ano(request: HttpRequest, hoje) -> int | None:
    """O ano pedido; "todos" junta tudo; qualquer outra coisa vira o ano atual."""
    valor = (request.GET.get("ano") or "").strip()
    if valor == "todos":
        return None
    if valor.isdecimal() and int(valor) in consolidado.anos_disponiveis(hoje):
        return int(valor)
    return hoje.year


@require_GET
def relatorios(request: HttpRequest) -> HttpResponse:
    hoje = timezone.localdate()
    ano = _ano(request, hoje)
    r = consolidado.montar(request.user, ano, hoje)
    return render(request, "painel/relatorios.html", {
        "r": r, "ano_valor": str(ano) if ano else "todos",
        "opcoes_ano": [(str(a), str(a)) for a in consolidado.anos_disponiveis(hoje)]
        + [("todos", "Todos os anos")],
        "gerado_em": timezone.localtime(),
        "migalhas": [("Início", reverse("painel:inicio")), ("Relatórios", "")],
    })


@require_GET
def exportar_relatorio(request: HttpRequest) -> HttpResponse:
    hoje = timezone.localdate()
    ano = _ano(request, hoje)
    r = consolidado.montar(request.user, ano, hoje)
    resposta = HttpResponse(
        consolidado.planilha(r),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    nome = f"relatorio-consolidado-{ano or 'todos'}.xlsx"
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    resposta["Cache-Control"] = "private, no-store"
    return resposta
