"""Diário de bordo (módulo 9b): a folha (motorista e viatura, trechos com km e
abastecimento, conferência do hodômetro, documento) e o documento em PDF/XLSX. Regra em
`diario.py`."""

from __future__ import annotations

import re

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from gestao.cadastros.models import Viatura

from . import diario, policies
from .dominio.diario import km as dominio_km
from .models import DiarioBordo, PrestacaoContas
from .views import _migalhas

CAMPO_LINHA = re.compile(r"^l-(\d+)-(km_inicial|km_final|abastecimento)$")


def _prestacao(request: HttpRequest, pk: int) -> PrestacaoContas:
    p = get_object_or_404(PrestacaoContas.objects.select_related(
        "oficio__unidade", "oficio__viatura__combustivel"), pk=pk)
    if not policies.pode_ver_equipe_prestacao(request.user, p):
        raise Http404
    return p


def _valores(request: HttpRequest) -> dict[int, dict[str, object]]:
    valores: dict[int, dict[str, object]] = {}
    for chave, valor in request.POST.items():
        if (m := CAMPO_LINHA.match(chave)):
            valores.setdefault(int(m.group(1)), {})[m.group(2)] = valor
    return valores


@require_GET
def folha(request: HttpRequest, pk: int) -> HttpResponse:
    p = _prestacao(request, pk)
    finalizada = diario.equipe_finalizada(p)
    editavel = diario.pode_editar(request.user, p, finalizada)
    d = (diario.obter(p) if editavel
         else DiarioBordo.objects.filter(prestacao=p).select_related("prestacao__oficio")
         .first())  # consulta, diário ainda não aberto: mostra sem criar nada
    lista = diario.linhas(d) if d else []
    conf = diario.conferencia(d, lista) if d else None
    oficio = p.oficio
    mot_oficio, via_oficio = diario.motorista_do_oficio(oficio), diario.viatura_do_oficio(oficio)
    nome, cpf = diario.motorista(d) if d else mot_oficio
    v = diario.viatura(d) if d else via_oficio
    def km(valor):
        return dominio_km(valor) if valor is not None else ""

    linhas = [{"l": linha, "rota": diario.rota(linha), "prevista": diario.prevista(linha),
               "rodado": conf.rodados[i] if conf else None,
               "km_inicial": km(linha.km_inicial), "km_final": km(linha.km_final)}
              for i, linha in enumerate(lista)]
    preenchidas = sum(1 for linha in lista
                      if linha.km_inicial is not None and linha.km_final is not None)
    return render(request, "viagens/diario/folha.html", {
        "p": p, "oficio": oficio, "d": d, "linhas": linhas, "conf": conf,
        "editavel": editavel, "equipe_finalizada": finalizada,
        "preenchidas": preenchidas, "completo": bool(lista) and preenchidas == len(lista),
        "faltam": len(lista) - preenchidas,
        "motorista": {"nome": nome, "cpf": cpf}, "viatura": v,
        "motorista_oficio": mot_oficio[0], "viatura_oficio": via_oficio,
        "alteracoes": (diario.alteracoes(d, do_oficio=mot_oficio, viatura_oficio=via_oficio)
                       if d else []),
        "equipe": [vj.servidor for vj in oficio.viajantes.select_related("servidor")
                   .order_by("ordem")],
        "viaturas": Viatura.objects.filter(ativo=True).order_by("modelo", "placa"),
        "tipos_viatura": Viatura.Tipo.choices,
        "migalhas": _migalhas(("Prestação de contas", reverse("viagens:prestacoes")),
                              (f"Diário de bordo · {oficio}", ""))})


@require_POST
def salvar(request: HttpRequest, pk: int) -> HttpResponse:
    """Sem JavaScript (ou "Salvar"): grava as linhas e volta para a folha."""
    p = _prestacao(request, pk)
    d = diario.obter(p)
    try:
        n = diario.salvar_linhas(request.user, d.pk, _valores(request))
    except (diario.DiarioInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Diário de bordo salvo." if n else "Nada mudou no diário.")
    return redirect(reverse("viagens:diario", args=[p.pk]) + "#trechos")


@require_POST
def autosave(request: HttpRequest, pk: int) -> JsonResponse:
    """Contrato do autosave.js: {"salvo", "em", "campos", "recarregar", "mensagem"}."""
    p = _prestacao(request, pk)
    try:
        d = diario.obter(p)
        diario.salvar_linhas(request.user, d.pk, _valores(request))
    except (diario.DiarioInvalido, PermissionDenied) as exc:
        return JsonResponse({"salvo": False, "mensagem": str(exc)})
    return JsonResponse({"salvo": True, "em": f"{timezone.localtime():%H:%M}", "campos": {},
                         "recarregar": False})


def _inteiro(texto: str | None) -> int | None:
    return int(texto) if texto and texto.isdigit() else None


@require_POST
def motorista(request: HttpRequest, pk: int) -> HttpResponse:
    p = _prestacao(request, pk)
    d = diario.obter(p)
    g = request.POST.get
    try:
        diario.trocar_motorista_e_viatura(
            request.user, d.pk, motorista_modo=g("motorista_modo", ""),
            motorista_servidor_id=_inteiro(g("motorista_servidor")),
            motorista_nome=g("motorista_nome", ""), motorista_cpf=g("motorista_cpf", ""),
            motorista_oficio=g("motorista_oficio", ""),
            motorista_protocolo=g("motorista_protocolo", ""),
            viatura_modo=g("viatura_modo", ""), viatura_id=_inteiro(g("viatura")),
            viatura_modelo=g("viatura_modelo", ""), viatura_placa=g("viatura_placa", ""),
            viatura_tipo=g("viatura_tipo", ""), viatura_combustivel=g("viatura_combustivel", ""))
    except (diario.DiarioInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Motorista e viatura deste diário atualizados (o ofício não "
                                  "muda).")
    return redirect(reverse("viagens:diario", args=[p.pk]) + "#motorista")


@require_GET
def documento(request: HttpRequest, pk: int, formato: str) -> HttpResponse:
    if formato not in ("pdf", "xlsx"):
        raise Http404
    p = _prestacao(request, pk)
    d = (diario.obter(p) if diario.pode_editar(request.user, p)
         else get_object_or_404(DiarioBordo, prestacao=p))
    dados = diario.dados_do_documento(d)
    if formato == "pdf":
        resposta = HttpResponse(diario.pdf_do_documento(dados), content_type="application/pdf")
        disposicao = "inline"
    else:
        resposta = HttpResponse(diario.planilha_do_documento(dados), content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
        disposicao = "attachment"
    nome = diario.nome_do_arquivo(d, formato)
    resposta["Content-Disposition"] = f'{disposicao}; filename="{nome}"'
    return resposta
