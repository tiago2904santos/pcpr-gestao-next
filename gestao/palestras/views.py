"""Telas das palestras e eventos (paridade com `demandas_eventos/views.py` da referência):
painel, lista com status e tipo de evento, exportação CSV com as colunas da planilha, a
folha da palestra (nova e existente, que se grava sozinha), o andamento (com o que o
status pede), a resposta ao solicitante e os cadastros de apoio.

Fora daqui por enquanto (ver docs/migration/palestras.md): pedido público com link de
acompanhamento, encaminhar à DG, consultar protocolo, "preencher com e-mail".
"""

from __future__ import annotations

import csv
from typing import Any
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import dominio, historico, policies, queries, services
from .forms import (
    FORM_ID,
    FormularioAndamento,
    FormularioPalestra,
    FormularioPalestrante,
    FormularioResposta,
)
from .models import Palestra, Palestrante, RespostaPadrao, Tema

POR_PAGINA = 25


def _exigir(condicao: bool) -> None:
    if not condicao:
        raise PermissionDenied


def _migalhas(*itens: tuple[str, str]) -> list[tuple[str, str]]:
    return [("Início", reverse("painel:inicio")), ("Palestras", reverse("palestras:painel")),
            *itens]


# ------------------------------------------------------------------ painel
@require_GET
def painel(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_acessar(request.user))
    hoje = timezone.localdate()
    temas = queries.por_tema(hoje)
    return render(request, "palestras/painel.html", {
        "ind": queries.indicadores(hoje), "publico": queries.publico_do_ano(hoje),
        "ano": hoje.year,
        "proximas": [queries.linha(p, hoje) for p in queries.proximas(hoje)],
        "recentes": [queries.linha(p, hoje) for p in queries.base().order_by(
            "-data_solicitacao", "-pk")[:6]],
        "por_tema": temas, "maior_tema": max((t["total"] for t in temas), default=0),
        "pode_criar": policies.pode_criar(request.user),
        "pode_gerir_cadastros": policies.pode_gerir_cadastros(request.user),
        "migalhas": [("Início", reverse("painel:inicio")), ("Palestras", "")],
    })


# ------------------------------------------------------------------ lista e exportação
def _querystring(request: HttpRequest, *sem: str) -> str:
    return urlencode([(k, v) for k, valores in request.GET.lists() for v in valores
                      if k not in sem and v])


@require_GET
def lista(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_acessar(request.user))
    hoje = timezone.localdate()
    filtros = queries.ler_filtros(request.GET)
    contagens = queries.contagens_por_status(queries.filtrar(filtros, com_status=False))
    qs = queries.filtrar(filtros).order_by("-data_solicitacao", "-pk")
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    base = _querystring(request, "pagina")
    return render(request, "palestras/lista.html", {
        "page_obj": pagina, "linhas": [queries.linha(p, hoje) for p in pagina.object_list],
        "filtros": filtros,
        "abas": [("", "Todas", contagens[""]),
                 *((v, r, contagens.get(v, 0)) for v, r, _d, _t in dominio.STATUS)],
        "qs_sem_status": _querystring(request, "status", "pagina"),
        "querystring_base": f"{base}&" if base else "",
        "tipos_evento": dominio.TIPOS_EVENTO, "temas": Tema.objects.order_by("nome"),
        "url_exportar": reverse("palestras:exportar") + (f"?{base}" if base else ""),
        "pode_criar": policies.pode_criar(request.user),
        "migalhas": _migalhas(("Palestras e eventos", "")),
    })


@require_GET
def exportar(request: HttpRequest) -> HttpResponse:
    """A lista filtrada em CSV com as colunas da planilha da ASCOM (";" e BOM), na ordem
    dela; local, endereço, bairro e CEP no fim, como na referência."""
    _exigir(policies.pode_acessar(request.user))
    qs = queries.filtrar(queries.ler_filtros(request.GET)).order_by("-data_solicitacao", "-pk")
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = (
        f'attachment; filename="palestras-{timezone.localdate():%Y-%m-%d}.csv"')
    resposta.write("﻿")
    escritor = csv.writer(resposta, delimiter=";", lineterminator="\r\n")
    escritor.writerow(["MÊS", "MUNICIPIO", "DATA DO EVENTO E HORA (PERÍODO)", "EVENTO",
                       "STATUS DA DEMANDA", "ANDAMENTO", "INFORMAÇÕES PRÉVIAS", "SOLICITANTE",
                       "CONTATO", "DATA DA SOLICITAÇÃO", "FOI SOLICITADO VIA:", "DESCRIÇÃO",
                       "QUANTIDADE DE PÚBLICO", "ASSUNTO E-MAIL", "PEDIDO/CONTATO", "TEMA",
                       "SERVIDOR", "LOCAL", "ENDEREÇO", "BAIRRO", "CEP"])
    for p in qs:
        escritor.writerow([
            queries.mes_de_referencia(p),
            f"{p.municipio.nome}/{p.municipio.uf}" if p.municipio else "",
            p.periodo or "À definir", p.get_evento_display().upper(),
            p.get_status_display().upper(), p.andamento, p.informacoes_previas, p.solicitante,
            p.contato_texto, f"{p.data_solicitacao:%d/%m/%Y}", p.canal_texto.upper(),
            p.descricao, "" if p.quantidade_publico is None else p.quantidade_publico,
            p.assunto_email, p.pedido_contato, ", ".join(t.nome for t in p.temas.all()),
            ", ".join(x.nome for x in p.palestrantes.all()), p.local, p.endereco, p.bairro,
            p.cep])
    return resposta


@require_GET
def buscar_palestrantes(request: HttpRequest) -> JsonResponse:
    """Busca da escolha de palestrantes (JSON do <pc-multiescolha>)."""
    _exigir(policies.pode_acessar(request.user))
    termo = dominio.uma_linha(request.GET.get("q"))[:60]
    qs = Palestrante.objects.order_by("nome")
    if termo:
        qs = qs.filter(Q(nome__icontains=termo) | Q(lotacao__icontains=termo)
                       | Q(tema_abordagem__icontains=termo))
    return JsonResponse({"resultados": [
        {"id": p.pk, "titulo": str(p), "meta": p.descricao} for p in qs[:12]]})


# ------------------------------------------------------------------ folha
def _primeiro_erro(form) -> str:
    for nome, erros in form.errors.items():
        rotulo = form.fields[nome].label if nome in form.fields else ""
        texto = erros[0] if erros else ""
        return f"Não salvo: {rotulo} — {texto}" if rotulo else f"Não salvo: {texto}"
    return "Não salvo."


def _contexto_folha(request: HttpRequest, form: FormularioPalestra, p: Palestra | None, *,
                    andamento: FormularioAndamento | None = None,
                    resposta: FormularioResposta | None = None) -> dict:
    hoje = timezone.localdate()
    contexto = {
        "form": form, "form_id": FORM_ID, "palestra": p,
        "editavel": policies.pode_editar(request.user) if p else policies.pode_criar(request.user),
        "solicitantes": list(Palestra.objects.order_by("solicitante")
                             .values_list("solicitante", flat=True).distinct()[:300]),
        "voltar": reverse("palestras:lista"),
        "pode_gerir_cadastros": policies.pode_gerir_cadastros(request.user),
    }
    if p is None:
        contexto["migalhas"] = _migalhas(("Palestras e eventos", reverse("palestras:lista")),
                                         ("Nova palestra", ""))
        return contexto
    tem_palestrante = p.palestrantes.exists()
    possiveis = dominio.opcoes_de_status(p.status, p.data_inicio_evento, hoje)
    contexto.update({
        "quando": dominio.quando(p.data_inicio_evento, p.data_fim_evento, hoje),
        "etapas": dominio.etapas(p.status),
        "andamento": andamento or FormularioAndamento(),
        "opcoes_status": [(v, r, dominio.DICAS[v]) for v, r, _d, _t in dominio.STATUS
                          if v in possiveis],
        # Só pergunta o que falta para um status que de fato está entre as opções.
        "faltas": dominio.Faltas(
            data=p.data_inicio_evento is None and bool({"agendada", "atendida"} & set(possiveis)),
            palestrante=not tem_palestrante and "agendada" in possiveis,
            publico=p.quantidade_publico is None and "atendida" in possiveis),
        "dica_atual": dominio.DICAS.get(p.status, ""),
        "ultima_anotacao": services.ultima_anotacao(p),
        "resposta": resposta or FormularioResposta(),
        "respostas_padrao": [(r, dominio.preencher_resposta(r.mensagem,
                                                            services.valores_dos_marcadores(p)))
                             for r in RespostaPadrao.objects.order_by("tipo")],
        "historico": historico.da_palestra(p),
        "migalhas": _migalhas(("Palestras e eventos", reverse("palestras:lista")), (str(p), "")),
    })
    return contexto


def _erro_do_servico(form, exc: dominio.RegraViolada) -> None:
    form.add_error(exc.campo if exc.campo in form.fields else None, str(exc))


@require_http_methods(["GET", "POST"])
def nova(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_criar(request.user))
    if request.method == "POST":
        form = FormularioPalestra(request.POST)
        if form.is_valid():
            try:
                p = services.criar(request.user, form.cleaned_data)
            except dominio.RegraViolada as exc:
                _erro_do_servico(form, exc)
            else:
                messages.success(request, f"{p} registrada. Ela se grava sozinha daqui em diante.")
                return redirect("palestras:palestra", pk=p.pk)
        messages.error(request, "Corrija os campos destacados para registrar.")
    else:
        form = FormularioPalestra(initial={"data_solicitacao": timezone.localdate()})
    return render(request, "palestras/folha.html", _contexto_folha(request, form, None))


@require_http_methods(["GET", "POST"])
def palestra(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(policies.pode_acessar(request.user))
    objeto = get_object_or_404(queries.base(), pk=pk)
    if request.method == "POST":
        _exigir(policies.pode_editar(request.user))
        form = FormularioPalestra(request.POST, instance=objeto)
        if form.is_valid():
            try:
                services.salvar(request.user, objeto.pk, form.cleaned_data)
            except dominio.RegraViolada as exc:
                _erro_do_servico(form, exc)
            else:
                messages.success(request, "Palestra salva.")
                return redirect("palestras:palestra", pk=objeto.pk)
        messages.error(request, "Corrija os campos destacados para salvar.")
        objeto.refresh_from_db()
    else:
        form = FormularioPalestra(instance=objeto)
    return render(request, "palestras/folha.html", _contexto_folha(request, form, objeto))


@require_POST
def autosave(request: HttpRequest, pk: int) -> JsonResponse:
    _exigir(policies.pode_acessar(request.user))
    objeto = get_object_or_404(Palestra, pk=pk)
    if not policies.pode_editar(request.user):
        return JsonResponse({"salvo": False, "mensagem": "Você não pode alterar palestras."})
    form = FormularioPalestra(request.POST, instance=objeto)
    if not form.is_valid():
        return JsonResponse({"salvo": False, "mensagem": _primeiro_erro(form)})
    try:
        salvo = services.salvar(request.user, objeto.pk, form.cleaned_data)
    except dominio.RegraViolada as exc:
        return JsonResponse({"salvo": False, "mensagem": f"Não salvo: {exc}"})
    return JsonResponse({"salvo": True, "recarregar": False,
                         "em": timezone.localtime(salvo.atualizado_em).strftime("%H:%M")})


def _refazer(request: HttpRequest, objeto: Palestra, **forms_extra) -> HttpResponse:
    contexto = _contexto_folha(request, FormularioPalestra(instance=objeto), objeto, **forms_extra)
    return render(request, "palestras/folha.html", contexto, status=400)


@require_POST
def andamento(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(policies.pode_editar(request.user))
    objeto = get_object_or_404(queries.base(), pk=pk)
    form = FormularioAndamento(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            salvo = services.registrar_andamento(
                request.user, objeto.pk, d["novo_status"], d["anotacao"],
                data_evento=d["data_evento"], palestrante=d["palestrante"],
                quantidade_publico=d["quantidade_publico"])
        except dominio.RegraViolada as exc:
            form.add_error("novo_status", str(exc))
        else:
            messages.success(request, f"Status: {salvo.get_status_display()}.")
            return redirect(reverse("palestras:palestra", args=[objeto.pk]) + "#andamento")
    elif "novo_status" in form.errors:
        form.errors["novo_status"] = form.error_class([dominio.MSG_ESCOLHA])
    messages.error(request, "O andamento não foi registrado: veja o cartão Andamento.")
    return _refazer(request, objeto, andamento=form)


@require_POST
def responder(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(policies.pode_editar(request.user))
    objeto = get_object_or_404(queries.base(), pk=pk)
    form = FormularioResposta(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            services.registrar_resposta(request.user, objeto.pk, d["resposta"], d["texto"],
                                        d["novo_status"])
        except dominio.RegraViolada as exc:
            form.add_error("novo_status" if exc.campo == "novo_status" else "texto", str(exc))
        else:
            messages.success(request, "Resposta registrada no histórico.")
            return redirect(reverse("palestras:palestra", args=[objeto.pk]) + "#resposta")
    messages.error(request, "A resposta não foi registrada: veja o cartão Resposta.")
    return _refazer(request, objeto, resposta=form)


# ------------------------------------------------------------------ cadastros de apoio
CADASTROS = {
    "palestrantes": ("Palestrantes", "users", "palestras:palestrantes"),
    "temas": ("Temas", "list-checks", "palestras:temas"),
    "respostas": ("Respostas padrão", "mail", "palestras:respostas"),
}


def _cadastro(request: HttpRequest, tipo: str) -> HttpResponse:
    _exigir(policies.pode_gerir_cadastros(request.user))
    titulo, icone, url = CADASTROS[tipo]
    modelo: Any = {"temas": Tema, "palestrantes": Palestrante, "respostas": RespostaPadrao}[tipo]
    erro, editando = "", None
    form = FormularioPalestrante() if tipo == "palestrantes" else None
    editado: FormularioPalestrante | None = None
    valores: dict[str, str] = {}
    if request.method == "POST":
        pk = request.POST.get("pk") or ""
        pk_int = int(pk) if pk.isdigit() else None
        try:
            if request.POST.get("acao") == "excluir" and pk_int:
                nome = services.excluir_cadastro(request.user, tipo, pk_int)
                messages.success(request, f"“{nome}” excluído.")
                return redirect(url)
            if tipo == "temas":
                services.salvar_tema(request.user, request.POST.get("nome", ""), pk_int)
            elif tipo == "respostas":
                services.salvar_resposta_padrao(request.user, request.POST.get("tipo", ""),
                                                request.POST.get("mensagem", ""), pk_int)
            else:
                instancia = Palestrante.objects.get(pk=pk_int) if pk_int else None
                enviado = FormularioPalestrante(request.POST, instance=instancia,
                                                prefix=f"p{pk_int}" if pk_int else None)
                if pk_int:
                    editado = enviado
                else:
                    form = enviado
                if not enviado.is_valid():
                    raise dominio.RegraViolada("Corrija os campos destacados.")
                services.salvar_palestrante(request.user, enviado.cleaned_data, pk_int)
            messages.success(request, "Salvo.")
            return redirect(url)
        except modelo.DoesNotExist as exc:
            raise Http404 from exc
        except dominio.RegraViolada as exc:
            erro, editando = str(exc), pk_int
            valores = {k: request.POST.get(k, "") for k in ("nome", "tipo", "mensagem")}
    registros = list(modelo.objects.order_by("tipo" if tipo == "respostas" else "nome"))
    usos = (services.usos_de_temas() if tipo == "temas"
            else services.usos_de_palestrantes() if tipo == "palestrantes" else {})
    for r in registros:
        r.usos = usos.get(r.pk, 0)
        if tipo == "palestrantes":
            r.form = (editado if editado is not None and editando == r.pk
                      else FormularioPalestrante(instance=r, prefix=f"p{r.pk}"))
    return render(request, "palestras/cadastro.html", {
        "tipo": tipo, "titulo": titulo, "icone": icone, "registros": registros, "erro": erro,
        "editando": editando, "valores": valores, "form": form,
        "outros": [(t, c) for t, c in CADASTROS.items() if t != tipo],
        "marcadores": dominio.MARCADORES,
        "migalhas": _migalhas((titulo, "")),
    })


@require_http_methods(["GET", "POST"])
def palestrantes(request: HttpRequest) -> HttpResponse:
    return _cadastro(request, "palestrantes")


@require_http_methods(["GET", "POST"])
def temas(request: HttpRequest) -> HttpResponse:
    return _cadastro(request, "temas")


@require_http_methods(["GET", "POST"])
def respostas(request: HttpRequest) -> HttpResponse:
    return _cadastro(request, "respostas")
