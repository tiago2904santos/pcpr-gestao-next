"""Telas do controle de publicações (paridade com `publicacoes/views.py` da referência):
painel, lista com filas e filtros, exportação CSV, a folha da pauta (nova e existente, que
se grava sozinha), o registro de andamento e os cadastros de apoio.
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
from .forms import FORM_ID, FormularioAndamento, FormularioPauta
from .models import Integrante, Publicacao, UnidadeResponsavel

POR_PAGINA = 25


def _exigir(condicao: bool) -> None:
    if not condicao:
        raise PermissionDenied


def _migalhas(*itens: tuple[str, str]) -> list[tuple[str, str]]:
    return [("Início", reverse("painel:inicio")),
            ("Publicações", reverse("publicacoes:painel")), *itens]


# ------------------------------------------------------------------ painel
@require_GET
def painel(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_acessar(request.user))
    hoje = timezone.localdate()
    inicio = queries.inicio_do_mes(hoje)
    mes = queries.resumo_do_mes(hoje)
    tempo, amostra = queries.tempo_medio(hoje)
    abertas = list(queries.base().filter(status__in=dominio.ABERTOS)
                   .order_by("data", "inicio_pauta", "pk")[:8])
    recentes = list(queries.base().order_by("-data", "-inicio_pauta", "-pk")[:8])
    por_jornalista = queries.por_jornalista(inicio)
    por_unidade = queries.por_unidade(inicio)
    return render(request, "publicacoes/painel.html", {
        "mes": mes, "abertas_total": queries.em_aberto().count(), "inicio": inicio,
        "tempo": tempo, "amostra": amostra,
        "mes_rotulo": f"{queries.NOMES_DOS_MESES[hoje.month - 1]} de {hoje.year}",
        "percentual": dominio.percentual(mes["publicadas"], mes["total"]),
        "abertas": [queries.linha(p) for p in abertas],
        "recentes": [queries.linha(p) for p in recentes],
        "por_jornalista": por_jornalista,
        "maior_jornalista": max((j["total"] for j in por_jornalista), default=0),
        "por_unidade": por_unidade,
        "maior_unidade": max((u["total"] for u in por_unidade), default=0),
        "grafico": queries.serie_mensal(hoje),
        "pode_criar": policies.pode_criar(request.user),
        "pode_gerir_cadastros": policies.pode_gerir_cadastros(request.user),
        "migalhas": [("Início", reverse("painel:inicio")), ("Publicações", "")],
    })


# ------------------------------------------------------------------ lista e exportação
def _querystring(request: HttpRequest, *sem: str) -> str:
    return urlencode([(k, v) for k, valores in request.GET.lists() for v in valores
                      if k not in sem and v])


def _base_da_paginacao(request: HttpRequest) -> str:
    texto = _querystring(request, "pagina")
    return f"{texto}&" if texto else ""


@require_GET
def lista(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_acessar(request.user))
    filtros = queries.ler_filtros(request.GET)
    contagens = queries.contagens_das_filas(queries.filtrar(filtros, com_fila=False))
    pagina = Paginator(queries.filtrar(filtros), POR_PAGINA).get_page(request.GET.get("pagina"))
    abas = [("", "Todas", contagens[""]),
            *((chave, rotulo, contagens[chave]) for chave, rotulo, _s in dominio.FILAS)]
    return render(request, "publicacoes/lista.html", {
        "page_obj": pagina, "linhas": [queries.linha(p) for p in pagina.object_list],
        "filtros": filtros, "abas": abas, "fila": filtros.fila,
        "qs_sem_fila": _querystring(request, "fila", "pagina"),
        "querystring_base": _base_da_paginacao(request),
        "status": Publicacao.Status.choices,
        "equipe": Integrante.objects.order_by("nome"),
        "unidades": UnidadeResponsavel.objects.order_by("nome"),
        "url_exportar": reverse("publicacoes:exportar") + (
            f"?{_querystring(request, 'pagina')}" if request.GET else ""),
        "pode_criar": policies.pode_criar(request.user),
        "migalhas": _migalhas(("Pautas", "")),
    })


def _hora(valor: time | None) -> str:
    return valor.strftime("%H:%M") if valor else ""


@require_GET
def exportar(request: HttpRequest) -> HttpResponse:
    """A lista filtrada em CSV (";" e BOM, para abrir no Excel), como na referência."""
    _exigir(policies.pode_acessar(request.user))
    qs = queries.filtrar(queries.ler_filtros(request.GET))
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = (
        f'attachment; filename="publicacoes-{timezone.localdate():%Y-%m-%d}.csv"')
    resposta.write("﻿")
    escritor = csv.writer(resposta, delimiter=";", lineterminator="\r\n")
    escritor.writerow(["Data", "Jornalista", "Unidade", "Fonte", "Início da pauta", "Título",
                       "Status", "Andamento", "Colocada para edição", "Data de publicação",
                       "Horário de publicação", "Revisão", "Galeria de fotos",
                       "Bitly nos grupos", "Enviado à SESP", "Publicado na AEN",
                       "Link PCPR", "Link AEN", "Tempo até publicar"])
    for p in qs.iterator(chunk_size=500):
        escritor.writerow([
            f"{p.data:%d/%m/%Y}", p.jornalista.nome, p.unidade.nome if p.unidade else "",
            p.fonte, _hora(p.inicio_pauta), p.titulo, p.get_status_display(), p.andamento,
            _hora(p.colocada_edicao),
            f"{p.data_publicacao:%d/%m/%Y}" if p.data_publicacao else "",
            _hora(p.horario_publicacao), p.revisao.nome if p.revisao else "",
            p.galeria_fotos.nome if p.galeria_fotos else "", dominio.sim_nao(p.bitly_grupos),
            dominio.sim_nao(p.enviado_sesp), dominio.sim_nao(p.publicado_aen), p.link_site,
            p.link_aen, p.tempo_ate_publicar_texto])
    return resposta


# ------------------------------------------------------------------ folha
def _primeiro_erro(form) -> str:
    for nome, erros in form.errors.items():
        rotulo = form.fields[nome].label if nome in form.fields else ""
        texto = erros[0] if erros else ""
        return f"Não salvo: {rotulo} — {texto}" if rotulo else f"Não salvo: {texto}"
    return "Não salvo."


def _contexto_folha(request: HttpRequest, form: FormularioPauta, pauta: Publicacao | None,
                    andamento: FormularioAndamento | None = None) -> dict:
    contexto = {
        "form": form, "form_id": FORM_ID, "pauta": pauta,
        "editavel": policies.pode_editar(request.user) if pauta
        else policies.pode_criar(request.user),
        "voltar": reverse("publicacoes:lista"),
    }
    if pauta is None:
        contexto["migalhas"] = _migalhas(("Pautas", reverse("publicacoes:lista")),
                                         ("Nova pauta", ""))
        return contexto
    contexto.update({
        "andamento": andamento or FormularioAndamento(),
        "opcoes_status": [(v, r, dominio.DICAS[v], v == pauta.status)
                          for v, r, _d, _t in dominio.STATUS],
        "dica_atual": dominio.DICAS.get(pauta.status, ""),
        "ultima_anotacao": services.ultima_anotacao(pauta),
        "historico": historico.da_pauta(pauta),
        "migalhas": _migalhas(("Pautas", reverse("publicacoes:lista")), (str(pauta), "")),
    })
    return contexto


def _erro_do_servico(form, exc: dominio.RegraViolada) -> None:
    form.add_error(exc.campo if exc.campo in form.fields else None, str(exc))


@require_http_methods(["GET", "POST"])
def nova(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_criar(request.user))
    if request.method == "POST":
        form = FormularioPauta(request.POST)
        if form.is_valid():
            try:
                pauta = services.criar(request.user, form.cleaned_data)
            except dominio.RegraViolada as exc:
                _erro_do_servico(form, exc)
            else:
                messages.success(request, f"{pauta} registrada. Ela se grava sozinha daqui "
                                          "em diante.")
                return redirect("publicacoes:pauta", pk=pauta.pk)
        messages.error(request, "Corrija os campos destacados para registrar.")
    else:
        agora = timezone.localtime()
        form = FormularioPauta(initial={
            "data": agora.date(), "inicio_pauta": agora.time().replace(second=0,
                                                                       microsecond=0)})
    return render(request, "publicacoes/folha.html", _contexto_folha(request, form, None))


@require_http_methods(["GET", "POST"])
def pauta(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(policies.pode_acessar(request.user))
    objeto = get_object_or_404(queries.base(), pk=pk)
    if request.method == "POST":
        _exigir(policies.pode_editar(request.user))
        form = FormularioPauta(request.POST, instance=objeto)
        if form.is_valid():
            try:
                services.salvar(request.user, objeto.pk, form.cleaned_data)
            except dominio.RegraViolada as exc:
                _erro_do_servico(form, exc)
            else:
                messages.success(request, "Pauta salva.")
                return redirect("publicacoes:pauta", pk=objeto.pk)
        messages.error(request, "Corrija os campos destacados para salvar.")
        objeto.refresh_from_db()
    else:
        form = FormularioPauta(instance=objeto)
    return render(request, "publicacoes/folha.html", _contexto_folha(request, form, objeto))


@require_POST
def autosave(request: HttpRequest, pk: int) -> JsonResponse:
    """Grava a folha a cada pausa (componentes/autosave.js), quando o formulário é válido;
    senão diz o que impede, no status da barra."""
    _exigir(policies.pode_acessar(request.user))
    objeto = get_object_or_404(Publicacao, pk=pk)
    if not policies.pode_editar(request.user):
        return JsonResponse({"salvo": False, "mensagem": "Você não pode alterar pautas."})
    form = FormularioPauta(request.POST, instance=objeto)
    if not form.is_valid():
        return JsonResponse({"salvo": False, "mensagem": _primeiro_erro(form)})
    unidade_nova = bool((form.cleaned_data.get("unidade_nova") or "").strip())
    try:
        salvo = services.salvar(request.user, objeto.pk, form.cleaned_data)
    except dominio.RegraViolada as exc:
        return JsonResponse({"salvo": False, "mensagem": f"Não salvo: {exc}"})
    # Unidade nova entra na lista: a tela é redesenhada para mostrá-la escolhida.
    return JsonResponse({"salvo": True, "recarregar": unidade_nova,
                         "em": timezone.localtime(salvo.atualizado_em).strftime("%H:%M")})


@require_POST
def andamento(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(policies.pode_editar(request.user))
    objeto = get_object_or_404(queries.base(), pk=pk)
    form = FormularioAndamento(request.POST)
    if form.is_valid():
        try:
            salvo = services.registrar_andamento(request.user, objeto.pk,
                                                 form.cleaned_data["novo_status"],
                                                 form.cleaned_data["anotacao"])
        except dominio.RegraViolada as exc:
            form.add_error("novo_status", str(exc))
        else:
            messages.success(request, f"Status: {salvo.get_status_display()}.")
            return redirect(reverse("publicacoes:pauta", args=[objeto.pk]) + "#andamento")
    elif "novo_status" in form.errors:
        form.errors["novo_status"] = form.error_class([dominio.MSG_ESCOLHA])
    messages.error(request, "O andamento não foi registrado: veja o cartão Andamento.")
    contexto = _contexto_folha(request, FormularioPauta(instance=objeto), objeto, form)
    return render(request, "publicacoes/folha.html", contexto, status=400)


# ------------------------------------------------------------------ cadastros de apoio
CADASTROS = {
    "equipe": {"titulo": "Equipe", "singular": "integrante", "novo": "Novo integrante",
               "exemplo": "Ex.: Gabriela", "icone": "users",
               "intro": "Nome curto usado como jornalista, revisão e galeria de fotos.",
               "url": "publicacoes:equipe", "modulo": "Publicações",
               "uso_icone": "newspaper", "uso": "pauta,pautas"},
    "unidades": {"titulo": "Unidades responsáveis", "singular": "unidade",
                 "novo": "Nova unidade", "exemplo": "Ex.: DP de Ponta Grossa",
                 "icone": "landmark",
                 "intro": "Unidade policial responsável pela pauta (DP, DHPP, DPC…). Também "
                          "entra pelo campo “Outra unidade” da pauta.",
                 "url": "publicacoes:unidades", "modulo": "Publicações",
                 "uso_icone": "newspaper", "uso": "pauta,pautas"},
}


def _cadastro(request: HttpRequest, tipo: str) -> HttpResponse:
    _exigir(policies.pode_gerir_cadastros(request.user))
    meta = CADASTROS[tipo]
    modelo = services.TIPOS[tipo]
    erro, valor, editando = "", "", None
    if request.method == "POST":
        pk = request.POST.get("pk")
        pk_int = int(pk) if pk and pk.isdigit() else None
        try:
            if request.POST.get("acao") == "excluir" and pk_int:
                nome = services.excluir_cadastro(request.user, tipo, pk_int)
                messages.success(request, f"“{nome}” excluído.")
            else:
                registro = services.salvar_cadastro(request.user, tipo,
                                                    request.POST.get("nome", ""), pk_int)
                messages.success(request, f"“{registro.nome}” salvo.")
            return redirect(meta["url"])
        except modelo.DoesNotExist as exc:
            raise Http404 from exc
        except dominio.RegraViolada as exc:
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
def unidades(request: HttpRequest) -> HttpResponse:
    return _cadastro(request, "unidades")
