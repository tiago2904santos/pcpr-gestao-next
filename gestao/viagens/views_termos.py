"""Telas dos termos de autorização (paridade com `viagens_termos` da referência): lista com
abas e busca, cadastro numa tela (com o que vem do ofício à vista), documentos gerados na
hora (PDF por servidor, genérico e da viatura; PDF único; ZIP de DOCX) e o ciclo de vida
(cancelar com motivo, reativar, excluir)."""

from __future__ import annotations

from urllib.parse import urlsplit

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import CharField, Count, DateField, Min, OuterRef, Q, Subquery
from django.db.models.functions import Cast, Coalesce, TruncDate
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.http.response import HttpResponseBase
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from gestao.cadastros.forms import formularios_de_cadastro_rapido
from gestao.cadastros.validacoes import normalizar_placa, somente_digitos

from . import assinados, linha_do_tempo, policies, prestacao, termos, views_assinados
from .forms import FormularioTermo
from .models import EdicaoTermo, Oficio, TermoAutorizacao, Trecho
from .views import POR_PAGINA, _migalhas
from .views_editor import (
    moldura_da_folha,
    moldura_do_pdf,
    primeiro_erro,
    resposta_de_folha,
)

ABAS = [("", "Todos", "todos"), ("futuros", "Que vão acontecer", "futuros"),
        ("andamento", "Em andamento e realizados", "andamento"),
        ("finalizados", "Finalizados", "finalizados"),
        ("cancelados", "Cancelados", "cancelados")]


def _com_inicio(qs):
    """Anota `inicio_efetivo`: a data do termo ou, herdando, a saída do ofício."""
    saida = (Trecho.objects.filter(oficio=OuterRef("oficio_id")).order_by()
             .values("oficio").annotate(m=Min("saida_em")).values("m"))
    return qs.annotate(inicio_efetivo=Coalesce(
        "data_inicio", TruncDate(Subquery(saida)), output_field=DateField()))


def _filtrar(qs, aba: str):
    hoje = timezone.localdate()
    ativos = qs.filter(situacao=TermoAutorizacao.Situacao.ATIVO)
    prestadas = prestacao.prestadas("termo")  # termo avulso nunca finaliza
    if aba == "finalizados":
        return ativos.filter(prestadas)
    if aba == "futuros":
        return ativos.filter(~prestadas, inicio_efetivo__gt=hoje)
    if aba == "andamento":
        return ativos.filter(~prestadas, inicio_efetivo__lte=hoje)
    if aba == "cancelados":
        return qs.filter(situacao=TermoAutorizacao.Situacao.CANCELADO)
    return qs


def _buscar(qs, termo: str):
    if not termo:
        return qs
    filtro = (Q(destinos__municipio__nome__unaccent__icontains=termo)
              | Q(oficio__trechos__destino__nome__unaccent__icontains=termo)
              | Q(servidores__nome__unaccent__icontains=termo)
              | Q(oficio__viajantes__servidor__nome__unaccent__icontains=termo)
              | Q(viatura__modelo__unaccent__icontains=termo)
              | Q(evento__unaccent__icontains=termo))
    if "/" in termo and all(p.isascii() and p.isdecimal() for p in termo.split("/", 1)):
        numero, ano = termo.split("/", 1)
        filtro |= Q(oficio__numero=int(numero), oficio__ano=int(ano))
    if len(digitos := somente_digitos(termo)) >= 3:
        filtro |= Q(oficio__protocolo__contains=digitos)
    if len(placa := normalizar_placa(termo)) >= 3:
        filtro |= Q(viatura__placa__contains=placa) | Q(oficio__viatura__placa__contains=placa)
    return qs.filter(filtro).distinct()


@require_GET
def lista(request: HttpRequest) -> HttpResponse:
    if not request.user.has_perm("viagens.view_termoautorizacao"):
        raise PermissionDenied
    base = _com_inicio(policies.termos_visiveis(request.user))
    oficio_pk = request.GET.get("oficio") or ""
    oficio = None
    if oficio_pk.isascii() and oficio_pk.isdecimal():
        oficio = policies.oficios_visiveis(request.user).filter(pk=int(oficio_pk)).first()
        base = base.filter(oficio_id=int(oficio_pk))
    aba = request.GET.get("aba") or ""
    if aba not in {chave for chave, _, _ in ABAS}:
        aba = ""
    busca = (request.GET.get("q") or "").strip()
    qs = termos.com_dados(_buscar(_filtrar(base, aba), busca).order_by("-criado_em")).annotate(
        # Vias assinadas: as em vigor (selo "N de M assinados") e se há alguma guardada
        # (com via, o termo não se exclui) — numa consulta só para a página.
        vias_vigentes=Count("vias_assinadas", filter=Q(vias_assinadas__revogada_em__isnull=True),
                            distinct=True),
        vias_total=Count("vias_assinadas", distinct=True))
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    linhas = []
    for t in pagina.object_list:
        ef = termos.efetivo(t)
        linhas.append({"termo": t, "ef": ef, "docs": termos.documentos_do_termo(t, ef),
                       "editavel": policies.pode_editar_termo(request.user, t),
                       "cancelavel": policies.pode_cancelar_termo(request.user, t),
                       "excluivel": policies.pode_excluir_termo(request.user, t)})
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    hoje = timezone.localdate()
    contagens = {"todos": base.count(),
                 **{chave: _filtrar(base, chave).count() for chave, _, _ in ABAS if chave}}
    return render(request, "viagens/termos/lista.html", {
        "page_obj": pagina, "linhas": linhas, "abas": ABAS, "aba": aba, "termo_busca": busca,
        "contagens": contagens, "hoje": hoje,
        "oficio_filtro": oficio_pk if oficio is not None else "", "oficio": oficio,
        "pode_termo_do_oficio": (oficio is not None and policies.pode_criar_termo(request.user)
                                 and oficio.situacao != Oficio.Situacao.CANCELADO),
        "querystring_base": (filtros.urlencode() + "&") if filtros else "",
        "voltar": request.get_full_path(),
        "pode_criar": policies.pode_criar_termo(request.user),
        "migalhas": _migalhas(("Termos de autorização", ""))})


def _termo_visivel(request: HttpRequest, pk: int) -> TermoAutorizacao:
    termo = get_object_or_404(termos.com_dados(TermoAutorizacao.objects.all()), pk=pk)
    if not policies.pode_ver_termo(request.user, termo):
        raise PermissionDenied
    return termo


def _oficios_escolhiveis(request: HttpRequest):
    return policies.oficios_visiveis(request.user).exclude(
        situacao=Oficio.Situacao.CANCELADO)


def _formulario(request: HttpRequest, *args, termo=None, **kwargs) -> FormularioTermo:
    extras = {"oficios": _oficios_escolhiveis(request),
              "fonte_servidores": reverse("cadastros:buscar_servidores"),
              "fonte_municipios": reverse("cadastros:buscar_municipios")}
    if termo is not None and not args and not kwargs.get("initial"):
        return FormularioTermo.de(termo, **extras)
    return FormularioTermo(*args, termo=termo, **extras, **kwargs)


def _tela(request: HttpRequest, form: FormularioTermo, termo=None, status: int = 200):
    oficio = None
    if form.is_bound and form.is_valid():
        oficio = form.cleaned_data.get("oficio")
    elif termo is not None:
        oficio = termo.oficio
    elif (pk := form.initial.get("oficio")):
        oficio = _oficios_escolhiveis(request).filter(pk=pk).first()
    ef = termos.efetivo(termo) if termo is not None else None
    voltar = reverse("viagens:termos")
    if termo is None and oficio is not None:  # veio da janela do ofício: volta para ela
        voltar = f"{reverse('viagens:oficios')}?resumo={oficio.pk}"
    docs = termos.documentos_do_termo(termo, ef) if termo is not None else []
    # Qual documento o visualizador mostra: ?previa=<chave>, senão o primeiro da lista.
    pedida = request.GET.get("previa", "")
    previa = next((d for d in docs if d["chave"] == pedida), docs[0] if docs else None)
    if termo is not None and policies.pode_ver_documento_termo(request.user, termo):
        vias = assinados.vigentes_do(termo)
        for d in docs:  # a via assinada de cada documento (selo e menu na lista)
            d["via"] = views_assinados.cartao(
                request, assinados.Alvo("termo", termo, d["chave"]),
                vias.get(("termo", d["chave"])), titulo=d["titulo"],
                original_url=reverse("viagens:documento_termo", args=[termo.pk, d["chave"],
                                                                        "pdf"]))
    return render(request, "viagens/termos/editar.html", {
        "form": form, "termo": termo, "oficio": oficio, "ef": ef, "voltar": voltar,
        "heranca": termos.heranca_do_oficio(oficio),
        "docs": docs, "previa": previa,
        "historico": (linha_do_tempo.do_termo(termo)
                      if termo is not None and policies.pode_ver_historico_termo(
                          request.user, termo) else []),
        "pode_ver_documento": (termo is not None
                               and policies.pode_ver_documento_termo(request.user, termo)),
        "editavel": termo is None or policies.pode_editar_termo(request.user, termo),
        "pode_cancelar": termo is not None and policies.pode_cancelar_termo(request.user, termo),
        "pode_excluir": termo is not None and policies.pode_excluir_termo(request.user, termo),
        # Cadastrar viatura sem sair da folha: o mesmo diálogo da tela de Cadastros e da
        # folha do ofício (componentes/dialogo_viatura.html).
        **formularios_de_cadastro_rapido(),
        "migalhas": _migalhas(("Termos de autorização", reverse("viagens:termos")),
                              (str(termo) if termo else "Novo termo", ""))}, status=status)


def _gravar(request: HttpRequest, form: FormularioTermo, termo=None) -> HttpResponse:
    if form.is_valid():
        try:
            salvo = termos.salvar(request.user, pk=termo.pk if termo else None,
                                  **form.cleaned_data)
        except termos.TermoInvalido as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"{salvo} salvo. Os documentos estão logo abaixo.")
            return redirect(reverse("viagens:editar_termo", args=[salvo.pk]) + "#t-documentos")
    return _tela(request, form, termo, status=422)


@require_http_methods(["GET", "POST"])
def novo(request: HttpRequest) -> HttpResponse:
    policies.exigir(policies.pode_criar_termo(request.user),
                    "Você não pode criar termos de autorização.")
    if request.method == "POST" and request.POST.get("acao") == "criar":
        # "Novo termo" (lista, viagem): cria o rascunho na hora e abre a folha — os
        # documentos já aparecem e vão se refazendo enquanto a pessoa preenche.
        try:
            termo = termos.salvar(request.user)
        except termos.TermoInvalido as exc:
            messages.error(request, str(exc))
            return redirect("viagens:termos")
        return redirect("viagens:editar_termo", termo.pk)
    if request.method == "POST":
        return _gravar(request, _formulario(request, request.POST))
    inicial = {}
    oficio_pk = request.GET.get("oficio") or ""
    # "Termo de autorização" a partir do ofício: o termo já nasce ligado a ele.
    oficio = (_oficios_escolhiveis(request).filter(pk=int(oficio_pk)).first()
              if oficio_pk.isascii() and oficio_pk.isdecimal() else None)
    if oficio is not None:
        # Já preenchido com o que vem do ofício (destinos, período, equipe, viatura).
        inicial = {"oficio": oficio.pk, **FormularioTermo.campos_do_oficio(oficio)}
    return _tela(request, _formulario(request, initial=inicial))


@require_POST
def criar_do_oficio(request: HttpRequest, oficio_pk: int) -> HttpResponse:
    """"Novo termo de autorização" na janela do ofício: cria ligado a ele, herdando tudo, e
    abre direto nos documentos. Se faltar algo (ofício sem roteiro), abre o cadastro."""
    oficio = get_object_or_404(_oficios_escolhiveis(request), pk=oficio_pk)
    try:
        termo = termos.salvar(request.user, oficio=oficio)
    except termos.TermoInvalido as exc:
        messages.warning(request, f"{exc} Complete o termo abaixo.")
        return redirect(f"{reverse('viagens:novo_termo')}?oficio={oficio.pk}")
    messages.success(request, f"{termo} criado a partir do Ofício {oficio.numero_formatado}.")
    return redirect(reverse("viagens:editar_termo", args=[termo.pk]) + "#t-documentos")


@require_http_methods(["GET", "POST"])
def editar(request: HttpRequest, pk: int) -> HttpResponse:
    termo = _termo_visivel(request, pk)
    if request.method == "POST":
        policies.exigir(policies.pode_editar_termo(request.user, termo),
                        "Este termo não pode ser alterado.")
        return _gravar(request, _formulario(request, request.POST, termo=termo), termo)
    return _tela(request, _formulario(request, termo=termo), termo)


@require_POST
def autosave(request: HttpRequest, pk: int) -> JsonResponse:
    """Grava o termo a cada pausa na digitação (componentes/autosave.js), quando o
    formulário inteiro é válido; senão diz o que impede, no status da barra."""
    termo = _termo_visivel(request, pk)
    if not policies.pode_editar_termo(request.user, termo):
        return JsonResponse({"salvo": False, "mensagem": "Este termo não pode ser alterado."})
    form = _formulario(request, request.POST, termo=termo)
    if not form.is_valid():
        return JsonResponse({"salvo": False, "mensagem": primeiro_erro(form)})
    oficio_antes = termo.oficio_id
    try:
        salvo = termos.salvar(request.user, pk=termo.pk, **form.cleaned_data)
    except termos.TermoInvalido as exc:
        return JsonResponse({"salvo": False, "mensagem": f"Não salvo: {exc}"})
    except PermissionDenied:  # cancelado por outra pessoa no meio do caminho
        return JsonResponse({"salvo": False, "mensagem": "Este termo não pode mais ser alterado."})
    except TermoAutorizacao.DoesNotExist:
        return JsonResponse({"salvo": False, "mensagem": "Este termo foi excluído."})
    # Trocar o ofício muda o que vem dele sob cada campo: a tela é redesenhada.
    return JsonResponse({"salvo": True, "recarregar": salvo.oficio_id != oficio_antes,
                         "em": timezone.localtime(salvo.atualizado_em).strftime("%H:%M"),
                         "campos": {"versao": termos.versao_de(salvo)}})


@require_GET
@moldura_da_folha
def folha(request: HttpRequest, pk: int, chave: str) -> HttpResponse:
    """Um documento do termo em HTML, para o visualizador da tela."""
    termo = _termo_visivel(request, pk)
    policies.exigir(policies.pode_ver_documento_termo(request.user, termo),
                    "Reative o termo para ver os documentos.")
    # ?versao=N mostra uma versão do texto (o histórico do editor); 0 é o modelo.
    regioes, marcados = None, set()
    pedido = request.GET.get("versao") or ""
    if pedido.isascii() and pedido.isdigit():
        numero = int(pedido)
        edicao = (EdicaoTermo.objects.filter(termo=termo, chave=chave, numero=numero).first()
                  if numero else None)
        if numero and edicao is None:
            raise Http404
        regioes = dict(edicao.regioes) if edicao else {}
        marcados = {b["chave"] for b in edicao.blocos_alterados} if edicao else set()
    else:
        vigente = termos.edicao_vigente(termo, chave)
        marcados = {b["chave"] for b in vigente.blocos_alterados} if vigente else set()
    return resposta_de_folha(request, lambda nonce: termos.html_do_documento(
        termos.dados_do_documento(termo, chave), folha=True, nonce=nonce, regioes=regioes,
        blocos_alterados=marcados), erros=(termos.TermoInvalido,))


@require_GET
@moldura_do_pdf
def documento(request: HttpRequest, pk: int, chave: str, formato: str) -> HttpResponseBase:
    """Um documento do termo, gerado na hora: PDF (abre no navegador) ou DOCX (baixa)."""
    termo = _termo_visivel(request, pk)
    policies.exigir(policies.pode_editar_termo(request.user, termo),
                    "Reative o termo para gerar documentos.")
    if formato not in ("pdf", "docx"):
        raise Http404
    try:
        dados = termos.dados_do_documento(termo, chave)
    except termos.TermoInvalido as exc:
        if request.GET.get("previa") == "1":  # dentro do visualizador: o aviso na folha
            return resposta_de_folha(request, lambda nonce: "", erros=(termos.TermoInvalido,),
                                     erro=exc)
        messages.error(request, str(exc))
        return redirect("viagens:editar_termo", termo.pk)
    nome = termos.nome_do_arquivo(termo, chave, formato)
    if formato == "pdf":
        resposta = HttpResponse(termos.pdf_do_documento(dados), content_type="application/pdf")
        resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    else:
        resposta = HttpResponse(termos.docx_do_documento(dados), content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
        resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    resposta["Cache-Control"] = "no-store"  # dados pessoais da equipe (RG, CPF, telefone)
    return resposta


@require_GET
def visualizar(request: HttpRequest, pk: int) -> HttpResponse:
    """O PDF completo do termo numa página da aplicação, na mesma aba (com Voltar)."""
    termo = _termo_visivel(request, pk)
    policies.exigir(policies.pode_editar_termo(request.user, termo),
                    "Reative o termo para ver os documentos.")
    # Vindo de "Gerar" sem aba nova (?voltar=lista), o Voltar leva à lista de termos.
    para_lista = request.GET.get("voltar") == "lista"
    docs = termos.documentos_do_termo(termo)
    return render(request, "viagens/visualizar.html", {
        "placa_rotulo": "Termo", "placa_numero": f"#{termo.pk}", "titulo_doc": str(termo),
        "descricao": f"{len(docs)} documento{'s' if len(docs) != 1 else ''}, na ordem da "
                     "lista do termo — como saem no PDF.",
        "folhas": [{"titulo": d["titulo"], "descricao": d["descricao"],
                    "url": reverse("viagens:folha_termo", args=[termo.pk, d["chave"]])}
                   for d in docs],
        "pdf_url": reverse("viagens:todos_termo", args=[termo.pk, "pdf"]),
        "pdf_nome": f"termo-{termo.pk}-todos.pdf",
        "separados": {"url": reverse("viagens:baixar_termo", args=[termo.pk]),
                      "itens": [d["chave"] for d in docs],
                      "voltar": request.get_full_path()},
        "baixar_url": reverse("viagens:baixar_termo", args=[termo.pk]),
        "voltar_url": reverse("viagens:termos") if para_lista
        else reverse("viagens:editar_termo", args=[termo.pk]),
        "voltar_rotulo": "Voltar à lista" if para_lista else "Voltar ao termo",
        "migalhas": _migalhas(("Termos de autorização", reverse("viagens:termos")),
                              (str(termo), reverse("viagens:editar_termo", args=[termo.pk])),
                              ("Visualizar", ""))})


@require_GET
@moldura_do_pdf
def todos(request: HttpRequest, pk: int, formato: str) -> HttpResponse:
    """Todos os documentos do termo: um PDF só ou um ZIP de DOCX (referência)."""
    termo = _termo_visivel(request, pk)
    policies.exigir(policies.pode_editar_termo(request.user, termo),
                    "Reative o termo para gerar documentos.")
    try:
        if formato == "pdf":
            resposta = HttpResponse(termos.pdf_unico(termo), content_type="application/pdf")
            resposta["Content-Disposition"] = f'inline; filename="termo-{termo.pk}-todos.pdf"'
        elif formato == "zip":
            resposta = HttpResponse(termos.zip_de_docx(termo), content_type="application/zip")
            resposta["Content-Disposition"] = (f'attachment; filename="termo-{termo.pk}-'
                                               'docx.zip"')
        else:
            raise Http404
        resposta["Cache-Control"] = "no-store"
    except termos.TermoInvalido as exc:
        messages.error(request, str(exc))
        return redirect("viagens:editar_termo", termo.pk)
    return resposta


def _voltar(request: HttpRequest, padrao: str, termo_pk: int | None = None) -> str:
    """A lista como estava, ou o próprio termo (quando a ação veio dele)."""
    voltar = request.POST.get("voltar") or ""
    caminhos = {reverse("viagens:termos")}
    if termo_pk is not None:
        caminhos.add(reverse("viagens:editar_termo", args=[termo_pk]))
    if (urlsplit(voltar).path in caminhos
            and url_has_allowed_host_and_scheme(voltar, allowed_hosts={request.get_host()})):
        return voltar
    return padrao


def _acao(request: HttpRequest, pk: int, executar, padrao: str | None = None):
    termo = _termo_visivel(request, pk)
    try:
        mensagem = executar(termo)
    except (termos.TermoInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, mensagem)
    return redirect(_voltar(request, padrao or reverse("viagens:termos"), termo_pk=pk))


@require_POST
def cancelar(request: HttpRequest, pk: int) -> HttpResponse:
    def executar(t):
        termos.cancelar(request.user, t.pk, request.POST.get("motivo", ""))
        return f"{t} cancelado. O histórico foi mantido."
    return _acao(request, pk, executar)


@require_POST
def reativar(request: HttpRequest, pk: int) -> HttpResponse:
    return _acao(request, pk, lambda t: f"{termos.reativar(request.user, t.pk)} reativado.")


@require_POST
def excluir(request: HttpRequest, pk: int) -> HttpResponse:
    return _acao(request, pk, lambda t: f"{termos.excluir(request.user, t.pk)} excluído.")


@require_GET
@require_GET
def dados_do_oficio(request: HttpRequest, oficio_pk: int) -> JsonResponse:
    """O que um termo copia do ofício ao ser vinculado a ele: destinos, período, equipe e
    viatura — para a folha preencher os campos na hora, como "usar um roteiro" no ofício.

    Só ofícios que o termo pode usar (`_oficios_escolhiveis`: visíveis e não cancelados).
    """
    if not request.user.has_perm("viagens.view_oficio"):
        raise PermissionDenied
    oficio = get_object_or_404(
        _oficios_escolhiveis(request).select_related("viatura", "sede"), pk=oficio_pk)
    destinos, inicio, fim = termos._do_oficio(oficio)
    servidores = [v.servidor for v in oficio.viajantes.select_related(
        "servidor__cargo", "servidor__unidade").order_by("ordem", "id")]
    return JsonResponse({
        "destinos": [{"cidade": f"{m.nome}/{m.uf}", "uf": m.uf} for m in destinos],
        "inicio": f"{inicio:%d/%m/%Y}" if inicio else "",
        "fim": f"{fim:%d/%m/%Y}" if fim and fim != inicio else "",
        "servidores": [{"id": str(s.pk), "titulo": s.nome, "meta": s.descricao}
                       for s in servidores],
        "viatura": str(oficio.viatura_id) if oficio.viatura_id else "",
    })


def buscar_oficios(request: HttpRequest) -> JsonResponse:
    """Ofícios que um termo pode usar (visíveis, não cancelados), para o seletor do termo."""
    if not request.user.has_perm("viagens.view_oficio"):
        raise PermissionDenied
    busca = (request.GET.get("q") or "").strip()
    qs = _oficios_escolhiveis(request).annotate(numero_texto=Cast("numero", CharField()))
    filtro = Q(trechos__destino__nome__unaccent__icontains=busca) | Q(
        viajantes__servidor__nome__unaccent__icontains=busca)
    if (digitos := somente_digitos(busca)):
        if "/" in busca and all(p.isascii() and p.isdecimal() for p in busca.split("/", 1)):
            numero, ano = busca.split("/", 1)
            filtro |= Q(numero=int(numero), ano=int(ano))
        else:
            filtro |= Q(numero_texto__startswith=digitos[:6]) | Q(protocolo__contains=digitos)
    ofs = (qs.filter(filtro).distinct().select_related("sede")
           .prefetch_related("trechos__destino").order_by("-ano", "-numero")[:30])
    resultados = []
    for o in ofs:
        destinos = list(dict.fromkeys(f"{t.destino.nome}/{t.destino.uf}" for t in o.trechos.all()
                                      if t.destino_id != o.sede_id))
        resultados.append({"id": str(o.pk), "titulo": f"Ofício {o.numero_formatado}",
                           "meta": " · ".join(p for p in (", ".join(destinos),
                                                          o.get_situacao_display()) if p)})
    return JsonResponse({"resultados": resultados})
