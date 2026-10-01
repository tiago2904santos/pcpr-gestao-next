"""Telas do módulo Viagens (piloto: painel, lista, novo, edição, detalhe, documentos)."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.vary import vary_on_headers

from gestao.cadastros.models import Servidor

from . import policies, queries, services
from .documentos.dados import dados_do_oficio
from .documentos.pdf import ASSETS, html_do_documento
from .dominio.diarias import Faixa
from .forms import (
    ConjuntoDestinos,
    FormularioNovoOficio,
    FormularioOficio,
    FormularioRetorno,
    iniciais_do_roteiro,
)
from .models import Documento, Oficio
from .queries import trechos_de, viajantes_de

POR_PAGINA = 20


def _htmx(request: HttpRequest) -> bool:
    return bool(getattr(request, "htmx", False))


def _oficio_visivel(request: HttpRequest, pk: int) -> Oficio:
    oficio = get_object_or_404(
        Oficio.objects.select_related("unidade", "viatura", "viatura__combustivel", "sede",
                                      "transporte_combustivel"), pk=pk)
    if not policies.pode_ver(request.user, oficio):
        raise Http404  # não revela a existência de ofícios de outras unidades
    return oficio


def _migalhas(*itens: tuple[str, str]) -> list[tuple[str, str]]:
    return [("Início", reverse("painel:inicio")), ("Viagens", reverse("viagens:painel")),
            *itens]


# ------------------------------------------------------------------ painel
@require_GET
def painel(request: HttpRequest) -> HttpResponse:
    qs = policies.oficios_visiveis(request.user)
    pendentes = list(queries.com_dados_de_lista(
        qs.filter(situacao=Oficio.Situacao.RASCUNHO)).order_by("-atualizado_em")[:5])
    proximos = list(queries.com_dados_de_lista(
        qs.exclude(situacao=Oficio.Situacao.CANCELADO).filter(
            trechos__ordem=1, trechos__saida_em__gte=timezone.now())
    ).order_by("primeira_saida")[:5])  # type: ignore[misc]  # anotado em com_dados_de_lista
    return render(request, "viagens/painel.html", {
        "indicadores": queries.indicadores_do_painel(qs),
        "pendentes": pendentes, "proximos": proximos,
        "pode_editar_oficios": policies.edita_oficios(request.user),
        "pode_criar": policies.pode_criar(request.user),
        "migalhas": [("Início", reverse("painel:inicio")), ("Viagens", "")],
    })


# ------------------------------------------------------------------ lista
@require_GET
@vary_on_headers("HX-Request", "HX-Target")  # senão o "Voltar" do navegador reusa o fragmento
def lista(request: HttpRequest) -> HttpResponse:
    if not policies.pode_listar(request.user):
        raise PermissionDenied
    base = policies.oficios_visiveis(request.user)
    situacao = request.GET.get("situacao") or ""
    termo = (request.GET.get("q") or "").strip()
    qs = queries.aplicar_filtro_situacao(base, situacao)
    qs = services.buscar_por_texto(qs, termo)
    ordem = request.GET.get("ordem") or "-numero"
    ordens = {"-numero": ("-ano", "-numero"), "numero": ("ano", "numero"),
              "saida": ("primeira_saida",), "-saida": ("-primeira_saida",)}
    qs = queries.com_dados_de_lista(qs).order_by(*ordens.get(ordem, ordens["-numero"]))
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    contexto = {
        "page_obj": pagina,
        "oficios": pagina.object_list,
        "contagens": queries.contagens(base),
        "situacao": situacao,
        "termo": termo,
        "ordem": ordem,
        "querystring_base": (filtros.urlencode() + "&") if filtros else "",
        "abas": [("", "Todos", "todos")] + [
            (chave, rotulo, chave) for chave, (rotulo, _) in queries.FILTROS_SITUACAO.items()],
        "pode_criar": policies.pode_criar(request.user),
        "pode_editar_oficios": policies.edita_oficios(request.user),
        "agora": timezone.now(),
        "migalhas": _migalhas(("Ofícios", "")),
    }
    if _htmx(request) and request.htmx.target == "resultados":  # type: ignore[attr-defined]
        return render(request, "viagens/oficios/lista.html#resultados", contexto)
    return render(request, "viagens/oficios/lista.html", contexto)


# ------------------------------------------------------------------ novo
def novo(request: HttpRequest) -> HttpResponse:
    policies.exigir(policies.pode_criar(request.user),
                    "Seu usuário precisa estar lotado em uma unidade para criar ofícios.")
    form = FormularioNovoOficio(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            oficio = services.criar_rascunho(request.user,
                                             data_oficio=form.cleaned_data["data_oficio"])
            if form.cleaned_data["motivo"]:
                services.salvar_dados(oficio, request.user,
                                      {"motivo": form.cleaned_data["motivo"]})
        except services.RegraViolada as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Ofício {oficio.numero_formatado} criado como rascunho. "
                                      "Agora inclua a equipe e o roteiro.")
            return redirect(f"{reverse('viagens:editar', args=[oficio.pk])}#equipe")
    unidade = policies.unidade_do_usuario(request.user)
    return render(request, "viagens/oficios/novo.html", {
        "form": form, "unidade": unidade,
        "migalhas": _migalhas(("Ofícios", reverse("viagens:oficios")), ("Novo ofício", "")),
    })


# ------------------------------------------------------------------ edição
SECOES_DO_OFICIO = [("dados", "Dados"), ("equipe", "Equipe"), ("transporte", "Transporte"),
                    ("roteiro", "Roteiro"), ("diarias", "Diárias"),
                    ("justificativa", "Justificativa")]


def _contexto_edicao(request, oficio, form=None, destinos=None, retorno=None, erro_roteiro=""):
    if destinos is None or retorno is None:
        iniciais_destinos, inicial_retorno = iniciais_do_roteiro(oficio)
        destinos = destinos or ConjuntoDestinos(initial=iniciais_destinos, prefix="destino")
        retorno = retorno or FormularioRetorno(initial=inicial_retorno, prefix="retorno")
    prontidao = services.verificar_prontidao(oficio)
    secoes = []
    for chave, rotulo in SECOES_DO_OFICIO:
        pendencias = prontidao.da_secao(chave)
        ok = not pendencias and (chave != "diarias" or bool(oficio.diarias_resumo))
        secoes.append({"chave": chave, "rotulo": rotulo, "ok": ok,
                       "bloqueia": any(p.bloqueia for p in pendencias)})
    return {
        "oficio": oficio,
        "form": form or FormularioOficio(instance=oficio),
        "secoes": secoes,
        "secoes_ok": sum(1 for sec in secoes if sec["ok"]),
        "recem_salvo": request.GET.get("salvo") == "1",
        "destinos": destinos,
        "retorno": retorno,
        "erro_roteiro": erro_roteiro,
        "viajantes": viajantes_de(oficio),
        "prontidao": prontidao,
        "prazo": services.avaliar_prazo_do_oficio(oficio),
        "assunto": services.assunto_do_oficio(oficio),
        "calculo": oficio.diarias_calculo,
        "faixas": {f.value: f.rotulo for f in Faixa},
        "pode_emitir": policies.pode_emitir(request.user, oficio),
        "pode_excluir": policies.pode_excluir(request.user, oficio),
        "migalhas": _migalhas(("Ofícios", reverse("viagens:oficios")),
                              (oficio.numero_formatado, reverse("viagens:detalhe",
                                                                args=[oficio.pk])),
                              ("Editar", "")),
    }


def editar(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    if not policies.pode_editar(request.user, oficio):
        if oficio.editavel:
            messages.info(request, "Seu perfil permite consultar, mas não editar ofícios.")
        else:
            messages.info(request, f"O Ofício {oficio.numero_formatado} está "
                                   f"{oficio.get_situacao_display().lower()} e não pode ser "
                                   "editado; veja os detalhes abaixo.")
        return redirect("viagens:detalhe", pk=oficio.pk)
    if request.method != "POST":
        return render(request, "viagens/oficios/editar.html", _contexto_edicao(request, oficio))

    form = FormularioOficio(request.POST, instance=oficio)
    if request.POST.get("acao") == "adicionar_destino":
        # Reexibe o formulário com uma linha a mais, preservando o que foi digitado.
        total = int(request.POST.get("destino-TOTAL_FORMS") or 0)
        iniciais = [
            {c: request.POST.get(f"destino-{i}-{c}", "") for c in ("cidade", "saida", "chegada")}
            for i in range(total) if not request.POST.get(f"destino-{i}-DELETE")
        ]
        ultimo = iniciais[-1] if iniciais else {}
        iniciais.append({"saida": ultimo.get("chegada", "")})
        destinos = ConjuntoDestinos(initial=iniciais[:10], prefix="destino")
        retorno = FormularioRetorno(initial={c: request.POST.get(f"retorno-{c}", "")
                                             for c in ("saida", "chegada")}, prefix="retorno")
        form.is_valid()
        contexto = _contexto_edicao(request, oficio, form, destinos, retorno)
        contexto["foco"] = f"id_destino-{len(iniciais) - 1}-cidade"
        contexto["sujo"] = True  # nada foi salvo ainda: avisa e protege a saída
        return render(request, "viagens/oficios/editar.html", contexto)
    destinos = ConjuntoDestinos(request.POST, prefix="destino")
    retorno = FormularioRetorno(request.POST, prefix="retorno")
    roteiro_vazio = not any(
        request.POST.get(f"destino-{i}-{c}") for i in range(10)
        for c in ("cidade", "saida", "chegada")
    ) and not any(request.POST.get(f"retorno-{c}") for c in ("saida", "chegada"))
    roteiro_ok = roteiro_vazio or (destinos.is_valid() and retorno.is_valid())
    if form.is_valid() and roteiro_ok:
        try:
            dados = {k: v for k, v in form.cleaned_data.items() if k != "versao"}
            trechos = None if roteiro_vazio else _trechos_informados(oficio, destinos, retorno)
            oficio = services.salvar_edicao(oficio, request.user, dados, trechos,
                                            versao=form.cleaned_data.get("versao"))
        except services.ConflitoDeEdicao as exc:
            form.add_error(None, str(exc))
        except services.RegraViolada as exc:
            contexto = _contexto_edicao(request, oficio, form, destinos, retorno, str(exc))
            contexto.update(sujo=True, foco="alerta-roteiro")
            return render(request, "viagens/oficios/editar.html", contexto, status=422)
        else:
            if request.POST.get("acao") == "emitir":
                bloqueantes = services.verificar_prontidao(oficio).bloqueantes
                if bloqueantes:
                    messages.warning(request, f"Rascunho salvo, mas ainda há {len(bloqueantes)} "
                                              "pendência(s) para emitir. Veja a seção 7.")
                    return redirect(f"{reverse('viagens:editar', args=[oficio.pk])}#emissao")
                return redirect("viagens:revisar_emissao", pk=oficio.pk)
            # A confirmação é da própria barra de ações ("Rascunho salvo às HH:MM"),
            # não de um toast: o operador salva dezenas de vezes por dia.
            return redirect(f"{reverse('viagens:editar', args=[oficio.pk])}?salvo=1")
    contexto = _contexto_edicao(request, oficio, form, destinos, retorno)
    contexto.update(sujo=True, foco="resumo-erros" if form.errors else "alerta-roteiro")
    return render(request, "viagens/oficios/editar.html", contexto, status=422)


def _trechos_informados(oficio, destinos, retorno) -> list[services.TrechoInformado]:
    trechos = []
    origem = oficio.sede
    for f in destinos:
        if not f.cleaned_data or f.cleaned_data.get("DELETE"):
            continue
        cidade = f.cleaned_data["cidade"]
        trechos.append(services.TrechoInformado(origem.pk, cidade.pk, f.cleaned_data["saida"],
                                                f.cleaned_data["chegada"]))
        origem = cidade
    trechos.append(services.TrechoInformado(origem.pk, oficio.sede_id,
                                            retorno.cleaned_data["saida"],
                                            retorno.cleaned_data["chegada"]))
    return trechos


# ------------------------------------------------------------------ equipe (HTMX)
def _secao_equipe(request, oficio, erro: str = "") -> HttpResponse:
    oficio.refresh_from_db()
    contexto = {
        "oficio": oficio, "erro_equipe": erro, "oob": True,
        "viajantes": viajantes_de(oficio),
        "prontidao": services.verificar_prontidao(oficio),
    }
    resposta = render(request, "viagens/oficios/_equipe.html", contexto)
    resposta["HX-Trigger"] = "equipe-alterada"
    return resposta


@require_POST
def adicionar_viajante(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    servidor = get_object_or_404(Servidor, pk=request.POST.get("id"))
    try:
        services.adicionar_viajante(oficio, request.user, servidor)
    except services.RegraViolada as exc:
        return _secao_equipe(request, oficio, str(exc))
    if not _htmx(request):
        return redirect(f"{reverse('viagens:editar', args=[pk])}#equipe")
    return _secao_equipe(request, oficio)


@require_POST
def remover_viajante(request: HttpRequest, pk: int, viajante_id: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    services.remover_viajante(oficio, request.user, viajante_id)
    if not _htmx(request):
        return redirect(f"{reverse('viagens:editar', args=[pk])}#equipe")
    return _secao_equipe(request, oficio)


@require_POST
def definir_motorista(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    viajante_id = request.POST.get("viajante") or None
    services.definir_motorista(oficio, request.user, int(viajante_id) if viajante_id else None)
    if not _htmx(request):
        return redirect(f"{reverse('viagens:editar', args=[pk])}#equipe")
    return _secao_equipe(request, oficio)


@require_GET
def secao_diarias(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    return render(request, "viagens/oficios/_diarias.html", {
        "oficio": oficio, "calculo": oficio.diarias_calculo, "numerado": True,
        "faixas": {f.value: f.rotulo for f in Faixa}})


# ------------------------------------------------------------------ emissão
def revisar_emissao(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    policies.exigir(policies.pode_emitir(request.user, oficio),
                    "Este ofício não pode ser emitido por você agora.")
    services.recalcular_diarias(oficio)
    prontidao = services.verificar_prontidao(oficio)
    return render(request, "viagens/oficios/revisar_emissao.html", {
        "oficio": oficio, "prontidao": prontidao, "dados": dados_do_oficio(oficio),
        "prazo": services.avaliar_prazo_do_oficio(oficio),
        "migalhas": _migalhas(("Ofícios", reverse("viagens:oficios")),
                              (oficio.numero_formatado, reverse("viagens:detalhe",
                                                                args=[oficio.pk])),
                              ("Emitir", "")),
    })


@require_POST
def emitir(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    try:
        services.emitir(oficio, request.user, versao=int(request.POST.get("versao") or 0) or None)
    except services.RegraViolada as exc:
        messages.error(request, str(exc))
        return redirect("viagens:revisar_emissao", pk=pk)
    messages.success(request, f"Ofício {oficio.numero_formatado} emitido. O PDF está sendo "
                              "gerado e aparece em Documentos em instantes.")
    return redirect("viagens:detalhe", pk=pk)


@require_POST
def reabrir(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    try:
        services.reabrir(oficio, request.user, request.POST.get("motivo", ""))
    except services.RegraViolada as exc:
        messages.error(request, str(exc))
        return redirect("viagens:detalhe", pk=pk)
    messages.success(request, "Ofício reaberto. Corrija e emita uma nova versão.")
    return redirect("viagens:editar", pk=pk)


@require_POST
def cancelar(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    try:
        services.cancelar(oficio, request.user, request.POST.get("motivo", ""))
    except services.RegraViolada as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Ofício {oficio.numero_formatado} cancelado.")
    return redirect("viagens:detalhe", pk=pk)


@require_POST
def excluir(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    numero = services.excluir_rascunho(oficio, request.user)
    messages.success(request, f"Rascunho {numero} excluído; o número volta a ficar disponível.")
    return redirect("viagens:oficios")


# ------------------------------------------------------------------ detalhe
@require_GET
def detalhe(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    documentos = list(oficio.documentos.select_related("emitido_por"))
    return render(request, "viagens/oficios/detalhe.html", {
        "oficio": oficio,
        "viajantes": viajantes_de(oficio),
        "trechos": trechos_de(oficio),
        "documentos": documentos,
        "gerando": any(d.situacao == Documento.Situacao.GERANDO for d in documentos),
        "historico": list(oficio.historico.select_related("usuario")[:30]),
        "prontidao": services.verificar_prontidao(oficio) if oficio.editavel else None,
        "prazo": services.avaliar_prazo_do_oficio(oficio),
        "assunto": services.assunto_do_oficio(oficio),
        "calculo": oficio.diarias_calculo,
        "faixas": {f.value: f.rotulo for f in Faixa},
        "pode_editar": policies.pode_editar(request.user, oficio),
        "pode_emitir": policies.pode_emitir(request.user, oficio),
        "pode_reabrir": policies.pode_reabrir(request.user, oficio),
        "pode_cancelar": policies.pode_cancelar(request.user, oficio),
        "pode_excluir": policies.pode_excluir(request.user, oficio),
        "migalhas": _migalhas(("Ofícios", reverse("viagens:oficios")),
                              (oficio.numero_formatado, "")),
    })


@require_GET
def resumo(request: HttpRequest, pk: int) -> HttpResponse:
    """Fragmento HTMX: o registro da lista se expande com roteiro, equipe e documentos."""
    oficio = _oficio_visivel(request, pk)
    return render(request, "viagens/oficios/_resumo.html", {
        "oficio": oficio,
        "viajantes": viajantes_de(oficio),
        "trechos": trechos_de(oficio),
        "documentos": list(oficio.documentos.select_related("emitido_por")),
        "prontidao": services.verificar_prontidao(oficio) if oficio.editavel else None,
        "pode_editar": policies.pode_editar(request.user, oficio),
    })


@require_GET
def documentos_parcial(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    documentos = list(oficio.documentos.select_related("emitido_por"))
    return render(request, "viagens/oficios/_documentos.html", {
        "oficio": oficio, "documentos": documentos,
        "gerando": any(d.situacao == Documento.Situacao.GERANDO for d in documentos)})


@require_GET
def baixar_documento(request: HttpRequest, documento_id: int) -> FileResponse:
    doc = get_object_or_404(Documento.objects.select_related("oficio"), pk=documento_id)
    if not policies.pode_ver(request.user, doc.oficio):
        raise Http404
    if doc.situacao != Documento.Situacao.PRONTO:
        raise Http404("Documento ainda não gerado.")
    resposta = FileResponse(doc.arquivo.open("rb"), content_type="application/pdf",
                            as_attachment=request.GET.get("baixar") == "1",
                            filename=doc.nome_arquivo)
    resposta["X-Content-SHA256"] = doc.sha256
    return resposta


@require_GET
def previa(request: HttpRequest, pk: int) -> HttpResponse:
    """Minuta em PDF gerada na hora (rascunho), com marca d'água — não é arquivada."""
    oficio = _oficio_visivel(request, pk)
    tipo = request.GET.get("tipo", "oficio")
    if tipo not in {"oficio", "justificativa"}:
        raise Http404
    dados = dados_do_oficio(oficio)
    from weasyprint import HTML

    pdf = HTML(string=html_do_documento(tipo, dados, previa=True),
               base_url=str(ASSETS)).write_pdf()
    resposta = HttpResponse(pdf, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="minuta-{oficio.numero}-{oficio.ano}.pdf"'
    return resposta


# ------------------------------------------------------------------ APIs (combobox/busca)
@require_GET
def buscar_servidores(request: HttpRequest) -> JsonResponse:
    if not policies.pode_buscar_servidores(request.user):
        raise PermissionDenied
    termo = (request.GET.get("q") or "").strip()
    digitos = "".join(c for c in termo if c.isdigit())
    filtro = Q(nome__unaccent__icontains=termo)
    if len(digitos) >= 3:
        filtro |= Q(cpf__contains=digitos) | Q(rg__contains=digitos)
    servidores = (Servidor.objects.filter(ativo=True).filter(filtro)
                  .select_related("cargo", "unidade").order_by("nome")[:15])
    return JsonResponse({"resultados": [
        {"id": str(s.pk), "titulo": s.nome, "meta": f"{s.cargo} • {s.unidade.sigla}"}
        for s in servidores]})

