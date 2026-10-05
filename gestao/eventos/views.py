"""Telas dos catálogos de Eventos Sociais (paridade com `cadastros/views.py` da
referência): índice com as contagens, a lista de cada catálogo (incluir, renomear, ativar
ou inativar, excluir o que não está em uso) e o modelo da solicitação do tipo de evento."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from . import catalogos, policies
from .models import Equipe, OrgaoResponsavel, Servico, TipoEvento

POR_PAGINA = 25


def _migalhas(*itens: tuple[str, str]) -> list[tuple[str, str]]:
    return [("Início", reverse("painel:inicio")),
            ("Cadastros de Eventos", reverse("eventos:cadastros")), *itens]


@require_GET
def indice(request: HttpRequest) -> HttpResponse:
    visiveis = policies.catalogos_visiveis(request.user)
    if not visiveis:
        raise PermissionDenied
    cartoes = [(catalogos.CATALOGOS[s], catalogos.CATALOGOS[s].modelo.objects.count(),
                catalogos.CATALOGOS[s].modelo.objects.filter(ativo=False).count())
               for s in visiveis]
    return render(request, "eventos/cadastros.html", {
        "cartoes": cartoes, "migalhas": [("Início", reverse("painel:inicio")),
                                          ("Cadastros de Eventos", "")]})


@require_http_methods(["GET", "POST"])
def catalogo(request: HttpRequest, slug: str) -> HttpResponse:
    if slug not in catalogos.CATALOGOS:
        raise Http404
    if not policies.pode_gerir_catalogo(request.user, slug):
        raise PermissionDenied
    cat = catalogos.CATALOGOS[slug]
    erro, editando, valores = "", None, {}
    if request.method == "POST":
        pk = request.POST.get("pk") or ""
        pk_int = int(pk) if pk.isdigit() else None
        acao = request.POST.get("acao")
        try:
            if acao == "excluir" and pk_int:
                nome = catalogos.excluir(request.user, slug, pk_int)
                messages.success(request, f"“{nome}” excluído.")
            elif acao == "ativo" and pk_int:
                r = catalogos.alternar_ativo(request.user, slug, pk_int)
                messages.success(request, f"“{r.nome}” {'ativado' if r.ativo else 'inativado'}.")
            else:
                r = catalogos.salvar(request.user, slug, request.POST, pk_int)
                messages.success(request, f"{cat.titulo}: “{r.nome}” salvo.")
            return redirect(request.get_full_path())
        except cat.modelo.DoesNotExist as exc:
            raise Http404 from exc
        except catalogos.CatalogoInvalido as exc:
            erro, editando = str(exc), pk_int
            valores = {"nome": request.POST.get("nome", ""), "texto": request.POST.get("texto", "")}
    q = " ".join((request.GET.get("q") or "").split())[:100]
    situacao = request.GET.get("situacao") or ""
    qs = cat.modelo.objects.order_by("nome")
    if q:
        qs = qs.filter(nome__icontains=q)
    if situacao in ("ativos", "inativos"):
        qs = qs.filter(ativo=situacao == "ativos")
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    base = "&".join(p for p in (f"q={q}" if q else "",
                                f"situacao={situacao}" if situacao else "") if p)
    return render(request, "eventos/catalogo.html", {
        "cat": cat, "page_obj": pagina, "registros": list(pagina.object_list), "q": q,
        "situacao": situacao, "erro": erro, "editando": editando, "valores": valores,
        "querystring_base": f"{base}&" if base else "",
        "outros": [catalogos.CATALOGOS[s] for s in policies.catalogos_visiveis(request.user)
                   if s != slug],
        "migalhas": _migalhas((cat.titulo, "")),
    })


@require_http_methods(["GET", "POST"])
def modelo_do_tipo(request: HttpRequest, pk: int) -> HttpResponse:
    if not policies.pode_gerir_catalogo(request.user, "tipos-evento"):
        raise PermissionDenied
    tipo = get_object_or_404(TipoEvento.objects.prefetch_related("servicos_sugeridos",
                                                                 "equipes_padrao"), pk=pk)
    orgaos = OrgaoResponsavel.objects.filter(ativo=True) | OrgaoResponsavel.objects.filter(
        pk=tipo.orgao_padrao_id or 0)
    escolhidos = {s.pk for s in tipo.servicos_sugeridos.all()}
    servicos = Servico.objects.filter(ativo=True) | Servico.objects.filter(pk__in=escolhidos)
    atuais = {e.equipe_id: e.quantidade for e in tipo.equipes_padrao.all()}
    equipes = Equipe.objects.filter(ativo=True) | Equipe.objects.filter(pk__in=atuais)
    erros: list[str] = []
    if request.method == "POST":
        orgao_id = request.POST.get("orgao") or ""
        orgao = orgaos.filter(pk=orgao_id).first() if orgao_id.isdigit() else None
        marcados = [int(x) for x in request.POST.getlist("servicos") if x.isdigit()]
        novas: dict[int, int | None] = {}
        for e in equipes.distinct():
            if request.POST.get(f"equipe_{e.pk}"):
                texto = (request.POST.get(f"quantidade_{e.pk}") or "").strip()
                if texto and not (texto.isdigit() and int(texto) > 0):
                    erros.append(f"Informe uma quantidade válida para {e.nome}.")
                novas[e.pk] = int(texto) if texto.isdigit() and int(texto) > 0 else None
        if not erros:
            catalogos.salvar_modelo(request.user, tipo.pk,
                                    solicitante=request.POST.get("solicitante", ""),
                                    cargo=request.POST.get("cargo", ""), orgao=orgao,
                                    servicos=list(servicos.filter(pk__in=marcados).distinct()),
                                    equipes=novas)
            messages.success(request, f"Modelo do tipo {tipo.nome} salvo.")
            return redirect("eventos:modelo_do_tipo", pk=tipo.pk)
        messages.error(request, "Corrija os campos destacados para continuar.")
    return render(request, "eventos/modelo_do_tipo.html", {
        "tipo": tipo, "orgaos": orgaos.distinct().order_by("nome"),
        "servicos": servicos.distinct().order_by("nome"), "escolhidos": escolhidos,
        "equipes": [(e, e.pk in atuais, atuais.get(e.pk)) for e in
                    equipes.distinct().order_by("nome")], "erros": erros,
        "migalhas": _migalhas(("Tipos de evento", reverse("eventos:tipos-evento")),
                              (f"Modelo — {tipo.nome}", "")),
    })
