"""Telas do atendimento à imprensa (paridade com `atendimento_imprensa/views.py` da
referência): painel, lista com filas e filtros, exportação CSV, a folha do atendimento
(nova e existente, que se grava sozinha), o registro de andamento e os cadastros de apoio.
"""

from __future__ import annotations

import csv
from datetime import time
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import dominio, historico, policies, queries, services
from .forms import FORM_ID, FormularioAndamento, FormularioAtendimento
from .models import Atendimento, Integrante, Veiculo

POR_PAGINA = 25
NOMES_DOS_MESES = queries.NOMES_DOS_MESES


def _exigir(condicao: bool) -> None:
    if not condicao:
        raise PermissionDenied


def _migalhas(*itens: tuple[str, str]) -> list[tuple[str, str]]:
    return [("Início", reverse("painel:inicio")), ("Imprensa", reverse("imprensa:painel")),
            *itens]


# ------------------------------------------------------------------ painel
@require_GET
def painel(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_acessar(request.user))
    hoje = timezone.localdate()
    inicio = queries.inicio_do_mes(hoje)
    mes = queries.resumo_do_mes(hoje)
    abertos = queries.em_aberto().count()
    vencidos = queries.em_aberto().filter(deadline__lt=hoje).count()
    pendentes = list(queries.base().filter(situacao__in=dominio.ABERTAS)
                     .order_by("deadline", "data", "horario")[:8])
    recentes = list(queries.base().order_by("-data", "-horario", "-pk")[:8])
    por_responsavel = queries.por_responsavel(inicio)
    por_veiculo = queries.por_veiculo(inicio)
    maior_veiculo = max((v["total"] for v in por_veiculo), default=0)
    maior_responsavel = max((r["total"] for r in por_responsavel), default=0)
    return render(request, "imprensa/painel.html", {
        "mes": mes, "abertos": abertos, "vencidos": vencidos, "inicio": inicio,
        "mes_rotulo": f"{NOMES_DOS_MESES[hoje.month - 1]} de {hoje.year}",
        "percentual": dominio.percentual(mes["atendidos"], mes["total"]),
        "pendentes": [queries.linha(a, hoje) for a in pendentes],
        "recentes": [queries.linha(a, hoje) for a in recentes],
        "por_veiculo": por_veiculo, "maior_veiculo": maior_veiculo,
        "por_responsavel": por_responsavel, "maior_responsavel": maior_responsavel,
        "grafico": queries.serie_mensal(hoje),
        "pode_criar": policies.pode_criar(request.user),
        "pode_gerir_cadastros": policies.pode_gerir_cadastros(request.user),
        "migalhas": [("Início", reverse("painel:inicio")), ("Imprensa", "")],
    })


# ------------------------------------------------------------------ lista e exportação
def _querystring(request: HttpRequest, *sem: str) -> str:
    pares = [(k, v) for k, valores in request.GET.lists() for v in valores
             if k not in sem and v]
    return urlencode(pares)


def _base_da_paginacao(request: HttpRequest) -> str:
    """Os filtros atuais sem a página, prontos para receber "pagina=N" (paginacao.html)."""
    texto = _querystring(request, "pagina")
    return f"{texto}&" if texto else ""


@require_GET
def lista(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_acessar(request.user))
    hoje = timezone.localdate()
    filtros = queries.ler_filtros(request.GET)
    sem_fila = queries.filtrar(filtros, hoje, com_fila=False)
    contagens = queries.contagens_das_filas(sem_fila)
    qs = queries.filtrar(filtros, hoje)
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    abas = [("", "Todos", contagens[""]),
            *((chave, rotulo, contagens[chave]) for chave, rotulo, _s in dominio.FILAS)]
    return render(request, "imprensa/lista.html", {
        "page_obj": pagina, "linhas": [queries.linha(a, hoje) for a in pagina.object_list],
        "filtros": filtros, "abas": abas, "fila": filtros.fila,
        "qs_sem_fila": _querystring(request, "fila", "pagina"),
        "querystring_base": _base_da_paginacao(request),
        "situacoes": Atendimento.Situacao.choices,
        "veiculos": Veiculo.objects.order_by("nome"),
        "equipe": Integrante.objects.order_by("nome"),
        "url_exportar": reverse("imprensa:exportar") + (
            f"?{_querystring(request, 'pagina')}" if request.GET else ""),
        "pode_criar": policies.pode_criar(request.user),
        "migalhas": _migalhas(("Atendimentos", "")),
    })


def _hora(valor: time | None) -> str:
    return valor.strftime("%H:%M") if valor else ""


@require_GET
def exportar(request: HttpRequest) -> HttpResponse:
    """A lista filtrada em CSV (";" e BOM, para abrir no Excel), como na referência."""
    _exigir(policies.pode_acessar(request.user))
    hoje = timezone.localdate()
    qs = queries.filtrar(queries.ler_filtros(request.GET), hoje)
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = (
        f'attachment; filename="atendimento-imprensa-{hoje:%Y-%m-%d}.csv"')
    resposta.write("﻿")
    escritor = csv.writer(resposta, delimiter=";", lineterminator="\r\n")
    escritor.writerow(["Data", "Horário", "Jornalista", "Veículo", "Contato", "Pedido",
                       "Situação", "Responsável", "Deadline / veiculação",
                       "Horário da resposta", "Responsável pela resposta", "Fontes",
                       "Início do pedido", "Retorno das fontes", "Andamento", "Resposta"])
    for a in qs.iterator(chunk_size=500):
        escritor.writerow([
            f"{a.data:%d/%m/%Y}", _hora(a.horario), a.jornalista,
            a.veiculo.nome if a.veiculo else "", a.contato, a.pedido,
            a.get_situacao_display(), a.responsavel.nome if a.responsavel else "",
            f"{a.deadline:%d/%m/%Y}" if a.deadline else "", _hora(a.horario_resposta),
            a.responsavel_resposta.nome if a.responsavel_resposta else "",
            a.fonte, a.inicio_pedido, a.final_pedido, a.andamento, a.resposta])
    return resposta


# ------------------------------------------------------------------ folha
def _primeiro_erro(form) -> str:
    for nome, erros in form.errors.items():
        rotulo = form.fields[nome].label if nome in form.fields else ""
        texto = erros[0] if erros else ""
        return f"Não salvo: {rotulo} — {texto}" if rotulo else f"Não salvo: {texto}"
    return "Não salvo."


def _contexto_folha(request: HttpRequest, form: FormularioAtendimento,
                    atendimento: Atendimento | None,
                    andamento: FormularioAndamento | None = None) -> dict:
    hoje = timezone.localdate()
    contexto = {
        "form": form, "form_id": FORM_ID, "atendimento": atendimento,
        "editavel": policies.pode_editar(request.user) if atendimento
        else policies.pode_criar(request.user),
        "jornalistas": list(Atendimento.objects.order_by("jornalista")
                            .values_list("jornalista", flat=True).distinct()[:400]),
        "voltar": reverse("imprensa:lista"),
    }
    if atendimento is None:
        contexto["migalhas"] = _migalhas(("Atendimentos", reverse("imprensa:lista")),
                                         ("Novo atendimento", ""))
        return contexto
    contexto.update({
        "prazo": dominio.selo_do_deadline(atendimento.deadline, atendimento.situacao, hoje),
        "fontes": dominio.fontes_alinhadas(atendimento.fonte, atendimento.inicio_pedido,
                                           atendimento.final_pedido),
        "andamento": andamento or FormularioAndamento(),
        "situacoes": [(v, r, dominio.DICAS[v], v == atendimento.situacao)
                      for v, r, _d, _t in dominio.SITUACOES],
        "dica_atual": dominio.DICAS.get(atendimento.situacao, ""),
        "ultima_anotacao": services.ultima_anotacao(atendimento),
        "historico": historico.do_atendimento(atendimento),
        "migalhas": _migalhas(("Atendimentos", reverse("imprensa:lista")), (str(atendimento), "")),
    })
    return contexto


def _erro_do_servico(form, exc: services.AtendimentoInvalido) -> None:
    form.add_error(exc.campo if exc.campo in form.fields else None, str(exc))


@require_http_methods(["GET", "POST"])
def novo(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_criar(request.user))
    if request.method == "POST":
        form = FormularioAtendimento(request.POST)
        if form.is_valid():
            try:
                atendimento = services.criar(request.user, form.cleaned_data)
            except services.AtendimentoInvalido as exc:
                _erro_do_servico(form, exc)
            else:
                messages.success(request, f"{atendimento} registrado. Ele se grava sozinho "
                                          "daqui em diante.")
                return redirect("imprensa:atendimento", pk=atendimento.pk)
        messages.error(request, "Corrija os campos destacados para registrar.")
    else:
        agora = timezone.localtime()
        form = FormularioAtendimento(initial={
            "data": agora.date(), "horario": agora.time().replace(second=0, microsecond=0)})
    return render(request, "imprensa/folha.html", _contexto_folha(request, form, None))


@require_http_methods(["GET", "POST"])
def atendimento(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(policies.pode_acessar(request.user))
    objeto = get_object_or_404(queries.base(), pk=pk)
    if request.method == "POST":
        _exigir(policies.pode_editar(request.user))
        form = FormularioAtendimento(request.POST, instance=objeto)
        if form.is_valid():
            try:
                services.salvar(request.user, objeto.pk, form.cleaned_data)
            except services.AtendimentoInvalido as exc:
                _erro_do_servico(form, exc)
            else:
                messages.success(request, "Atendimento salvo.")
                return redirect("imprensa:atendimento", pk=objeto.pk)
        messages.error(request, "Corrija os campos destacados para salvar.")
        objeto.refresh_from_db()
    else:
        form = FormularioAtendimento(instance=objeto)
    return render(request, "imprensa/folha.html", _contexto_folha(request, form, objeto))


@require_POST
def autosave(request: HttpRequest, pk: int) -> JsonResponse:
    """Grava a folha a cada pausa (componentes/autosave.js), quando o formulário é válido;
    senão diz o que impede, no status da barra."""
    _exigir(policies.pode_acessar(request.user))
    objeto = get_object_or_404(Atendimento, pk=pk)
    if not policies.pode_editar(request.user):
        return JsonResponse({"salvo": False, "mensagem": "Você não pode alterar atendimentos."})
    form = FormularioAtendimento(request.POST, instance=objeto)
    if not form.is_valid():
        return JsonResponse({"salvo": False, "mensagem": _primeiro_erro(form)})
    veiculo_novo = bool((form.cleaned_data.get("veiculo_novo") or "").strip())
    try:
        salvo = services.salvar(request.user, objeto.pk, form.cleaned_data)
    except services.AtendimentoInvalido as exc:
        return JsonResponse({"salvo": False, "mensagem": f"Não salvo: {exc}"})
    # Veículo novo entra na lista de veículos: a tela é redesenhada para mostrá-lo escolhido.
    return JsonResponse({"salvo": True, "recarregar": veiculo_novo,
                         "em": timezone.localtime(salvo.atualizado_em).strftime("%H:%M")})


@require_POST
def andamento(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(policies.pode_editar(request.user))
    objeto = get_object_or_404(queries.base(), pk=pk)
    form = FormularioAndamento(request.POST)
    if form.is_valid():
        try:
            salvo = services.registrar_andamento(request.user, objeto.pk,
                                                 form.cleaned_data["nova_situacao"],
                                                 form.cleaned_data["anotacao"])
        except services.AtendimentoInvalido as exc:
            form.add_error("nova_situacao", str(exc))
        else:
            messages.success(request, f"Situação: {salvo.get_situacao_display()}.")
            return redirect(reverse("imprensa:atendimento", args=[objeto.pk]) + "#andamento")
    elif "nova_situacao" in form.errors:
        form.errors["nova_situacao"] = form.error_class([dominio.MSG_ESCOLHA])
    messages.error(request, "O andamento não foi registrado: veja o cartão Andamento.")
    contexto = _contexto_folha(request, FormularioAtendimento(instance=objeto), objeto, form)
    return render(request, "imprensa/folha.html", contexto, status=400)


# ------------------------------------------------------------------ cadastros de apoio
CADASTROS = {
    "equipe": {"titulo": "Equipe", "singular": "integrante", "novo": "Novo integrante",
               "exemplo": "Ex.: Mariana", "icone": "users",
               "intro": "Nome curto usado como responsável pelo atendimento e pela resposta.",
               "url": "imprensa:equipe", "modulo": "Imprensa", "uso_icone": "messages-square",
               "uso": "atendimento,atendimentos"},
    "veiculos": {"titulo": "Veículos de imprensa", "singular": "veículo",
                 "novo": "Novo veículo", "exemplo": "Ex.: RPC", "icone": "radio",
                 "intro": "Veículo que fez o pedido (TV, rádio, portal, jornal). Também entra "
                          "pelo campo “Outro veículo” do atendimento.",
                 "url": "imprensa:veiculos", "modulo": "Imprensa",
                 "uso_icone": "messages-square", "uso": "atendimento,atendimentos"},
}


def _cadastro(request: HttpRequest, tipo: str) -> HttpResponse:
    _exigir(policies.pode_gerir_cadastros(request.user))
    meta = CADASTROS[tipo]
    modelo = services.TIPOS[tipo]
    erro, valor, editando = "", "", None
    if request.method == "POST":
        acao = request.POST.get("acao")
        pk = request.POST.get("pk")
        pk_int = int(pk) if pk and pk.isdigit() else None
        try:
            if acao == "excluir" and pk_int:
                nome = services.excluir_cadastro(request.user, tipo, pk_int)
                messages.success(request, f"“{nome}” excluído.")
            else:
                registro = services.salvar_cadastro(request.user, tipo,
                                                    request.POST.get("nome", ""), pk_int)
                messages.success(request, f"“{registro.nome}” salvo.")
            return redirect(meta["url"])
        except modelo.DoesNotExist as exc:
            raise Http404 from exc
        except services.AtendimentoInvalido as exc:
            erro, valor, editando = str(exc), request.POST.get("nome", ""), pk_int
    registros = list(modelo.objects.order_by("nome"))
    usos = services.usos_por_registro(tipo)
    for r in registros:
        r.usos = usos.get(r.pk, 0)
    return render(request, "arquetipos/cadastro_nomes.html", {
        "tipo": tipo, "meta": meta, "registros": registros, "erro": erro, "valor": valor,
        "editando": editando, "outros": [(t, m) for t, m in CADASTROS.items() if t != tipo],
        "migalhas": _migalhas((meta["titulo"], "")),
    })


@require_http_methods(["GET", "POST"])
def equipe(request: HttpRequest) -> HttpResponse:
    return _cadastro(request, "equipe")


@require_http_methods(["GET", "POST"])
def veiculos(request: HttpRequest) -> HttpResponse:
    return _cadastro(request, "veiculos")
