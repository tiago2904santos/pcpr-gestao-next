"""Cadastros de apoio: busca de municípios e textos prontos (o CRUD dos demais cadastros
está em views_crud.py)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.postgres.lookups import Unaccent
from django.core.exceptions import PermissionDenied
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.db.models.functions import Lower
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_GET, require_POST

from . import policies, textos
from .forms import FormularioTexto
from .models import ModeloTexto, Municipio


def _migalhas(rotulo: str):
    return [("Início", reverse("painel:inicio")), ("Viagens", reverse("viagens:painel")),
            ("Cadastros", reverse("cadastros:indice")), (rotulo, "")]


@require_GET
def buscar_municipios(request: HttpRequest) -> JsonResponse:
    """Autocompletar "Cidade/UF": prefixo sem acento/caixa, Paraná primeiro; `?uf=SC`
    restringe ao estado escolhido no itinerário."""
    termo = (request.GET.get("q") or "").strip()
    nome, _, uf = termo.partition("/")
    uf = uf or (request.GET.get("uf") or "")  # filtro do seletor de estado (itinerário)
    qs = Municipio.objects.annotate(n=Unaccent(Lower("nome"))).filter(
        n__startswith=Unaccent(Lower(Value(nome.strip()))))
    if uf.strip():
        qs = qs.filter(uf__iexact=uf.strip()[:2])
    prioridade = Case(When(uf="PR", then=0), default=1, output_field=IntegerField())
    resultados = qs.annotate(prioridade=prioridade).order_by("prioridade", "nome")[:12]
    return JsonResponse({"resultados": [
        {"id": f"{m.nome}/{m.uf}", "titulo": f"{m.nome}/{m.uf}", "meta": ""} for m in resultados
    ]})


# ---------------------------------------------------------------- textos prontos
ABAS_TEXTOS = [
    (ModeloTexto.Tipo.MOTIVO.value, "Motivos"),
    (ModeloTexto.Tipo.JUSTIFICATIVA.value, "Justificativas"),
    (ModeloTexto.Tipo.OFICIO.value, "Trechos"),
]


def _url_textos(tipo: str, **extra) -> str:
    return f"{reverse('cadastros:textos')}?{urlencode({'tipo': tipo, **extra})}"


def _lista_textos(request: HttpRequest, *, form=None, editando=None, status=200):
    """A lista de um tipo e a janela de novo/editar. A janela vem aberta quando há algo a
    mostrar nela: edição pedida (`?editar=<pk>`) ou formulário com erro."""
    tipo = request.GET.get("tipo") or request.POST.get("tipo") or ModeloTexto.Tipo.MOTIVO
    if tipo not in dict(ABAS_TEXTOS):
        tipo = ModeloTexto.Tipo.MOTIVO.value
    termo = (request.GET.get("q") or "").strip()
    qs = ModeloTexto.objects.filter(tipo=tipo).order_by("-ativo", "ordem", "nome")
    if termo:
        qs = qs.filter(Q(nome__unaccent__icontains=termo) | Q(texto__unaccent__icontains=termo))
    contagens = dict(ModeloTexto.objects.filter(ativo=True).values("tipo")
                     .annotate(n=Count("id")).values_list("tipo", "n"))
    gerir = policies.pode_gerir_textos(request.user)
    lista = list(qs)
    for t in lista:  # o que cada linha oferece vem da política, não do template
        setattr(t, "alteravel", policies.pode_alterar_texto(request.user, t))  # noqa: B010
        setattr(t, "excluivel", policies.pode_excluir_texto(request.user, t))  # noqa: B010
    if form is None and gerir and (pk := request.GET.get("editar", "")).isdigit():
        editando = ModeloTexto.objects.filter(pk=int(pk)).first()
        if editando and not policies.pode_alterar_texto(request.user, editando):
            editando = None  # padrão/do sistema: só o gestor abre para editar
        form = FormularioTexto.de(editando) if editando else None
    abrir = form is not None or (gerir and request.GET.get("novo") == "1")
    if form is None:
        form = FormularioTexto(initial={"tipo": tipo, "ordem": 100})
    return render(request, "cadastros/textos.html", {
        "textos": lista, "tipo": tipo, "termo": termo, "abas": ABAS_TEXTOS,
        "ativos": sum(1 for t in lista if t.ativo),
        "inativos": sum(1 for t in lista if not t.ativo),
        "contagens": contagens, "pode_gerir": gerir, "form": form, "editando": editando,
        "abrir_dialogo": abrir,
        # O padrão só tem efeito no motivo (é o texto do ofício novo).
        "usa_padrao": tipo == ModeloTexto.Tipo.MOTIVO,
        "pode_definir_padrao": policies.pode_definir_padrao(request.user),
        "migalhas": _migalhas("Textos prontos")}, status=status)


@require_GET
@permission_required("cadastros.view_modelotexto", raise_exception=True)
def textos_prontos(request: HttpRequest) -> HttpResponse:
    return _lista_textos(request)


def _quer_json(request: HttpRequest) -> bool:
    return "application/json" in request.headers.get("Accept", "")


@require_POST
def salvar_texto(request: HttpRequest) -> HttpResponse:
    """Cria ou altera (`pk`). A folha do ofício chama com Accept: JSON ("Guardar como texto
    pronto") e recebe o texto criado para pôr na escolha sem recarregar a folha."""
    policies.exigir(policies.pode_gerir_textos(request.user))
    pk = (request.POST.get("pk") or "").strip() or None
    if pk is not None and not pk.isdigit():
        raise Http404("Texto pronto não encontrado.")
    editando = get_object_or_404(ModeloTexto, pk=int(pk)) if pk else None
    form = FormularioTexto(request.POST)
    if form.is_valid():
        try:
            modelo = textos.salvar(request.user, pk=int(pk) if pk else None,
                                   **form.cleaned_data)
        except textos.TextoInvalido as exc:
            form.add_error(None, str(exc))
        else:
            if _quer_json(request):
                return JsonResponse({"id": modelo.pk, "nome": modelo.nome,
                                     "texto": modelo.texto})
            feito = "atualizado" if pk else "criado"
            messages.success(request, f"Texto pronto “{modelo.nome}” {feito}.")
            return redirect(_url_textos(modelo.tipo))
    if _quer_json(request):
        erros = [str(e) for lista in form.errors.values() for e in lista]
        return JsonResponse({"erro": " ".join(erros)}, status=422)
    return _lista_textos(request, form=form, editando=editando, status=422)


def _acao_texto(request: HttpRequest, pk: int, acao) -> HttpResponse:
    modelo = get_object_or_404(ModeloTexto, pk=pk)
    try:
        mensagem = acao(modelo)
    except (textos.TextoInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, mensagem)
    return redirect(_url_textos(modelo.tipo))


@require_POST
def texto_padrao(request: HttpRequest, pk: int) -> HttpResponse:
    def acao(m):
        if m.padrao:
            textos.deixar_de_ser_padrao(request.user, m.pk)
            return f"“{m.nome}” deixou de ser o padrão."
        textos.definir_padrao(request.user, m.pk)
        return f"“{m.nome}” agora é o texto padrão."
    return _acao_texto(request, pk, acao)


@require_POST
def texto_ativo(request: HttpRequest, pk: int) -> HttpResponse:
    def acao(m):
        novo = textos.alternar_ativo(request.user, m.pk)
        if novo.ativo:
            return f"“{m.nome}” reativado."
        return f"“{m.nome}” desativado: saiu da lista de escolha."
    return _acao_texto(request, pk, acao)


@require_POST
def texto_excluir(request: HttpRequest, pk: int) -> HttpResponse:
    return _acao_texto(request, pk, lambda m: f"“{textos.excluir(request.user, m.pk)}” excluído.")
