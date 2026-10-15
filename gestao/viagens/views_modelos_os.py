"""Cadastro dos modelos de OS (gestor): lista, janela de novo/editar, ativar/desativar,
excluir e "Ver exemplo" (a folha de uma OS fictícia com os campos como estão, sem gravar).
A mesma receita de Textos prontos (cadastros/views.py)."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from . import modelos_os, ordens, policies
from .dominio import modelo_os as dominio
from .forms import FormularioModeloOS
from .models import ModeloOS
from .views import _migalhas
from .views_editor import moldura_da_folha, resposta_de_folha


def _lista(request: HttpRequest, *, form=None, editando=None, status=200) -> HttpResponse:
    policies.exigir(policies.pode_ver_modelos_os(request.user))
    termo = (request.GET.get("q") or "").strip()
    qs = ModeloOS.objects.annotate(n_ordens=Count("ordens")).prefetch_related("funcoes") \
        .order_by("-ativo", "ordem", "nome")
    if termo:
        qs = qs.filter(Q(nome__unaccent__icontains=termo)
                       | Q(referencia__unaccent__icontains=termo))
    gerir = policies.pode_gerir_modelos_os(request.user)
    lista = list(qs)
    for m in lista:  # o que cada linha oferece vem da política, não do template
        setattr(m, "excluivel", policies.pode_excluir_modelo_os(request.user, m))  # noqa: B010
        setattr(m, "pede_hora", m.usa_hora)  # noqa: B010
    if form is None and gerir and (pk := request.GET.get("editar", "")).isdigit():
        editando = ModeloOS.objects.filter(pk=int(pk)).first()
        form = FormularioModeloOS.de(editando) if editando else None
    abrir = form is not None or (gerir and request.GET.get("novo") == "1")
    if form is None:
        form = FormularioModeloOS()
    return render(request, "viagens/ordens/modelos.html", {
        "modelos": lista, "termo": termo, "form": form, "editando": editando,
        "ativos": sum(1 for m in lista if m.ativo),
        "inativos": sum(1 for m in lista if not m.ativo),
        "pode_gerir": gerir, "abrir_dialogo": abrir,
        "marcadores_etapa": sorted(dominio.MARCADORES_ETAPA),
        "marcadores_funcao": sorted(dominio.MARCADORES_FUNCAO),
        "migalhas": _migalhas(("Cadastros", reverse("cadastros:indice")),
                              ("Modelos de OS", ""))}, status=status)


@require_GET
def lista(request: HttpRequest) -> HttpResponse:
    return _lista(request)


def _formulario_enviado(request: HttpRequest) -> tuple[FormularioModeloOS, ModeloOS | None]:
    policies.exigir(policies.pode_gerir_modelos_os(request.user))
    pk = (request.POST.get("pk") or "").strip() or None
    if pk is not None and not pk.isdigit():
        raise Http404("Modelo não encontrado.")
    editando = get_object_or_404(ModeloOS, pk=int(pk)) if pk else None
    return FormularioModeloOS(request.POST), editando


@require_POST
def salvar(request: HttpRequest) -> HttpResponse:
    form, editando = _formulario_enviado(request)
    if form.is_valid():
        try:
            modelo = modelos_os.salvar(request.user, pk=editando.pk if editando else None,
                                       **form.dados_para_salvar())
        except modelos_os.ModeloInvalido as exc:
            form.add_error(None, str(exc))
        else:
            feito = "atualizado" if editando else "criado"
            messages.success(request, f"Modelo “{modelo.nome}” {feito}.")
            return redirect("viagens:modelos_os")
    return _lista(request, form=form, editando=editando, status=422)


@require_POST
@moldura_da_folha
def exemplo(request: HttpRequest) -> HttpResponse:
    """A folha de uma OS fictícia com o modelo como está na janela — sem gravar nada."""
    form, editando = _formulario_enviado(request)
    if not form.is_valid():
        return _lista(request, form=form, editando=editando, status=422)
    dados = form.dados_para_salvar()
    modelo = dominio.Modelo(
        nome=dados["nome"], referencia=dados["referencia"], textos=dados["textos"],
        funcoes=tuple(dominio.Funcao(f.get("codigo") or f"f{i}", f["nome"], f["texto"],
                                     f.get("icone", ""))
                      for i, f in enumerate(dados["funcoes"], 1)),
        justificativas=tuple(j.strip() for j in dados["justificativas"].splitlines()
                             if j.strip()),
        finalidade=dados["finalidade"])
    unidade = policies.unidade_do_usuario(request.user)
    if unidade is None:
        raise PermissionDenied("Sem unidade para montar o exemplo.")

    def gerar(nonce: str) -> str:
        return ordens.html_do_modelo(ordens.dados_de_exemplo(modelo, unidade), folha=True,
                                     nonce=nonce)
    return resposta_de_folha(request, gerar)


def _acao(request: HttpRequest, pk: int, executar) -> HttpResponse:
    modelo = get_object_or_404(ModeloOS, pk=pk)
    try:
        mensagem = executar(modelo)
    except (modelos_os.ModeloInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, mensagem)
    return redirect("viagens:modelos_os")


@require_POST
def ativo(request: HttpRequest, pk: int) -> HttpResponse:
    def executar(m):
        novo = modelos_os.alternar_ativo(request.user, m.pk)
        if novo.ativo:
            return f"“{m.nome}” reativado."
        return f"“{m.nome}” desativado: saiu das opções de modelo."
    return _acao(request, pk, executar)


@require_POST
def excluir(request: HttpRequest, pk: int) -> HttpResponse:
    return _acao(request, pk, lambda m: f"“{modelos_os.excluir(request.user, m.pk)}” excluído.")
