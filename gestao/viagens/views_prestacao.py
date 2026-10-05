"""Prestação de contas (módulo 9a): a lista (um bloco por ofício, um cartão por servidor),
a solicitação de cada cartão (grava sozinha, como a referência), arquivar/finalizar
(servidor e equipe), envio ao financeiro e a planilha. Regra em `prestacao.py`; ficha em
docs/migration/prestacao.md."""

from __future__ import annotations

import re
from datetime import date, datetime

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from . import anexos, exportacao, policies, prestacao
from .dominio.prestacao import prazo_para_prestar
from .models import PrestacaoContas, PrestacaoServidor, Trecho
from .viagem import periodo_curto
from .views import _migalhas

POR_PAGINA = 25  # ofícios por página (referência)
ATENCAO = {"saque_vencendo", "prestacao_vencida", "sem_solicitacao", "finalizadas_mes"}
NUMERO_OFICIO = re.compile(r"^\s*(\d{1,5})\s*/\s*(\d{4})\s*$")
VAZIOS = {
    "nao_liberadas": "Nenhum servidor com diárias pendentes de liberação.",
    "liberadas": "Nenhum servidor com diárias já liberadas.",
    "devolvidas": "Nenhuma prestação devolvida para correção.",
    "arquivados": "Nenhuma prestação de servidor arquivada.",
    "finalizados": "Nenhuma equipe com todas as prestações finalizadas.",
    "saque_vencendo": "Nenhum saque perto do prazo sem comprovante.",
    "prestacao_vencida": "Nenhuma prestação com o prazo vencido.",
    "sem_solicitacao": "Nenhuma prestação em aberto sem número de solicitação.",
    "finalizadas_mes": "Nenhuma prestação finalizada neste mês.",
}
ROTULOS = {"arquivar": "arquivada", "desarquivar": "desarquivada", "finalizar": "finalizada",
           "reabrir": "reaberta"}
ROTULOS_EQUIPE = {"arquivar": "arquivadas", "desarquivar": "desarquivadas",
                  "finalizar": "finalizadas", "reabrir": "reabertas"}


def _data(texto: str, rotulo: str = "Data") -> date | None:
    texto = (texto or "").strip()
    if not texto:
        return None
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise prestacao.PrestacaoInvalida(f"{rotulo} inválida: {texto}. Use dd/mm/aaaa.")


def _voltar(request: HttpRequest, ancora: str = "") -> str:
    voltar = (request.POST.get("voltar") or "").split("#")[0]
    if not (voltar.startswith("/") and not voltar.startswith("//")
            and url_has_allowed_host_and_scheme(voltar, allowed_hosts={request.get_host()})):
        voltar = reverse("viagens:prestacoes")
    return f"{voltar}#{ancora}" if ancora else voltar


def _buscar(qs, termo: str):
    if not termo:
        return qs
    filtro = (Q(servidor__nome__unaccent__icontains=termo)
              | Q(numero_solicitacao__icontains=termo)
              | Q(prestacao__oficio__protocolo__icontains=re.sub(r"\D", "", termo) or termo))
    if (m := NUMERO_OFICIO.match(termo)):
        filtro |= Q(prestacao__oficio__numero=int(m.group(1)),
                    prestacao__oficio__ano=int(m.group(2)))
    return qs.filter(filtro)


def _linhas(request: HttpRequest):
    base = policies.prestacoes_visiveis(request.user).select_related(
        "servidor", "prestacao__oficio")
    abas = [a for a in request.GET.getlist("aba") if a in dict(prestacao.ABAS)]
    busca = (request.GET.get("q") or "").strip()
    buscadas = _buscar(base, busca)
    qs = buscadas
    if abas:
        ids: set[int] = set()
        for aba in abas:
            ids.update(prestacao.filtrar(buscadas, aba).values_list("pk", flat=True))
        qs = buscadas.filter(pk__in=ids)
    return buscadas, qs, abas, busca


@require_GET
def lista(request: HttpRequest) -> HttpResponse:
    policies.exigir(policies.pode_listar_prestacoes(request.user))
    buscadas, qs, abas, busca = _linhas(request)
    contagens = {"todas": buscadas.count(),
                 **{a: prestacao.filtrar(buscadas, a).count() for a, _ in prestacao.ABAS}}
    # A paginação é por ofício: a equipe não se parte entre páginas (referência).
    ids = qs.select_related(None).values("prestacao_id")
    prestacoes = (PrestacaoContas.objects.filter(pk__in=ids)
                  .select_related("oficio__unidade")
                  .prefetch_related(Prefetch("oficio__trechos", queryset=Trecho.objects
                                             .select_related("destino").order_by("ordem")))
                  .annotate(equipe=Count("oficio__viajantes", distinct=True))
                  .order_by("-oficio__ano", "-oficio__numero"))
    pagina = Paginator(prestacoes, POR_PAGINA).get_page(request.GET.get("pagina"))
    da_pagina = {p.pk: p for p in pagina.object_list}
    por_prestacao: dict[int, list] = {}
    hoje = timezone.localdate()
    situacao = anexos.situacao(da_pagina)
    for ps in qs.filter(prestacao__in=list(da_pagina)).order_by("servidor__nome"):
        ps.prestacao = da_pagina[ps.prestacao_id]
        por_prestacao.setdefault(ps.prestacao_id, []).append(
            _linha(request, ps, hoje, situacao))
    blocos = [_bloco(request, p, por_prestacao.get(p.pk, [])) for p in pagina.object_list]
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    return render(request, "viagens/prestacao/lista.html", {
        "page_obj": pagina, "blocos": blocos, "aba": abas[0] if len(abas) == 1 else "",
        "abas_situacao": [(c, r) for c, r in prestacao.ABAS if c not in ATENCAO],
        "abas_atencao": [(c, r) for c, r in prestacao.ABAS if c in ATENCAO],
        "contagens": contagens, "busca": busca, "total_servidores": qs.count(),
        "acoes_equipe": list(ROTULOS),
        "vazio": VAZIOS.get(abas[0], "Nenhuma prestação encontrada.") if len(abas) == 1
        else "Nenhuma prestação encontrada.",
        "querystring_base": (filtros.urlencode() + "&") if filtros else "",
        "migalhas": _migalhas(("Prestação de contas", ""))})


def _linha(request: HttpRequest, ps: PrestacaoServidor, hoje: date,
           situacao: anexos.Situacao) -> dict:
    selos = prestacao.selos(ps, hoje, tem_comprovante=bool(situacao.comprovantes.get(ps.pk)))
    return {"ps": ps, "selos": selos,
            "pendencias": prestacao.pendencias(ps, situacao),
            "diaria": prestacao.diaria_liberada(ps, getattr(ps.prestacao, "equipe", None)),
            "prestar_ate": prazo_para_prestar(ps.prazo_limite_saque),
            "editavel": policies.pode_editar_prestacao(request.user, ps)}


def _bloco(request: HttpRequest, p: PrestacaoContas, linhas: list) -> dict:
    trechos = list(p.oficio.trechos.all())
    destinos = list(dict.fromkeys(str(t.destino) for t in trechos))
    periodo = (periodo_curto(timezone.localtime(trechos[0].saida_em).date(),
                             timezone.localtime(trechos[-1].chegada_em).date())
               if trechos else "")
    abertas = [linha for linha in linhas if not linha["ps"].finalizada]
    por_enviar = [linha for linha in linhas if linha["ps"].finalizada
                  and linha["ps"].situacao not in ("enviada", "aprovada")]
    return {"p": p, "linhas": linhas, "destinos": ", ".join(destinos), "periodo": periodo,
            "editavel": policies.pode_editar_equipe_prestacao(request.user, p),
            "todas_finalizadas": bool(linhas) and not abertas,
            "reabrivel": bool(por_enviar), "por_enviar": por_enviar,
            "alguma_arquivada": any(linha["ps"].arquivada for linha in linhas)}


def _ps(request: HttpRequest, pk: int) -> PrestacaoServidor:
    ps = get_object_or_404(PrestacaoServidor.objects.select_related(
        "servidor", "prestacao__oficio"), pk=pk)
    if not policies.pode_ver_prestacao(request.user, ps):
        raise Http404
    return ps


def _gravar_cartao(request: HttpRequest, ps: PrestacaoServidor) -> None:
    """Os campos do cartão, quando vieram (o cartão aberto manda os três)."""
    if "numero" not in request.POST or ps.finalizada:
        return
    prestacao.salvar_solicitacao(
        request.user, ps.pk, numero=request.POST.get("numero", ""),
        liberacao=_data(request.POST.get("liberacao", ""), "Data de liberação"),
        prazo=_data(request.POST.get("prazo", ""), "Prazo de saque"))


@require_POST
def salvar(request: HttpRequest, pk: int) -> HttpResponse:
    """Sem JavaScript (ou Enter num campo): grava o cartão e volta para ele."""
    ps = _ps(request, pk)
    try:
        _gravar_cartao(request, ps)
    except (prestacao.PrestacaoInvalida, PermissionDenied) as exc:
        messages.error(request, f"{ps.servidor.nome}: {exc}")
    else:
        messages.success(request, f"Solicitação de {ps.servidor.nome} salva.")
    return redirect(_voltar(request, f"ps-{ps.pk}"))


@require_POST
def autosave(request: HttpRequest, pk: int) -> JsonResponse:
    """Contrato do autosave.js: {"salvo", "em", "campos", "recarregar", "mensagem"}."""
    ps = _ps(request, pk)
    try:
        _gravar_cartao(request, ps)
    except (prestacao.PrestacaoInvalida, PermissionDenied) as exc:
        return JsonResponse({"salvo": False, "mensagem": str(exc)})
    return JsonResponse({"salvo": True, "em": f"{timezone.localtime():%H:%M}", "campos": {},
                         "recarregar": False})


@require_POST
def acao_servidor(request: HttpRequest, pk: int, acao: str) -> HttpResponse:
    ps = _ps(request, pk)
    if acao not in {*ROTULOS, "enviar", "aprovar", "devolver"}:
        raise Http404
    ancora = f"ps-{ps.pk}"
    try:
        # O que está digitado no cartão vale antes da ação (nada se perde ao clicar).
        _gravar_cartao(request, ps)
        if acao == "arquivar":
            prestacao.arquivar(request.user, ps.pk, True)
        elif acao == "desarquivar":
            prestacao.arquivar(request.user, ps.pk, False)
        elif acao == "finalizar":
            prestacao.finalizar(request.user, ps.pk, request.POST.get("justificativa", ""))
        elif acao == "reabrir":
            prestacao.reabrir(request.user, ps.pk)
        elif acao == "enviar":
            n = prestacao.enviar(request.user, ps.pk, enviada_em=_data(
                request.POST.get("enviada_em", ""), "Data do envio"),
                protocolo=request.POST.get("protocolo", ""),
                equipe=request.POST.get("equipe") == "1")
            plural = "servidor" if n == 1 else "servidores"
            messages.success(request, f"Envio registrado para {n} {plural}.")
            return redirect(_voltar(request, ancora))
        elif acao == "aprovar":
            prestacao.aprovar(request.user, ps.pk)
            messages.success(request, f"Prestação de {ps.servidor.nome} aprovada.")
            return redirect(_voltar(request, ancora))
        else:
            prestacao.devolver(request.user, ps.pk, request.POST.get("motivo", ""))
            messages.success(request, f"Prestação de {ps.servidor.nome} devolvida e reaberta "
                                      "para correção.")
            return redirect(_voltar(request, ancora))
    except (prestacao.PrestacaoInvalida, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Prestação de {ps.servidor.nome} {ROTULOS[acao]}.")
    return redirect(_voltar(request, ancora))


@require_POST
def acao_equipe(request: HttpRequest, pk: int, acao: str) -> HttpResponse:
    p = get_object_or_404(PrestacaoContas.objects.select_related("oficio"), pk=pk)
    if not policies.pode_ver_equipe_prestacao(request.user, p):
        raise Http404
    if acao not in ROTULOS:
        raise Http404
    ancora = f"equipe-{p.pk}"
    try:
        r = prestacao.acao_da_equipe(request.user, p.pk, acao)
    except PermissionDenied as exc:
        messages.error(request, str(exc))
        return redirect(_voltar(request, ancora))
    if r.pulados:
        nomes = (" e ".join([", ".join(r.pulados[:-1]), r.pulados[-1]])
                 if len(r.pulados) > 1 else r.pulados[0])
        quem = "ainda tem" if len(r.pulados) == 1 else "ainda têm"
        inicio = "Ficaram de fora" if r.feitos else "Ninguém foi finalizado"
        messages.warning(request, f"{inicio}: {nomes} {quem} pendência (veja “Falta para "
                                  "finalizar” no cartão).")
    if r.feitos:
        plural = "servidor" if r.feitos == 1 else "servidores"
        messages.success(request, f"Prestações {ROTULOS_EQUIPE[acao]}: {r.feitos} {plural}.")
    elif not r.pulados:
        messages.info(request, "Nada a fazer: a equipe já estava assim.")
    return redirect(_voltar(request, ancora))


@require_GET
def exportar(request: HttpRequest) -> HttpResponse:
    policies.exigir(policies.pode_listar_prestacoes(request.user))
    _, qs, _, _ = _linhas(request)
    conteudo = exportacao.planilha_de_prestacoes(
        qs.select_related("servidor", "prestacao__oficio").order_by(
            "-prestacao__oficio__ano", "-prestacao__oficio__numero", "servidor__nome"))
    resposta = HttpResponse(conteudo, content_type=(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
    resposta["Content-Disposition"] = (
        f'attachment; filename="prestacoes_{timezone.localdate():%Y-%m-%d}.xlsx"')
    return resposta
