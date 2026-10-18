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
from django.utils.http import urlencode
from django.views.decorators.http import require_GET, require_http_methods

from gestao.cadastros.fontes import atividades_e_servicos

from . import catalogos, policies
from .models import Equipe, OrgaoResponsavel, TipoEvento

POR_PAGINA = 25


def _migalhas(*itens: tuple[str, str]) -> list[tuple[str, str]]:
    return [("Início", reverse("painel:inicio")),
            ("Cadastros de Eventos", reverse("eventos:cadastros")), *itens]


@require_GET
def indice(request: HttpRequest) -> HttpResponse:
    visiveis = policies.catalogos_visiveis(request.user)
    if not visiveis:
        raise PermissionDenied
    cartoes = []
    for slug in visiveis:  # a lista de catálogos dos cadastros gerais (lista_catalogo.html)
        cat = catalogos.CATALOGOS[slug]
        total = cat.modelo.objects.count()
        inativos = cat.modelo.objects.filter(ativo=False).count()
        cartoes.append({"titulo": cat.titulo, "url": reverse(cat.url_name), "icone": cat.icone,
                        "texto": f"Cadastre {cat.genitivo.split(' ', 1)[-1]} usado nas "
                                 "solicitações de evento.",
                        "resumo": f"{total} cadastrado{'s' if total != 1 else ''}"
                                  + (f" · {inativos} inativo{'s' if inativos != 1 else ''}"
                                     if inativos else "")})
    return render(request, "eventos/cadastros.html", {
        "cartoes": cartoes, "migalhas": [("Início", reverse("painel:inicio")),
                                          ("Cadastros de Eventos", "")]})


@require_http_methods(["GET", "POST"])
def catalogo(request: HttpRequest, slug: str) -> HttpResponse:
    """Um catálogo (forma dos catálogos de Viagens): abas Ativos/Inativos com a contagem,
    busca, uma linha por registro com o menu de ações, e novo/editar numa janela
    (`?novo=1`, `?editar=<pk>`; com erro, a janela volta aberta com o que foi digitado)."""
    if slug not in catalogos.CATALOGOS:
        raise Http404
    if not policies.pode_gerir_catalogo(request.user, slug):
        raise PermissionDenied
    cat = catalogos.CATALOGOS[slug]
    q = " ".join((request.GET.get("q") or "").split())[:100]
    # `situacao=` é o endereço antigo do filtro: continua valendo.
    aba = request.GET.get("aba") or request.GET.get("situacao") or ""
    aba = "inativos" if aba == "inativos" else ""
    base = urlencode({chave: valor for chave, valor in (("q", q), ("aba", aba)) if valor})
    volta = f"{request.path}?{base}" if base else request.path
    erro, editando, valores, abrir, campo_erro = "", None, {}, False, ""
    if request.method == "POST":
        pk = request.POST.get("pk") or ""
        if pk and (not pk.isascii() or not pk.isdecimal() or len(pk) > 18):
            raise Http404
        pk_int = int(pk) if pk else None
        if pk_int is not None and pk_int <= 0:
            raise Http404
        acao = request.POST.get("acao")
        try:
            if acao == "excluir" and pk_int:
                nome = catalogos.excluir(request.user, slug, pk_int)
                messages.success(request, f"“{nome}” excluído.")
            elif acao == "ativo" and pk_int:
                r = catalogos.alternar_ativo(request.user, slug, pk_int)
                messages.success(request, f"“{r.nome}” {'reativado' if r.ativo else 'desativado'}.")
            else:
                r = catalogos.salvar(request.user, slug, request.POST, pk_int)
                messages.success(request, f"{cat.titulo}: “{r.nome}” salvo.")
            return redirect(volta)
        except cat.modelo.DoesNotExist as exc:
            raise Http404 from exc
        except catalogos.CatalogoInvalido as exc:
            if acao in ("excluir", "ativo"):
                messages.error(request, str(exc))
                return redirect(volta)
            erro, abrir, campo_erro = str(exc), True, exc.campo or ""
            editando = cat.modelo.objects.filter(pk=pk_int).first() if pk_int else None
            valores = {"nome": request.POST.get("nome", ""), "texto": request.POST.get("texto", "")}
    else:
        pk_editar = request.GET.get("editar") or ""
        if pk_editar.isdigit():
            editando = cat.modelo.objects.filter(pk=int(pk_editar)).first()
        if editando is not None:
            valores = {"nome": editando.nome, "texto": getattr(editando, "texto", "")}
        abrir = editando is not None or request.GET.get("novo") == "1"
    todos = cat.modelo.objects.all()
    contagens = {"ativos": todos.filter(ativo=True).count(),
                 "inativos": todos.filter(ativo=False).count()}
    qs = todos.filter(ativo=aba != "inativos").order_by("nome")
    if slug == "tipos-evento":  # "tem modelo" de cada linha sem uma consulta por tipo
        qs = qs.prefetch_related("servicos_sugeridos", "equipes_padrao")
    if q:
        qs = qs.filter(nome__icontains=q)
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    if slug == "servicos":  # o catálogo é o mesmo das atividades do Plano de Trabalho
        descricao = ("Catálogo compartilhado com o Plano de Trabalho. As alterações valem para "
                     "os próximos usos; itens inativos continuam vinculados aos registros "
                     "anteriores.")
    else:
        descricao = (f"{'Os dados' if cat.com_texto else 'O nome'} {cat.genitivo} usado"
                     f"{'s' if cat.com_texto else ''} nas solicitações. O desativado sai dos "
                     "formulários novos e continua nas solicitações que já o usam.")
    feminino = cat.genitivo.startswith("da ")
    return render(request, "eventos/catalogo.html", {
        "cat": cat, "descricao_catalogo": descricao, "page_obj": pagina,
        "registros": list(pagina.object_list), "q": q, "aba": aba,
        "abas": [("", "Ativos", "ativos"), ("inativos", "Inativos", "inativos")],
        "contagens": contagens, "erro": erro, "campo_erro": campo_erro,
        "editando": editando, "valores": valores,
        "limite_nome": cat.modelo._meta.get_field("nome").max_length,
        "abrir_dialogo": abrir, "novo_rotulo": f"{'Nova' if feminino else 'Novo'} {cat.singular}",
        "querystring_base": f"{base}&" if base else "", "voltar": volta,
        "migalhas": _migalhas((cat.titulo, "")),
    }, status=422 if erro else 200)


@require_http_methods(["GET", "POST"])
def modelo_do_tipo(request: HttpRequest, pk: int) -> HttpResponse:
    if not policies.pode_gerir_catalogo(request.user, "tipos-evento"):
        raise PermissionDenied
    tipo = get_object_or_404(TipoEvento.objects.prefetch_related("servicos_sugeridos",
                                                                 "equipes_padrao"), pk=pk)
    orgaos = OrgaoResponsavel.objects.filter(ativo=True) | OrgaoResponsavel.objects.filter(
        pk=tipo.orgao_padrao_id or 0)
    escolhidos = {s.pk for s in tipo.servicos_sugeridos.all()}
    servicos = atividades_e_servicos(incluir=escolhidos)
    atuais = {e.equipe_id: e.quantidade for e in tipo.equipes_padrao.all()}
    equipes = Equipe.objects.filter(ativo=True) | Equipe.objects.filter(pk__in=atuais)
    erros: list[str] = []
    if request.method == "POST":
        orgao_id = request.POST.get("orgao") or ""
        orgao = (orgaos.filter(pk=orgao_id).first()
                 if orgao_id.isascii() and orgao_id.isdecimal() and len(orgao_id) <= 18 else None)
        marcados = [int(x) for x in request.POST.getlist("servicos")
                    if x.isascii() and x.isdecimal() and len(x) <= 18]
        novas: dict[int, int | None] = {}
        for e in equipes.distinct():
            if request.POST.get(f"equipe_{e.pk}"):
                texto = (request.POST.get(f"quantidade_{e.pk}") or "").strip()
                valido = (texto.isascii() and texto.isdecimal() and len(texto) <= 9
                          and int(texto) > 0)
                if texto and not valido:
                    erros.append(f"Informe uma quantidade válida para {e.nome}.")
                novas[e.pk] = int(texto) if valido else None
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
