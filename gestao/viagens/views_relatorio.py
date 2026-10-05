"""Relatório técnico (módulo 9c): a folha (texto da equipe, custeio, diária de cada
servidor) e o documento por servidor em PDF/DOCX. Regra em `relatorio.py`."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from gestao.cadastros import policies as politicas_cadastros

from . import diario, policies, relatorio
from . import prestacao as servico
from .dominio import relatorio as dominio
from .models import PrestacaoContas, PrestacaoServidor, RelatorioTecnico
from .views import _migalhas


def _prestacao(request: HttpRequest, pk: int) -> PrestacaoContas:
    p = get_object_or_404(PrestacaoContas.objects.select_related("oficio__unidade"), pk=pk)
    if not policies.pode_ver_equipe_prestacao(request.user, p):
        raise Http404
    return p


def _campos(request: HttpRequest) -> dict[str, str]:
    aceitos = {*dominio.CAMPOS_TEXTO, "diaria", *dominio.CUSTEIO,
               *(f"{c}_outro" for c in dominio.CUSTEIO)}
    return {k: str(request.POST.get(k, "")) for k in request.POST
            if k in aceitos or (k.startswith("ps-") and k.endswith("-diaria"))}


@require_GET
def folha(request: HttpRequest, pk: int) -> HttpResponse:
    p = _prestacao(request, pk)
    finalizada = diario.equipe_finalizada(p)
    editavel = diario.pode_editar(request.user, p, finalizada)
    rt = (relatorio.obter(p) if editavel
          else RelatorioTecnico.objects.filter(prestacao=p).first())
    sugestoes = relatorio.sugestoes(p) if editavel else {}
    prontos = relatorio.textos_prontos(p) if editavel else {}
    campos = [{"nome": c, "rotulo": dominio.ROTULOS[c], "tipo": dominio.TIPO_DO_CAMPO[c],
               "valor": (getattr(rt, c) if rt else "") or sugestoes.get(c, ""),
               "sugerido": bool(rt) and not getattr(rt, c) and c in sugestoes,
               "prontos": prontos.get(c, []),
               "obrigatorio": c in ("motivo", "atividade", "conclusao")}
              for c in dominio.CAMPOS_TEXTO]
    custeio = []
    for nome, (rotulo, fixas, padrao) in dominio.CUSTEIO.items():
        atual = getattr(rt, nome) if rt else padrao
        custeio.append({"nome": nome, "rotulo": rotulo, "fixas": fixas,
                        "outro": atual not in fixas, "valor": atual})
    servidores = []
    for ps in servico.ativos(PrestacaoServidor.objects.filter(prestacao=p)
                             .select_related("servidor").order_by("servidor__nome")):
        ps.prestacao = p
        liberada = servico.diaria_liberada(ps)
        recebida = (" ".join(t for t in (dominio.moeda(ps.diaria_valor_override),
                                          ps.diaria_valor_override_observacao) if t)
                    if ps.diaria_valor_override else "")
        servidores.append({"ps": ps, "liberada": dominio.moeda(liberada) if liberada else "",
                           "recebida": recebida})
    preenchido = bool(rt) and dominio.preenchido(
        {c: getattr(rt, c) for c in dominio.CAMPOS_TEXTO})
    return render(request, "viagens/relatorio/folha.html", {
        "p": p, "oficio": p.oficio, "rt": rt, "campos": campos, "custeio": custeio,
        "servidores": servidores, "editavel": editavel, "equipe_finalizada": finalizada,
        "preenchido": preenchido, "outro": dominio.OUTRO,
        "pode_gerir_textos": politicas_cadastros.pode_gerir_textos(request.user),
        "migalhas": _migalhas(("Prestação de contas", reverse("viagens:prestacoes")),
                              (f"Relatório técnico · {p.oficio}", ""))})


def _gravar(request: HttpRequest, p: PrestacaoContas) -> dict[str, str]:
    rt = relatorio.obter(p)
    return relatorio.salvar(request.user, rt.pk, _campos(request))


@require_POST
def salvar(request: HttpRequest, pk: int) -> HttpResponse:
    p = _prestacao(request, pk)
    try:
        erros = _gravar(request, p)
    except (relatorio.RelatorioInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        for erro in erros.values():
            messages.error(request, erro)
        if not erros:
            messages.success(request, "Relatório técnico salvo.")
    return redirect(reverse("viagens:relatorio", args=[p.pk]))


@require_POST
def autosave(request: HttpRequest, pk: int) -> JsonResponse:
    """Contrato do autosave.js. Com diária recusada, o texto grava e a resposta diz o erro."""
    p = _prestacao(request, pk)
    try:
        erros = _gravar(request, p)
    except (relatorio.RelatorioInvalido, PermissionDenied) as exc:
        return JsonResponse({"salvo": False, "mensagem": str(exc)})
    if erros:
        return JsonResponse({"salvo": False, "mensagem": " ".join(erros.values())})
    return JsonResponse({"salvo": True, "em": f"{timezone.localtime():%H:%M}", "campos": {},
                         "recarregar": False})


@require_GET
def documento(request: HttpRequest, pk: int, ps_pk: int, formato: str) -> HttpResponse:
    if formato not in ("pdf", "docx"):
        raise Http404
    p = _prestacao(request, pk)
    ps = get_object_or_404(servico.ativos(PrestacaoServidor.objects.select_related("servidor")),
                           pk=ps_pk, prestacao=p)
    rt = (relatorio.obter(p) if diario.pode_editar(request.user, p)
          else get_object_or_404(RelatorioTecnico, prestacao=p))
    dados = relatorio.dados_do_documento(rt, ps)
    nome = relatorio.nome_do_arquivo(rt, ps, formato)
    if formato == "pdf":
        resposta = HttpResponse(relatorio.pdf_do_documento(dados), content_type="application/pdf")
        resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    else:
        resposta = HttpResponse(relatorio.docx_do_documento(dados), content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
        resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resposta
