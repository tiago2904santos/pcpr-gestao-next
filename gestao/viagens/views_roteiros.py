"""Telas de roteiros cadastrados (como no sistema de referência): lista com abas e busca,
cadastro/edição com o mesmo itinerário do ofício, e "criar ofício com este roteiro"."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import F
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.vary import vary_on_headers

from . import itinerario, policies, queries, services
from .dominio.diarias import Faixa
from .forms import FORM_ID_ROTEIRO, FormularioRoteiro
from .models import Roteiro
from .views import POR_PAGINA, _htmx, _migalhas

ABAS = [("", "Todos", "todos")] + [(c, r, c) for c, r in queries.FILTROS_ROTEIRO.items()]


def _roteiro_visivel(request: HttpRequest, pk: int) -> Roteiro:
    roteiro = get_object_or_404(Roteiro.objects.select_related("sede", "unidade"), pk=pk)
    if not policies.pode_ver_roteiro(request.user, roteiro):
        raise PermissionDenied
    return roteiro


@require_GET
@vary_on_headers("HX-Request", "HX-Target")
def lista(request: HttpRequest) -> HttpResponse:
    if not request.user.has_perm("viagens.view_roteiro"):
        raise PermissionDenied
    base = policies.roteiros_visiveis(request.user)
    aba = request.GET.get("aba") or ""
    termo = (request.GET.get("q") or "").strip()
    qs = queries.buscar_roteiros(queries.filtrar_roteiros(base, aba), termo)
    qs = queries.roteiros_de_lista(qs).order_by(F("primeira_saida").desc(nulls_last=True),
                                                "-criado_em")
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    contexto = {
        "page_obj": pagina,
        "roteiros": pagina.object_list,
        "contagens": queries.contagens_roteiros(base),
        "abas": ABAS,
        "aba": aba,
        "termo": termo,
        "querystring_base": (filtros.urlencode() + "&") if filtros else "",
        "pode_criar": policies.pode_criar_roteiro(request.user),
        "pode_editar_roteiros": request.user.has_perm("viagens.change_roteiro"),
        "pode_criar_oficio": policies.pode_criar(request.user),
        "agora": timezone.now(),
        "migalhas": _migalhas(("Roteiros", "")),
    }
    if _htmx(request) and request.htmx.target == "resultados":  # type: ignore[attr-defined]
        return render(request, "viagens/roteiros/lista.html#resultados", contexto)
    return render(request, "viagens/roteiros/lista.html", contexto)


def _contexto(request, roteiro: Roteiro | None, form, itin, erro_roteiro: str = "") -> dict:
    rotulo = f"Roteiro #{roteiro.pk}" if roteiro else "Novo roteiro"
    return {
        "roteiro": roteiro,
        "form": form,
        **itin.contexto(),
        "erro_roteiro": erro_roteiro,
        "calculo": roteiro.diarias_calculo if roteiro else {},
        "faixas": {f.value: f.rotulo for f in Faixa},
        "oficios_do_roteiro": (list(roteiro.oficios.order_by("-ano", "-numero")[:10])
                               if roteiro else []),
        "pode_cancelar": roteiro is not None and policies.pode_cancelar_roteiro(request.user,
                                                                                roteiro),
        "pode_excluir": roteiro is not None and policies.pode_excluir_roteiro(request.user,
                                                                              roteiro),
        "pode_criar_oficio": policies.pode_criar(request.user),
        "migalhas": _migalhas(("Roteiros", reverse("viagens:roteiros")), (rotulo, "")),
    }


def _formulario(request: HttpRequest, roteiro: Roteiro | None) -> HttpResponse:
    """Cadastro e edição: a mesma folha (itinerário com mapa, efetivo e observações,
    diárias)."""
    if roteiro is None:
        policies.exigir(policies.pode_criar_roteiro(request.user),
                        "Seu usuário precisa estar lotado em uma unidade para criar roteiros.")
        try:
            sede = services.configuracao_da_unidade(
                policies.unidade_do_usuario(request.user)).sede
        except services.RegraViolada as exc:
            messages.error(request, str(exc))
            return redirect("viagens:roteiros")
    else:
        sede = roteiro.sede
        if not policies.pode_editar_roteiro(request.user, roteiro):
            messages.info(request, f"O roteiro #{roteiro.pk} está cancelado ou seu perfil não "
                                   "permite editá-lo.")
            return redirect("viagens:roteiros")
    template = "viagens/roteiros/editar.html"
    if request.method != "POST":
        trechos = queries.trechos_do_roteiro(roteiro) if roteiro else []
        itin = itinerario.montar(FORM_ID_ROTEIRO, sede=sede, trechos=trechos)
        contexto = _contexto(request, roteiro, FormularioRoteiro(instance=roteiro), itin)
        contexto["recem_salvo"] = request.GET.get("salvo") == "1"
        return render(request, template, contexto)

    form = FormularioRoteiro(request.POST, instance=roteiro or Roteiro(sede=sede))
    if request.POST.get("acao") == "adicionar_destino":  # sem JavaScript
        itin = itinerario.com_iniciais(FORM_ID_ROTEIRO, request.POST, mais_um=True)
        form.is_valid()
        contexto = _contexto(request, roteiro, form, itin)
        contexto.update(foco=f"id_destino-{itin.destinos.total_form_count() - 1}-cidade",
                        sujo=True)
        return render(request, template, contexto)
    itin = itinerario.montar(FORM_ID_ROTEIRO, dados=request.POST)
    vazio = itin.vazio(request.POST)
    roteiro_ok = itin.sede.is_valid() and (vazio or itin.valido())
    if form.is_valid() and roteiro_ok:
        try:
            dados = {c: form.cleaned_data[c] for c in ("quantidade_servidores", "observacoes")}
            dados["sede"] = itin.sede.cleaned_data["cidade"]
            salvo = services.salvar_roteiro(request.user, roteiro, dados,
                                            [] if vazio else itinerario.trechos(itin))
        except services.RegraViolada as exc:
            contexto = _contexto(request, roteiro, form, itin, str(exc))
            contexto.update(sujo=True, foco="alerta-roteiro")
            return render(request, template, contexto, status=422)
        if roteiro is None:
            messages.success(request, f"Roteiro #{salvo.pk} cadastrado.")
        return redirect(f"{reverse('viagens:editar_roteiro', args=[salvo.pk])}?salvo=1")
    contexto = _contexto(request, roteiro, form, itin)
    contexto.update(sujo=True, foco="resumo-erros" if form.errors else "alerta-roteiro")
    return render(request, template, contexto, status=422)


def novo(request: HttpRequest) -> HttpResponse:
    return _formulario(request, None)


def editar(request: HttpRequest, pk: int) -> HttpResponse:
    return _formulario(request, _roteiro_visivel(request, pk))


@require_POST
def cancelar(request: HttpRequest, pk: int) -> HttpResponse:
    roteiro = _roteiro_visivel(request, pk)
    services.cancelar_roteiro(request.user, roteiro)
    messages.success(request, f"Roteiro #{roteiro.pk} cancelado. Ele não aparece mais para "
                              "uso nos ofícios.")
    return redirect("viagens:roteiros")


@require_POST
def reativar(request: HttpRequest, pk: int) -> HttpResponse:
    roteiro = _roteiro_visivel(request, pk)
    services.reativar_roteiro(request.user, roteiro)
    messages.success(request, f"Roteiro #{roteiro.pk} reativado.")
    return redirect("viagens:editar_roteiro", pk=roteiro.pk)


@require_POST
def excluir(request: HttpRequest, pk: int) -> HttpResponse:
    roteiro = _roteiro_visivel(request, pk)
    try:
        services.excluir_roteiro(request.user, roteiro)
    except services.RegraViolada as exc:
        messages.error(request, str(exc))
        return redirect("viagens:roteiros")
    messages.success(request, f"Roteiro #{pk} excluído.")
    return redirect("viagens:roteiros")


@require_POST
def criar_oficio(request: HttpRequest, pk: int) -> HttpResponse:
    """"Criar ofício com este roteiro": o ofício nasce com os trechos do roteiro."""
    roteiro = _roteiro_visivel(request, pk)
    policies.exigir(policies.pode_criar(request.user),
                    "Seu usuário precisa estar lotado em uma unidade para criar ofícios.")
    try:
        oficio = services.criar_oficio_do_roteiro(request.user, roteiro)
    except services.RegraViolada as exc:
        messages.error(request, str(exc))
        return redirect("viagens:roteiros")
    messages.success(request, f"Ofício {oficio.numero_formatado} criado com o roteiro "
                              f"#{roteiro.pk}. Complete a equipe e os dados e salve.")
    return redirect("viagens:editar", oficio.pk)
