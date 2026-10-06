"""Telas das solicitações de coffee break (CB2): lista com a situação financeira, filtros e
CSV; a folha da solicitação (etapa 1: o evento e a ordem de serviço) com o lote que o
município recebe; cancelar, reativar, excluir, duplicar; e a lista de lotes com o saldo."""

from __future__ import annotations

import csv
from datetime import date, datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from gestao.cadastros.forms import resolver_municipio

from . import dominio_pedido as regras
from . import pedidos, policies, queries
from .forms_pedido import FORM_ID, MSG_TRAVADOS, FormularioSolicitacao
from .models import Fornecedor, Lote, Solicitacao

POR_PAGINA = 25
# A trilha na ordem do fluxo, com rótulos curtos (cabem na largura).
ABAS = (("aguardando_nota", "Aguardando nota"), ("aguardando_protocolo", "Aguardando protocolo"),
        ("aguardando_atesto", "Aguardando atesto"), ("aguardando_ob", "Aguardando OB"),
        ("aguardando_envio", "Aguardando envio"), ("concluida", "Concluídas"),
        ("cancelada", "Canceladas"))
COLUNAS = ("Nº", "Lote", "Fornecedor", "Data da solicitação", "Evento", "Período",
           "Local de entrega", "Endereço", "Bairro", "CEP", "Quantidade", "Quantidade faturada",
           "Valor unitário", "Valor", "Nota fiscal", "Protocolo", "Atesto GAF", "Ordem bancária",
           "Envio à empresa", "Situação", "Criado por")


def _exigir(request: HttpRequest) -> None:
    if not policies.pode_acessar(request.user):
        raise PermissionDenied


def _migalhas(*fim: tuple[str, str]) -> list[tuple[str, str]]:
    return [("Início", reverse("painel:inicio")),
            ("Coffee Break", reverse("coffee:solicitacoes")), *fim]


def _data(texto: str | None) -> date | None:
    try:
        return datetime.strptime((texto or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        try:
            return date.fromisoformat((texto or "").strip())
        except ValueError:
            return None


def _inteiro(texto: str | None) -> int | None:
    texto = (texto or "").strip()
    return int(texto) if texto.isdecimal() and len(texto) <= 9 else None


def _filtros(get) -> dict:
    return {"q": " ".join((get.get("q") or "").split())[:100], "lote": _inteiro(get.get("lote")),
            "fornecedor": _inteiro(get.get("fornecedor")), "de": _data(get.get("de")),
            "ate": _data(get.get("ate")), "situacao": get.get("situacao") or "",
            "pendentes": get.get("pendentes") == "1"}


def _base():
    return Solicitacao.objects.select_related("lote__contrato__fornecedor", "municipio",
                                              "criado_por")


def _linha(s: Solicitacao, hoje: date) -> dict:
    if s.data_evento is None:
        tempo = None
    elif s.data_evento < hoje:
        tempo = ("Realizado", "sucesso")
    elif s.data_evento == hoje:
        tempo = ("Acontecendo", "info")
    else:
        tempo = ("Previsto", "neutro")
    fatos = [("calendar", "Evento", f"{s.data_evento:%d/%m/%Y}" if s.data_evento
              else "Sem data do evento", s.data_evento is None),
             ("users", "Quantidade", f"{s.quantidade} pessoas", False),
             ("layers", "Lote", f"{s.lote} · {s.lote.contrato.fornecedor}", False),
             ("map-pin", "Município", s.municipio.nome, False)]
    if s.nota_fiscal:
        fatos.append(("receipt", "Nota fiscal", f"NF {s.nota_fiscal}", False))
    fatos.append(("clock", "Solicitada", f"Solicitada em {s.data_solicitacao:%d/%m/%Y}", False))
    return {"s": s, "tempo": tempo if not s.cancelada else None, "fatos": fatos}


@require_GET
def lista(request: HttpRequest) -> HttpResponse:
    _exigir(request)
    hoje = timezone.localdate()
    f = _filtros(request.GET)
    ativos = sum(bool(f[k]) for k in ("lote", "fornecedor", "de", "ate"))
    sem_situacao = queries.filtrar(_base(), **{**f, "situacao": "", "pendentes": False})
    contagens = queries.contagens_por_situacao(sem_situacao)
    qs = queries.filtrar(_base(), **f).order_by("-data_solicitacao", "-pk")
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    base = urlencode([(k, v) for k, vs in request.GET.lists() for v in vs if k != "pagina" and v])
    sem_sit = urlencode([(k, v) for k, vs in request.GET.lists() for v in vs
                         if k not in ("pagina", "situacao", "pendentes") and v])
    return render(request, "coffee/lista.html", {
        "page_obj": pagina, "linhas": [_linha(s, hoje) for s in pagina.object_list],
        "f": f, "ativos": ativos, "querystring_base": f"{base}&" if base else "",
        "qs_sem_situacao": sem_sit,
        "situacoes": [(c, r, contagens[c]) for c, r in ABAS],
        "total": contagens["total"],
        "lotes": Lote.objects.select_related("contrato").order_by("-exercicio", "numero"),
        "fornecedores": Fornecedor.objects.order_by("razao_social"),
        "url_exportar": reverse("coffee:exportar") + (f"?{base}" if base else ""),
        "migalhas": _migalhas(("Solicitações", "")),
    })


def _celula(valor):
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{valor}"
    return valor


def _d(v) -> str:
    return f"{v:%d/%m/%Y}" if v else ""


@require_GET
def exportar(request: HttpRequest) -> HttpResponse:
    """O recorte atual em CSV (";", BOM, decimais com vírgula), 21 colunas da referência."""
    _exigir(request)
    hoje = timezone.localdate()
    qs = queries.filtrar(_base(), **_filtros(request.GET)).order_by("-data_solicitacao", "-pk")
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="coffee-break-{hoje:%Y-%m-%d}.csv"'
    resposta.write("﻿")
    escritor = csv.writer(resposta, delimiter=";", lineterminator="\r\n")
    escritor.writerow(COLUNAS)
    for s in qs.iterator(chunk_size=500):
        unit = f"{s.valor_unitario:.4f}".replace(".", ",") if s.valor_unitario else ""
        valor = f"{s.valor:.2f}".replace(".", ",") if s.valor is not None else ""
        escritor.writerow([_celula(v) for v in (
            s.numero, str(s.lote), s.lote.contrato.fornecedor.razao_social,
            _d(s.data_solicitacao), s.descricao, _d(s.data_evento), s.local_entrega,
            s.endereco, s.bairro, s.cep, s.quantidade, s.quantidade_faturada or "", unit, valor,
            s.nota_fiscal, s.protocolo_pagamento, _d(s.atesto_em), _d(s.ordem_bancaria_em),
            _d(s.envio_empresa_em), s.situacao_rotulo, s.criado_por.nome)])
    return resposta


def _historico(s: Solicitacao) -> list:
    return list(s.movimentos.select_related("usuario")[:50])


def _contexto(request: HttpRequest, form: FormularioSolicitacao, s: Solicitacao | None,
              duplicada: Solicitacao | None = None) -> dict:
    hoje = timezone.localdate()
    ctx: dict = {"form": form, "s": s, "form_id": FORM_ID, "duplicada": duplicada,
                 "proximo_numero": queries.proximo_numero(hoje.year),
                 "msg_travados": MSG_TRAVADOS if form.travado else "",
                 "numero_ano": f"/ {(s.data_solicitacao if s else hoje).year}"}
    if s is not None:
        sal = queries.saldo(s.lote)
        ctx.update({
            "saldo": sal, "fim_vigencia": s.lote.contrato.fim_efetivo(),
            "historico": _historico(s), "linha": _linha(s, hoje),
            "aviso_antecedencia": regras.aviso_antecedencia(
                s.data_evento, hoje, s.lote.contrato.antecedencia_minima_dias,
                s.lote.contrato.numero) if not s.bloqueada else "",
            "migalhas": _migalhas(("Solicitações", reverse("coffee:solicitacoes")), (str(s), "")),
        })
    else:
        ctx["migalhas"] = _migalhas(("Solicitações", reverse("coffee:solicitacoes")),
                                    ("Nova solicitação", ""))
    return ctx


def _gravar(request: HttpRequest, form: FormularioSolicitacao, s: Solicitacao | None,
            duplicada: Solicitacao | None):
    try:
        r = pedidos.salvar(request.user, form.cleaned_data, s,
                           retroativo=form.cleaned_data.get("retroativo", False),
                           justificativa=form.cleaned_data.get("justificativa", ""),
                           duplicada_de=duplicada,
                           versao=form.cleaned_data.get("versao") if s is not None else None)
    except pedidos.PedidoInvalido as exc:
        form.add_error(exc.campo if exc.campo in form.fields else None, str(exc))
        return None
    if r.aviso:
        messages.warning(request, r.aviso)
    return r.solicitacao


@require_http_methods(["GET", "POST"])
def nova(request: HttpRequest) -> HttpResponse:
    _exigir(request)
    duplicada = None
    if (pk := _inteiro(request.GET.get("duplicar") or request.POST.get("duplicada_de"))):
        duplicada = get_object_or_404(Solicitacao, pk=pk)
    if request.method == "POST":
        form = FormularioSolicitacao(request.POST)
        if form.is_valid() and (s := _gravar(request, form, None, duplicada)) is not None:
            messages.success(request, f"Solicitação {s.numero} registrada no {s.lote} "
                                      f"({s.lote.contrato.fornecedor}). A ordem de serviço já "
                                      "pode ser gerada.")
            return redirect("coffee:solicitacoes")
        messages.error(request, "Corrija os campos destacados para continuar.")
        return render(request, "coffee/folha.html", _contexto(request, form, None, duplicada),
                      status=422)
    inicial: dict = {}
    if duplicada is not None:
        inicial = {**pedidos.dados_para_duplicar(duplicada), "duplicada_de": duplicada.pk}
    if (inicio := _data(request.GET.get("inicio"))):
        inicial["data_evento"] = inicio
    return render(request, "coffee/folha.html",
                  _contexto(request, FormularioSolicitacao(initial=inicial), None, duplicada))


@require_http_methods(["GET", "POST"])
def solicitacao(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(request)
    s = get_object_or_404(_base(), pk=pk)
    if request.method == "POST":
        if s.bloqueada:
            messages.error(request, regras.MSG_BLOQUEADA)
            return redirect("coffee:solicitacao", pk=pk)
        form = FormularioSolicitacao(request.POST, solicitacao=s)
        if form.is_valid() and _gravar(request, form, s, None) is not None:
            messages.success(request, "Solicitação de coffee break atualizada.")
            return redirect("coffee:solicitacoes")
        messages.error(request, "Corrija os campos destacados para continuar.")
        return render(request, "coffee/folha.html", _contexto(request, form, s), status=422)
    return render(request, "coffee/folha.html",
                  _contexto(request, FormularioSolicitacao(solicitacao=s), s))


@require_GET
def lote_do_municipio(request: HttpRequest) -> HttpResponse:
    """Trecho da folha: o lote que o município recebe (lote, fornecedor, contrato, saldo,
    empenho, vigência) — ou por que nenhum atende."""
    _exigir(request)
    info, erro = None, ""
    texto = (request.GET.get("municipio") or "").strip()
    data = _data(request.GET.get("data_evento")) or _data(
        request.GET.get("data_solicitacao")) or timezone.localdate()
    if texto:
        try:
            municipio = resolver_municipio(texto)
        except ValidationError as exc:
            erro = " ".join(exc.messages)
        else:
            info = queries.lote_para(municipio, data) if municipio.uf == "PR" else None
            if info is None and not erro:
                erro = (regras.MSG_SEM_LOTE.format(municipio=f"{municipio.nome}/{municipio.uf}")
                        if municipio.uf == "PR" else "Escolha um município do Paraná.")
    return render(request, "coffee/_lote.html", {
        "erro": erro, "lote": info.lote if info else None, "sal": info.saldo if info else None,
        "fim": info.fim if info else None, "proximidade": info.proximidade if info else "",
        "vencido": info.vencido if info else False})


def _acao(request: HttpRequest, pk: int, fazer, sucesso: str) -> HttpResponse:
    _exigir(request)
    get_object_or_404(Solicitacao, pk=pk)
    try:
        resultado = fazer()
    except pedidos.PedidoInvalido as exc:
        messages.error(request, str(exc))
        return redirect("coffee:solicitacao", pk=pk)
    messages.success(request, sucesso.format(r=resultado))
    return redirect("coffee:solicitacoes" if isinstance(resultado, str)
                    else reverse("coffee:solicitacao", args=[pk]))


@require_POST
def cancelar(request: HttpRequest, pk: int) -> HttpResponse:
    return _acao(request, pk, lambda: pedidos.cancelar(request.user, pk,
                                                       request.POST.get("motivo") or ""),
                 "Solicitação cancelada — a quantidade voltou ao saldo do lote.")


@require_POST
def reativar(request: HttpRequest, pk: int) -> HttpResponse:
    return _acao(request, pk, lambda: pedidos.reativar(request.user, pk),
                 "Solicitação reativada e saldo consumido.")


@require_POST
def excluir(request: HttpRequest, pk: int) -> HttpResponse:
    return _acao(request, pk, lambda: pedidos.excluir(request.user, pk),
                 "Solicitação {r} excluída — a quantidade voltou ao saldo do lote.")


@require_GET
def lotes(request: HttpRequest) -> HttpResponse:
    """Lotes com o saldo: "R de T unidades" e o selo de consumo (verde < 70%, âmbar ≥ 70%,
    vermelho ≥ 90%)."""
    _exigir(request)
    situacao = request.GET.get("situacao") or "ativos"
    qs = (Lote.objects.select_related("contrato__fornecedor").prefetch_related(
        "municipios", "contrato__aditivos").order_by("-exercicio", "numero", "pk"))
    if situacao == "ativos":
        qs = qs.filter(ativo=True)
    elif situacao == "inativos":
        qs = qs.filter(ativo=False)
    lista_lotes = list(qs)
    sal = queries.saldos(lista_lotes)
    hoje = timezone.localdate()
    linhas = []
    for lote in lista_lotes:
        fim = lote.contrato.fim_efetivo()
        linhas.append({"lote": lote, "saldo": sal[lote.pk], "fim": fim,
                       "vencido": bool(fim and fim < hoje)})
    return render(request, "coffee/lotes.html", {
        "linhas": linhas,
        "situacao": situacao, "pode_gerir": policies.pode_gerir_cadastros(request.user),
        "situacoes": (("ativos", "Vigentes"), ("inativos", "Encerrados"), ("todos", "Todos")),
        "migalhas": _migalhas(("Lotes", "")),
    })
