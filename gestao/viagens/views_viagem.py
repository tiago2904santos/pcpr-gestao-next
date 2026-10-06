"""Viagens (módulo 8): lista, nova viagem, a folha da viagem (dados, destinos, documentos
vinculados e os documentos agrupados, por etapa) e "novo documento já vinculado".
A regra está em `viagem.py`; a ficha em docs/migration/viagem.md."""

from __future__ import annotations

import re

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from gestao.cadastros.forms import formularios_de_cadastro_rapido

from . import policies, prestacao, viagem, viagem_conferencia
from .forms import FormularioViagem
from .linha_do_tempo import da_viagem
from .models import Viagem
from .views import POR_PAGINA, _migalhas
from .views_editor import primeiro_erro

ABAS = [("", "Todas", "todas"), ("futuras", "Que vão acontecer", "futuras"),
        ("atuais", "Em andamento e realizadas", "atuais"),
        ("prestadas", "Contas prestadas", "prestadas"),
        ("canceladas", "Canceladas", "canceladas")]
NUMERO_OFICIO = re.compile(r"^\s*(\d{1,5})\s*(?:/\s*(\d{4}))?\s*$")
ROTAS_NOVO = {"roteiro": "viagens:editar_roteiro", "oficio": "viagens:editar",
              "termo": "viagens:editar_termo", "ordem": "viagens:editar_ordem",
              "plano": "viagens:editar_plano"}


def _viagem_visivel(request: HttpRequest, pk: int) -> Viagem:
    v = get_object_or_404(Viagem.objects.select_related("unidade"), pk=pk)
    if not policies.pode_ver_viagem(request.user, v):
        raise Http404
    return v


def _filtrar(qs, aba: str):
    hoje = timezone.localdate()
    ativas = qs.exclude(situacao=Viagem.Situacao.CANCELADA)
    prestadas = prestacao.prestadas("viagem")
    if aba == "canceladas":
        return qs.filter(situacao=Viagem.Situacao.CANCELADA)
    if aba == "prestadas":
        return ativas.filter(prestadas)
    # As de contas prestadas saem das abas de quando (abas exclusivas, referência).
    if aba == "futuras":
        return ativas.filter(~prestadas, Q(data_inicio__gt=hoje) | Q(data_inicio__isnull=True))
    if aba == "atuais":
        return ativas.filter(~prestadas, data_inicio__lte=hoje)
    return qs


def _buscar(qs, termo: str):
    """Título, destino, servidor, placa e ofício (15/2026), como na referência."""
    if not termo:
        return qs
    filtro = (Q(titulo__unaccent__icontains=termo) | Q(motivo__unaccent__icontains=termo)
              | Q(destinos__municipio__nome__unaccent__icontains=termo)
              | Q(oficios__viajantes__servidor__nome__unaccent__icontains=termo))
    placa = re.sub(r"[^A-Za-z0-9]", "", termo).upper()
    if len(placa) >= 3 and any(c.isdigit() for c in placa):
        filtro |= Q(oficios__viatura__placa__icontains=placa)
    if (m := NUMERO_OFICIO.match(termo)):
        numero = Q(oficios__numero=int(m.group(1)))
        filtro |= numero & Q(oficios__ano=int(m.group(2))) if m.group(2) else numero
    return qs.filter(filtro).distinct()


@require_GET
def lista(request: HttpRequest) -> HttpResponse:
    policies.exigir(request.user.has_perm("viagens.view_viagem"))
    base = policies.viagens_visiveis(request.user)
    aba = request.GET.get("aba") or ""
    if aba not in {a for a, _, _ in ABAS}:
        aba = ""
    busca = (request.GET.get("q") or "").strip()
    buscadas = _buscar(base, busca)
    contagens = {"todas": buscadas.count(),
                 **{chave: _filtrar(buscadas, chave).count() for chave, _, _ in ABAS if chave}}
    qs = (_filtrar(buscadas, aba).select_related("unidade")
          .prefetch_related("destinos__municipio", "tipos")
          .annotate(n_oficios=Count("oficios", distinct=True),
                    n_ordens=Count("ordens", distinct=True),
                    n_planos=Count("planos", distinct=True)))
    from django.db.models import F
    ordem = ([F("data_inicio").asc(nulls_last=True), "pk"] if aba == "futuras"
             else ["-criado_em", "-pk"])
    pagina = Paginator(qs.order_by(*ordem), POR_PAGINA).get_page(request.GET.get("pagina"))
    hoje = timezone.localdate()
    linhas = [{"v": v, "quando": viagem.dias_para(v, hoje),
               "destinos": ", ".join(str(d.municipio) for d in v.destinos.all())}
              for v in pagina.object_list]
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    return render(request, "viagens/viagem/lista.html", {
        "page_obj": pagina, "linhas": linhas, "abas": ABAS, "aba": aba, "busca": busca,
        "contagens": contagens, "pode_criar": policies.pode_criar_viagem(request.user),
        "querystring_base": (filtros.urlencode() + "&") if filtros else "",
        "migalhas": _migalhas(("Todas as viagens", ""))})


@require_POST
def criar(request: HttpRequest) -> HttpResponse:
    try:
        nova = viagem.criar(request.user)
    except (viagem.ViagemInvalida, PermissionDenied) as exc:
        messages.error(request, str(exc))
        return redirect("viagens:viagens")
    return redirect("viagens:editar_viagem", nova.pk)


def _formulario(request: HttpRequest, v: Viagem, data=None) -> FormularioViagem:
    inicial = None if data is not None else {
        "versao": viagem.versao_de(v), "tipos": list(v.tipos.all()), "motivo": v.motivo,
        "descricao": v.descricao, "data_inicio": v.data_inicio, "data_fim": v.data_fim,
        "destinos": [d.municipio for d in v.destinos.select_related("municipio")],
        **{t: list(getattr(v, t).all()) for t in viagem.TIPOS_DE_DOCUMENTO},
        "vinculos_presentes": True}
    return FormularioViagem(data, initial=inicial, viagem=v,
                            fonte_municipios=reverse("cadastros:buscar_municipios"))


def _tela(request: HttpRequest, v: Viagem, form: FormularioViagem, status: int = 200):
    docs = viagem.documentos(v)
    return render(request, "viagens/viagem/editar.html", {
        "v": v, "form": form, "docs": docs, "quando": viagem.dias_para(v),
        "quadro": None if v.cancelada else viagem_conferencia.quadro(v),
        "diferencas": [] if v.cancelada else viagem_conferencia.coerencia(v),
        "destinos": [d.municipio for d in v.destinos.select_related("municipio")],
        "editavel": policies.pode_editar_viagem(request.user, v),
        "historico": da_viagem(v),
        "pode_excluir": policies.pode_excluir_viagem(request.user, v),
        "pode_cancelar": policies.pode_editar_viagem(request.user, v),
        "pode_reativar": v.cancelada and policies.pode_reativar_viagem(request.user, v),
        "pode_repetir": policies.pode_criar_viagem(request.user),
        "form_repetir": _form_repetir(),
        "pode_semear": bool(v.data_inicio and v.destinos.exists()),
        "migalhas": _migalhas(("Todas as viagens", reverse("viagens:viagens")),
                              (str(v), ""))}, status=status)


def _form_repetir():
    from .forms import FormularioRepetir
    return FormularioRepetir(auto_id="repetir_%s")


@require_GET
def editar(request: HttpRequest, pk: int) -> HttpResponse:
    v = _viagem_visivel(request, pk)
    return _tela(request, v, _formulario(request, v))


def _gravar(request: HttpRequest, v: Viagem, form: FormularioViagem) -> Viagem:
    dados = form.cleaned_data
    return viagem.salvar_dados(
        request.user, v.pk, tipos=list(dados["tipos"]), motivo=dados["motivo"],
        descricao=dados["descricao"], data_inicio=dados["data_inicio"],
        data_fim=dados["data_fim"], destinos=dados["destinos"], vinculos=form.vinculos(),
        versao=dados["versao"])


@require_POST
def salvar(request: HttpRequest, pk: int) -> HttpResponse:
    v = _viagem_visivel(request, pk)
    policies.exigir(policies.pode_editar_viagem(request.user, v),
                    "Esta viagem não pode ser alterada.")
    form = _formulario(request, v, request.POST)
    if form.is_valid():
        try:
            _gravar(request, v, form)
        except viagem.ViagemInvalida as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Dados da viagem atualizados.")
            return redirect("viagens:editar_viagem", v.pk)
    return _tela(request, v, form, status=422)


@require_POST
def autosave(request: HttpRequest, pk: int) -> JsonResponse:
    v = _viagem_visivel(request, pk)
    if not policies.pode_editar_viagem(request.user, v):
        return JsonResponse({"salvo": False, "mensagem": "Esta viagem não pode ser alterada."})
    form = _formulario(request, v, request.POST)
    if not form.is_valid():
        return JsonResponse({"salvo": False, "mensagem": primeiro_erro(form)})
    try:
        salva = _gravar(request, v, form)
    except viagem.ViagemInvalida as exc:
        return JsonResponse({"salvo": False, "mensagem": f"Não salvo: {exc}"})
    except PermissionDenied:
        return JsonResponse({"salvo": False, "mensagem": "Esta viagem não pode mais ser alterada."})
    return JsonResponse({"salvo": True, "recarregar": False,
                         "em": timezone.localtime(salva.atualizado_em).strftime("%H:%M"),
                         "campos": {"versao": viagem.versao_de(salva)}})


@require_POST
def excluir(request: HttpRequest, pk: int) -> HttpResponse:
    v = _viagem_visivel(request, pk)
    titulo = str(v)
    try:
        soltos = viagem.excluir(request.user, v.pk)
    except (viagem.ViagemInvalida, PermissionDenied) as exc:
        messages.error(request, str(exc))
        return redirect("viagens:editar_viagem", v.pk)
    texto = f"Viagem “{titulo}” excluída."
    if soltos:
        texto += f" {soltos} documento(s) continuam existindo, sem viagem."
    messages.success(request, texto)
    return redirect("viagens:viagens")


@require_POST
def cancelar(request: HttpRequest, pk: int) -> HttpResponse:
    v = _viagem_visivel(request, pk)
    try:
        viagem.cancelar(request.user, v.pk, request.POST.get("motivo", ""))
    except (viagem.ViagemInvalida, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Viagem cancelada. Todos os documentos vinculados também "
                                  "foram cancelados.")
    return redirect("viagens:editar_viagem", v.pk)


@require_POST
def reativar(request: HttpRequest, pk: int) -> HttpResponse:
    v = _viagem_visivel(request, pk)
    try:
        viagem.reativar(request.user, v.pk)
    except (viagem.ViagemInvalida, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Viagem reativada. Os documentos cancelados junto com ela "
                                  "também foram reativados.")
    return redirect("viagens:editar_viagem", v.pk)


@require_POST
def aplicar_coerencia(request: HttpRequest, pk: int) -> HttpResponse:
    """"Aplicar em todos": período, destinos e equipe da viagem nos documentos sem via
    assinada (referência)."""
    v = _viagem_visivel(request, pk)
    try:
        r = viagem_conferencia.aplicar(request.user, v.pk, request.POST.getlist("chave") or None)
    except PermissionDenied as exc:
        messages.error(request, str(exc))
    else:
        if r.atualizados:
            messages.success(request, "Documentos atualizados com os dados da viagem: "
                                      f"{', '.join(r.atualizados)}.")
        for documento, campo in r.pulados:
            messages.warning(request, f"{documento} já tem versão assinada e não foi alterado "
                                      f"({campo}). Corrija e assine de novo, se for o caso.")
        if not r.atualizados and not r.pulados:
            messages.info(request, "Nada a corrigir: os documentos já batem com a viagem.")
    return redirect(reverse("viagens:editar_viagem", args=[v.pk]) + "#conferencia")


@require_http_methods(["POST"])
def novo_documento(request: HttpRequest, pk: int, tipo: str) -> HttpResponse:
    """Cria o documento em rascunho, já vinculado e semeado, e abre a folha dele."""
    v = _viagem_visivel(request, pk)
    if tipo not in ROTAS_NOVO:
        raise Http404
    try:
        doc = viagem.novo_documento(request.user, v.pk, tipo)
    except (viagem.ViagemInvalida, PermissionDenied) as exc:
        messages.error(request, str(exc))
        return redirect(reverse("viagens:editar_viagem", args=[v.pk]) + "#documentos")
    except Exception as exc:  # regra do módulo do documento (ex.: unidade sem configuração)
        from . import ordens, planos, services, termos
        if not isinstance(exc, (services.RegraViolada, termos.TermoInvalido,
                                ordens.OrdemInvalida, planos.PlanoInvalido)):
            raise
        messages.error(request, str(exc))
        return redirect(reverse("viagens:editar_viagem", args=[v.pk]) + "#documentos")
    messages.success(request, f"{doc} criado já vinculado à viagem.")
    return redirect(ROTAS_NOVO[tipo], doc.pk)


@require_http_methods(["GET", "POST"])
def gerar_documentos(request: HttpRequest, pk: int) -> HttpResponse:
    """Gerar documentos em lote (referência): um ofício por equipe e, se pedidos e ainda
    inexistentes, termos, OS e plano. "Adicionar/Remover ofício" reenviam sem gravar."""
    from . import viagem_lote
    from .forms import FormularioLote

    v = _viagem_visivel(request, pk)
    if not policies.pode_editar_viagem(request.user, v):
        messages.error(request, "Reative a viagem antes de gerar documentos.")
        return redirect("viagens:editar_viagem", v.pk)
    fonte = reverse("cadastros:buscar_servidores")
    acao = request.POST.get("acao", "")
    try:
        quantidade = int(request.POST.get("quantidade") or 1)
    except ValueError:
        quantidade = 1
    erros: list[str] = []
    if request.method == "POST" and acao in ("adicionar", "remover"):
        dados = request.POST.copy()
        if acao == "adicionar":
            quantidade = min(quantidade + 1, viagem_lote.MAX_OFICIOS)
        elif quantidade > 1:
            quantidade -= 1
        form = FormularioLote(dados, quantidade=quantidade, fonte_servidores=fonte)
        form.is_valid()
        form.errors.clear()
    elif request.method == "POST":
        form = FormularioLote(request.POST, quantidade=quantidade, fonte_servidores=fonte)
        if form.is_valid():
            try:
                r = viagem_lote.gerar(request.user, v.pk, form.equipes(),
                                      com_termos=form.cleaned_data["termos"],
                                      com_ordem=form.cleaned_data["ordem"],
                                      com_plano=form.cleaned_data["plano"])
            except viagem_lote.LoteInvalido as exc:
                erros = exc.erros
            else:
                numeros = ", ".join(o.numero_formatado for o in r.oficios)
                partes = [f"{len(r.oficios)} ofício(s) ({numeros})"]
                if r.termos:
                    partes.append(f"{r.termos} termo(s)")
                if r.ordem:
                    partes.append(str(r.ordem))
                if r.plano:
                    partes.append(str(r.plano))
                messages.success(request, "Documentos gerados em rascunho: " + ", ".join(partes)
                                 + ". Revise e emita cada um na folha dele.")
                for aviso in r.avisos:
                    messages.warning(request, aviso)
                return redirect(reverse("viagens:editar_viagem", args=[v.pk]) + "#documentos")
    else:
        form = FormularioLote(quantidade=1, fonte_servidores=fonte)
    docs = viagem.documentos(v)
    return render(request, "viagens/viagem/lote.html", {
        "v": v, "form": form, "erros": erros, "docs": docs,
        "tem_ordem": any(not o.cancelada for o in docs.ordens),
        "tem_plano": any(not p.cancelado for p in docs.planos),
        "roteiro": next((r for r in reversed(docs.roteiros) if r.editavel), None),
        **formularios_de_cadastro_rapido(),
        "migalhas": _migalhas(("Todas as viagens", reverse("viagens:viagens")),
                              (str(v), reverse("viagens:editar_viagem", args=[v.pk])),
                              ("Gerar documentos", ""))}, status=422 if erros else 200)


@require_POST
def repetir(request: HttpRequest, pk: int) -> HttpResponse:
    """A mesma viagem em outra data (referência): números novos, sem protocolo/assinatura."""
    from . import viagem_repetir
    from .forms import FormularioRepetir

    v = _viagem_visivel(request, pk)
    form = FormularioRepetir(request.POST)
    if not form.is_valid():
        messages.error(request, primeiro_erro(form))
        return redirect("viagens:editar_viagem", v.pk)
    try:
        nova = viagem_repetir.repetir(request.user, v.pk, form.cleaned_data["nova_data"],
                                      form.cleaned_data["nova_cidade"])
    except (viagem.ViagemInvalida, PermissionDenied) as exc:
        messages.error(request, str(exc))
        return redirect("viagens:editar_viagem", v.pk)
    messages.success(request, "Viagem repetida em rascunho, com roteiro, ofícios, plano, ordem "
                              "de serviço e termos. Números e protocolos são novos; confira os "
                              "documentos antes de emitir.")
    return redirect("viagens:editar_viagem", nova.pk)

