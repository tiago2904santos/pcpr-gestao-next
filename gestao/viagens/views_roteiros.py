"""Telas de roteiros cadastrados (como no sistema de referência): lista com abas e busca,
cadastro/edição com o mesmo itinerário do ofício, e "criar ofício com este roteiro"."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import F
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.vary import vary_on_headers

from gestao.cadastros.models import Municipio

from . import itinerario, policies, queries, services
from .dominio.bate_volta import BateVoltaInvalido
from .dominio.diarias import Faixa, RoteiroIncalculavel, SemTabelaDeDiarias
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
@require_GET
def oficios_do_roteiro(request: HttpRequest, pk: int) -> HttpResponse:
    """Fragmento HTMX: os ofícios que usaram este roteiro, para a janelinha da lista."""
    roteiro = get_object_or_404(policies.roteiros_visiveis(request.user), pk=pk)
    return render(request, "viagens/roteiros/_oficios.html", {
        "roteiro": roteiro,
        "oficios": list(roteiro.oficios.select_related("sede")
                        .prefetch_related("trechos__destino").order_by("-ano", "-numero")[:50]),
    })


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
        # No modo bate-volta a etapa de trechos é conferência: mostra o que foi gerado.
        "dias_bate_volta": _dias_de_bate_volta(
            list(queries.trechos_do_roteiro(roteiro))
            if roteiro and roteiro.bate_volta else []),
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
        # Linhas do banco (TrechoRoteiro/BateVoltaRoteiro) para preencher a tela — nome
        # próprio porque o caminho do POST reusa `trechos`/`blocos` para os objetos de
        # domínio que vão ao serviço.
        trechos_salvos = queries.trechos_do_roteiro(roteiro) if roteiro else []
        blocos_salvos = list(roteiro.bate_voltas.select_related("destino")) if roteiro else []
        itin = itinerario.montar(FORM_ID_ROTEIRO, sede=sede, trechos=trechos_salvos,
                                 blocos=blocos_salvos,
                                 bate_volta_ligado=bool(roteiro and roteiro.bate_volta))
        contexto = _contexto(request, roteiro, FormularioRoteiro(instance=roteiro), itin)
        contexto["recem_salvo"] = request.GET.get("salvo") == "1"
        return render(request, template, contexto)

    form = FormularioRoteiro(request.POST, instance=roteiro or Roteiro(sede=sede))
    acao = request.POST.get("acao")
    if acao in ("adicionar_destino", "alternar_modo"):  # sem JavaScript
        # Alternar o modo só troca a tela: nada é gravado até salvar.
        itin = itinerario.com_iniciais(FORM_ID_ROTEIRO, request.POST,
                                       mais_um=acao == "adicionar_destino",
                                       bate_volta_ligado=request.POST.get("bate_volta") == "on")
        form.is_valid()
        contexto = _contexto(request, roteiro, form, itin)
        foco = ("id_bv-0-cidade" if itin.bate_volta
                else f"id_destino-{itin.destinos.total_form_count() - 1}-cidade")
        contexto.update(foco=foco, sujo=True)
        return render(request, template, contexto)
    ligado = request.POST.get("bate_volta") == "on"
    itin = itinerario.montar(FORM_ID_ROTEIRO, dados=request.POST, bate_volta_ligado=ligado)
    vazio = itin.vazio(request.POST)
    roteiro_ok = itin.sede.is_valid() and (vazio or itin.valido())
    if form.is_valid() and roteiro_ok:
        try:
            dados = {"sede": itin.sede.cleaned_data["cidade"], "bate_volta": ligado}
            blocos = [] if vazio or not ligado else itin.blocos_em_ordem()
            if vazio:
                trechos = []
            elif ligado:
                trechos = itinerario.trechos_de_blocos(blocos, itin.sede.cleaned_data["cidade"])
            else:
                trechos = itinerario.trechos(itin)
            salvo = services.salvar_roteiro(request.user, roteiro, dados, trechos, blocos)
        except (services.RegraViolada, BateVoltaInvalido) as exc:
            contexto = _contexto(request, roteiro, form, itin, str(exc))
            contexto.update(sujo=True, foco="alerta-roteiro")
            return render(request, template, contexto, status=422)
        messages.success(request, f"Roteiro #{salvo.pk} "
                                  f"{'cadastrado' if roteiro is None else 'salvo'}.")
        # O autosave já guarda o caminho; salvar quer dizer "terminei" e volta para a lista.
        return redirect("viagens:roteiros")
    contexto = _contexto(request, roteiro, form, itin)
    contexto.update(sujo=True, foco="resumo-erros" if form.errors else "alerta-roteiro")
    return render(request, template, contexto, status=422)


def novo(request: HttpRequest) -> HttpResponse:
    return _formulario(request, None)


def editar(request: HttpRequest, pk: int) -> HttpResponse:
    return _formulario(request, _roteiro_visivel(request, pk))


def _dias_de_bate_volta(trechos) -> list[dict]:
    """Um bate-volta se lê por dia, não por perna: as pernas vêm aos pares (ida, volta)."""
    return [{"dia": ida.saida_em, "destino": ida.destino, "ida": ida, "volta": volta,
             "km": (ida.distancia_km or 0) + (volta.distancia_km or 0)}
            for ida, volta in zip(trechos[::2], trechos[1::2], strict=False)]


@require_POST
def autosave(request: HttpRequest) -> JsonResponse:
    """Grava o roteiro enquanto se preenche, a partir do momento em que a etapa 1 está
    completa (sede e um destino). Salva o que der: o que ainda não é válido fica em branco e
    o roteiro segue como rascunho — nunca se perde o que já foi digitado.

    Especificação do bate-volta e do rascunho: docs/superpowers/specs/.
    """
    pk = request.POST.get("roteiro_id")
    roteiro = _roteiro_visivel(request, int(pk)) if pk else None
    if roteiro is None:
        policies.exigir(policies.pode_criar_roteiro(request.user),
                        "Seu usuário precisa estar lotado em uma unidade para criar roteiros.")
        sede = services.configuracao_da_unidade(policies.unidade_do_usuario(request.user)).sede
    else:
        sede = roteiro.sede

    ligado = request.POST.get("bate_volta") == "on"
    itin = itinerario.montar(FORM_ID_ROTEIRO, dados=request.POST, bate_volta_ligado=ligado)
    if not itin.sede.is_valid():
        return JsonResponse({"salvo": False, "motivo": "sede"}, status=200)

    dados: dict[str, Any] = {"sede": itin.sede.cleaned_data["cidade"] or sede,
                             "bate_volta": ligado}
    # "Grava o que der": itinerário incompleto não impede o rascunho — só não vira trecho.
    trechos: list | None = []
    blocos: list = []
    if itin.valido():
        try:
            if ligado:
                blocos = itin.blocos_em_ordem()
                trechos = itinerario.trechos_de_blocos(blocos, dados["sede"])
            else:
                trechos = itinerario.trechos(itin)
        except (BateVoltaInvalido, services.RegraViolada):
            trechos, blocos = [], []
    try:
        salvo = services.salvar_roteiro(request.user, roteiro, dados, trechos, blocos)
    except services.RegraViolada as exc:
        return JsonResponse({"salvo": False, "motivo": str(exc)}, status=200)
    return JsonResponse({"salvo": True, "id": salvo.pk,
                         "em": timezone.localtime(salvo.atualizado_em).strftime("%H:%M")})


@require_POST
def previa_trechos(request: HttpRequest) -> HttpResponse:
    """Trechos que os bate-voltas geram, antes de salvar. Usa a mesma expansão do
    salvamento, para a prévia não poder divergir do que será gravado."""
    policies.exigir(policies.pode_criar_roteiro(request.user),
                    "Seu usuário precisa estar lotado em uma unidade para montar roteiros.")
    itin = itinerario.montar(FORM_ID_ROTEIRO, dados=request.POST, bate_volta_ligado=True)
    gerados: list = []
    if itin.sede.is_valid() and itin.blocos.is_valid():
        sede = itin.sede.cleaned_data["cidade"]
        try:
            informados = itinerario.trechos_de_blocos(itin.blocos_em_ordem(), sede)
        except BateVoltaInvalido:
            informados = []
        municipios = Municipio.objects.in_bulk(
            {m for t in informados for m in (t.origem_id, t.destino_id)})
        gerados = [SimpleNamespace(origem=municipios[t.origem_id],
                                   destino=municipios[t.destino_id],
                                   saida_em=t.saida_em, chegada_em=t.chegada_em,
                                   distancia_km=t.distancia_km) for t in informados]
    return render(request, "viagens/_trechos_gerados.html",
                  {"dias_bate_volta": _dias_de_bate_volta(gerados)})


@require_POST
def previa_diarias(request: HttpRequest) -> HttpResponse:
    """Diárias enquanto a pessoa preenche: recebe o itinerário da tela e devolve a seção
    calculada, sem gravar nada. Só responde com números quando há ida, volta e datas."""
    policies.exigir(policies.pode_criar_roteiro(request.user),
                    "Seu usuário precisa estar lotado em uma unidade para calcular diárias.")
    sede_unidade = services.configuracao_da_unidade(
        policies.unidade_do_usuario(request.user)).sede
    ligado = request.POST.get("bate_volta") == "on"
    itin = itinerario.montar(FORM_ID_ROTEIRO, dados=request.POST, bate_volta_ligado=ligado)
    contexto = {"numerado": True, "numero": "3", "aguardando": "Aguardando trechos",
                "faixas": {f.value: f.rotulo for f in Faixa}, "calculo": {},
                "texto_vazio": "O cálculo aparece aqui assim que o roteiro tiver ida e volta "
                               "com datas."}
    if itin.sede.is_valid() and itin.valido():
        sede = itin.sede.cleaned_data["cidade"] or sede_unidade
        try:
            trechos = (itinerario.trechos_de_blocos(itin.blocos_em_ordem(), sede) if ligado
                       else itinerario.trechos(itin))
            contexto["calculo"] = services.calcular_informados(trechos, sede).como_dict()
        except (RoteiroIncalculavel, SemTabelaDeDiarias, BateVoltaInvalido) as exc:
            contexto["oficio"] = {"diarias_erro": str(exc)}
    return render(request, "viagens/oficios/_diarias.html", contexto)


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
