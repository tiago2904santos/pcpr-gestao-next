"""Relatório do contrato (tela, PDF e CSV) e a virada de exercício (CB6b)."""

from __future__ import annotations

import csv
import re
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from . import policies, relatorio, virada
from .documentos import MSG_SEM_MOTOR
from .models import Contrato
from .views_pedidos import _celula, _exigir, _migalhas


def _nome(contrato: Contrato) -> str:
    return re.sub(r"[^\w .-]", "-", f"Relatorio do contrato {contrato.numero}")[:120]


@require_GET
def relatorio_contrato(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(request)
    contrato = get_object_or_404(Contrato.objects.select_related("fornecedor")
                                 .prefetch_related("aditivos"), pk=pk)
    r = relatorio.montar(contrato, timezone.localdate())
    formato = request.GET.get("formato")
    if formato == "csv":
        resposta = HttpResponse(content_type="text/csv; charset=utf-8")
        resposta["Content-Disposition"] = f'attachment; filename="{_nome(contrato)}.csv"'
        resposta.write("﻿")
        escritor = csv.writer(resposta, delimiter=";", lineterminator="\r\n")
        for linha in relatorio.linhas_csv(r):
            escritor.writerow([_celula(v) for v in linha])
        return resposta
    if formato == "pdf":
        try:
            from weasyprint import HTML
        except (ImportError, OSError):
            messages.error(request, MSG_SEM_MOTOR)
            return redirect("coffee:relatorio_contrato", pk=contrato.pk)
        folha = render_to_string("coffee/pdf/relatorio.html", {"r": r, "tela": False})
        resposta = HttpResponse(HTML(string=folha).write_pdf(), content_type="application/pdf")
        resposta["Content-Disposition"] = f'attachment; filename="{_nome(contrato)}.pdf"'
        resposta["Cache-Control"] = "private, no-store"
        return resposta
    return render(request, "coffee/relatorio.html", {
        "r": r, "migalhas": _migalhas(("Lotes", reverse("coffee:lotes")),
                                      (f"Relatório do contrato {contrato.numero}", "")),
    })


def _inteiro(texto: str | None) -> int | None:
    texto = (texto or "").strip().replace(".", "")
    return int(texto) if texto.isdecimal() and len(texto) <= 9 else None


def _decimal(texto: str | None) -> Decimal | None:
    texto = (texto or "").strip().replace(".", "").replace(",", ".")
    if not texto:
        return None
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        return None
    return valor if valor.is_finite() and Decimal(0) <= valor < Decimal("1e12") else None


@require_http_methods(["GET", "POST"])
def virada_exercicio(request: HttpRequest) -> HttpResponse:
    """"Abrir exercício N+1": os lotes vigentes de N, cada um com a quantidade e o empenho."""
    if not policies.pode_gerir_cadastros(request.user, "lotes"):
        raise PermissionDenied
    origem = virada.exercicio_de_origem()
    if origem is None:
        messages.info(request, virada.MSG_SEM_LOTES)
        return redirect("coffee:lotes")
    destino = origem + 1
    lotes = virada.lotes_de_origem(origem)
    encerrar = request.POST.get("encerrar") == "1"
    if request.method == "POST":
        marcados = set(request.POST.getlist("criar"))
        linhas = [virada.Linha(
            lote, str(lote.pk) in marcados, _inteiro(request.POST.get(f"quantidade-{lote.pk}")),
            (request.POST.get(f"empenho-{lote.pk}") or "")[:60],
            _decimal(request.POST.get(f"valor-{lote.pk}"))) for lote in lotes]
        try:
            criados = virada.abrir_exercicio(request.user, destino, linhas, encerrar)
        except virada.ViradaInvalida as exc:
            messages.error(request, str(exc))
            status = 422
        else:
            messages.success(request, virada.mensagem(criados, origem, destino, encerrar))
            return redirect(reverse("coffee:lotes") + "?situacao=ativos")
    else:
        linhas = [virada.Linha(lote, not virada.impedimento(lote, destino),
                               lote.quantidade_total) for lote in lotes]
        status = 200
    return render(request, "coffee/virada.html", {
        "origem": origem, "destino": destino, "encerrar": encerrar,
        "linhas": [{"l": linha, "impedimento": virada.impedimento(linha.origem, destino),
                    "aviso": virada.aviso_de_vigencia(linha.origem, destino)}
                   for linha in linhas],
        "migalhas": _migalhas(("Lotes", reverse("coffee:lotes")),
                              (f"Abrir exercício {destino}", "")),
    }, status=status)
