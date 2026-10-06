"""Telas das solicitações de coffee break (CB2): lista com a situação financeira, filtros e
CSV; a folha da solicitação (etapa 1: o evento e a ordem de serviço) com o lote que o
município recebe; cancelar, reativar, excluir, duplicar; e a lista de lotes com o saldo."""

from __future__ import annotations

import csv
import re
from datetime import date, datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Max
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from gestao.cadastros.forms import resolver_municipio

from . import (
    conjunto,
    documentos,
    financeiro,
    ganchos,
    pdfs,
    pedidos,
    policies,
    queries,
    vias,
    virada,
)
from . import dominio_painel as regras_painel
from . import dominio_pedido as regras
from .forms_pedido import (
    FORM_FINANCEIRO,
    FORM_ID,
    MSG_TRAVADOS,
    FormularioAndamento,
    FormularioFinanceiro,
    FormularioSolicitacao,
)
from .models import Fornecedor, Lote, Solicitacao

POR_PAGINA = 25
# A trilha na ordem do fluxo, com rótulos curtos (cabem na largura).
ABAS = (("aguardando_nota", "Aguardando nota"), ("aguardando_protocolo", "Aguardando protocolo"),
        ("aguardando_atesto", "Aguardando atesto"), ("aguardando_ob", "Aguardando OB"),
        ("aguardando_envio", "Aguardando envio"), ("concluida", "Concluídas"),
        ("cancelada", "Canceladas"))
COLUNAS = ("Nº", "Lote", "Fornecedor", "Data da solicitação", "Evento", "Período",
           "Local de entrega", "Endereço", "Bairro", "CEP", "Quantidade", "Quantidade faturada",
           "Valor unitário", "Valor", "Nota fiscal", "Protocolo", "Atesto GAF", "Ordem bancária",
           "Envio à empresa", "Situação", "Criado por")


def _exigir(request: HttpRequest) -> None:
    if not policies.pode_acessar(request.user):
        raise PermissionDenied


def _migalhas(*fim: tuple[str, str]) -> list[tuple[str, str]]:
    return [("Início", reverse("painel:inicio")),
            ("Coffee Break", reverse("coffee:painel")), *fim]


def _data(texto: str | None) -> date | None:
    try:
        return datetime.strptime((texto or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        try:
            return date.fromisoformat((texto or "").strip())
        except ValueError:
            return None


def _inteiro(texto: str | None) -> int | None:
    texto = (texto or "").strip()
    return int(texto) if texto.isdecimal() and len(texto) <= 9 else None


def _filtros(get) -> dict:
    return {"q": " ".join((get.get("q") or "").split())[:100], "lote": _inteiro(get.get("lote")),
            "fornecedor": _inteiro(get.get("fornecedor")), "de": _data(get.get("de")),
            "ate": _data(get.get("ate")), "situacao": get.get("situacao") or "",
            "pendentes": get.get("pendentes") == "1"}


def _base():
    return Solicitacao.objects.select_related("lote__contrato__fornecedor", "municipio",
                                              "criado_por")


def _linha(s: Solicitacao, hoje: date) -> dict:
    if s.data_evento is None:
        tempo = None
    elif s.data_evento < hoje:
        tempo = ("Realizado", "sucesso")
    elif s.data_evento == hoje:
        tempo = ("Acontecendo", "info")
    else:
        tempo = ("Previsto", "neutro")
    fatos = [("calendar", "Evento", f"{s.data_evento:%d/%m/%Y}" if s.data_evento
              else "Sem data do evento", s.data_evento is None),
             ("users", "Quantidade", f"{s.quantidade} pessoas", False),
             ("layers", "Lote", f"{s.lote} · {s.lote.contrato.fornecedor}", False),
             ("map-pin", "Município", s.municipio.nome, False)]
    if s.nota_fiscal:
        fatos.append(("receipt", "Nota fiscal", f"NF {s.nota_fiscal}", False))
    fatos.append(("clock", "Solicitada", f"Solicitada em {s.data_solicitacao:%d/%m/%Y}", False))
    return {"s": s, "tempo": tempo if not s.cancelada else None, "fatos": fatos,
            "parada": _parada(s, hoje)}


def _parada(s: Solicitacao, hoje: date) -> str:
    """"Parada há N dias" (≥ 7) só quando a OS depende da equipe (está em "O que fazer
    hoje"); precisa do último histórico anotado (`ultimo`)."""
    if not hasattr(s, "ultimo") or s.cancelada or s.concluida:
        return ""
    chave = regras_painel.grupo_de(
        cancelada=False, concluida=False, data_evento=s.data_evento, nota=bool(s.nota_fiscal),
        oficio=bool(s.numero_oficio), protocolo=bool(s.protocolo_pagamento),
        ob=bool(s.ordem_bancaria_em), hoje=hoje)
    if chave is None or chave == "entregas":
        return ""
    dias = regras_painel.dias_parada((s.ultimo or s.criado_em).date(), s.data_evento, hoje)
    return regras_painel.texto_parada(dias) if dias >= regras_painel.DIAS_PARADA else ""


@require_GET
def lista(request: HttpRequest) -> HttpResponse:
    _exigir(request)
    hoje = timezone.localdate()
    f = _filtros(request.GET)
    ativos = sum(bool(f[k]) for k in ("lote", "fornecedor", "de", "ate"))
    sem_situacao = queries.filtrar(_base(), **{**f, "situacao": "", "pendentes": False})
    contagens = queries.contagens_por_situacao(sem_situacao)
    qs = (queries.filtrar(_base(), **f).annotate(ultimo=Max("movimentos__em"))
          .order_by("-data_solicitacao", "-pk"))
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    base = urlencode([(k, v) for k, vs in request.GET.lists() for v in vs if k != "pagina" and v])
    sem_sit = urlencode([(k, v) for k, vs in request.GET.lists() for v in vs
                         if k not in ("pagina", "situacao", "pendentes") and v])
    return render(request, "coffee/lista.html", {
        "page_obj": pagina, "linhas": [_linha(s, hoje) for s in pagina.object_list],
        "f": f, "ativos": ativos, "querystring_base": f"{base}&" if base else "",
        "qs_sem_situacao": sem_sit,
        "situacoes": [(c, r, contagens[c]) for c, r in ABAS],
        "total": contagens["total"],
        "lotes": Lote.objects.select_related("contrato").order_by("-exercicio", "numero"),
        "fornecedores": Fornecedor.objects.order_by("razao_social"),
        "url_exportar": reverse("coffee:exportar") + (f"?{base}" if base else ""),
        "migalhas": _migalhas(("Solicitações", "")),
    })


def _celula(valor):
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{valor}"
    return valor


def _d(v) -> str:
    return f"{v:%d/%m/%Y}" if v else ""


@require_GET
def exportar(request: HttpRequest) -> HttpResponse:
    """O recorte atual em CSV (";", BOM, decimais com vírgula), 21 colunas da referência."""
    _exigir(request)
    hoje = timezone.localdate()
    qs = queries.filtrar(_base(), **_filtros(request.GET)).order_by("-data_solicitacao", "-pk")
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="coffee-break-{hoje:%Y-%m-%d}.csv"'
    resposta.write("﻿")
    escritor = csv.writer(resposta, delimiter=";", lineterminator="\r\n")
    escritor.writerow(COLUNAS)
    for s in qs.iterator(chunk_size=500):
        unit = f"{s.valor_unitario:.4f}".replace(".", ",") if s.valor_unitario else ""
        valor = f"{s.valor:.2f}".replace(".", ",") if s.valor is not None else ""
        escritor.writerow([_celula(v) for v in (
            s.numero, str(s.lote), s.lote.contrato.fornecedor.razao_social,
            _d(s.data_solicitacao), s.descricao, _d(s.data_evento), s.local_entrega,
            s.endereco, s.bairro, s.cep, s.quantidade, s.quantidade_faturada or "", unit, valor,
            s.nota_fiscal, s.protocolo_pagamento, _d(s.atesto_em), _d(s.ordem_bancaria_em),
            _d(s.envio_empresa_em), s.situacao_rotulo, s.criado_por.nome)])
    return resposta


def _historico(s: Solicitacao) -> list:
    return list(s.movimentos.select_related("usuario")[:50])


def _contexto(request: HttpRequest, form: FormularioSolicitacao, s: Solicitacao | None,
              duplicada: Solicitacao | None = None,
              form_fin: FormularioFinanceiro | None = None) -> dict:
    hoje = timezone.localdate()
    ctx: dict = {"form": form, "s": s, "form_id": FORM_ID, "duplicada": duplicada, "origem": None,
                 "proximo_numero": queries.proximo_numero(hoje.year),
                 "msg_travados": MSG_TRAVADOS if form.travado else "",
                 "numero_ano": f"/ {(s.data_solicitacao if s else hoje).year}"}
    if s is not None:
        sal = queries.saldo(s.lote)
        marco = regras.proximo_marco(s.valores_dos_marcos, s.cancelada)
        admin = policies.pode_gerir_cadastros(request.user)
        ctx.update({
            "form_fin": form_fin or FormularioFinanceiro(solicitacao=s),
            "form_financeiro_id": FORM_FINANCEIRO,
            "etapas": regras.etapas(s.valores_dos_marcos, s.cancelada),
            "proximo_marco": marco if not s.bloqueada else None,
            "proximo_oficio": queries.proximo_oficio(timezone.localdate().year),
            "pode_reabrir": admin and s.concluida and not s.em_correcao and not s.cancelada,
            "pode_encerrar": admin and s.em_correcao,
            "documentos": [
                {"tipo": t, "titulo": documentos.TIPOS[t].titulo,
                 "faltas": documentos.pendencias(t, s),
                 "assinada": vias.assinada_vigente(s, t) if t in documentos.ASSINAVEIS
                 else None,
                 "assinavel": t in documentos.ASSINAVEIS,
                 "n_vias": s.vias.filter(tipo=t).count()} for t in documentos.TIPOS],
            "avisos_nota": pdfs.avisos_da_nota(s),
            "pdfs": (("nota", "Nota fiscal", s.nota_pdf,
                      (("Número", s.nota_fiscal), ("Valor", regras.moeda(s.nota_valor)
                                                   if s.nota_valor is not None else ""),
                       ("Emissão", f"{s.nota_emissao:%d/%m/%Y}" if s.nota_emissao else ""),
                       ("CNPJ do emitente", s.nota_cnpj))),
                     ("ob", "Ordem bancária", s.ob_pdf,
                      (("Número", s.ob_numero), ("Valor", regras.moeda(s.ob_valor)
                                                 if s.ob_valor is not None else "")))),
            "aviso_ob": pdfs.aviso_da_ob(s),
            "grupo": conjunto.membros(s) if conjunto.em_grupo(s) else [],
            "principal": conjunto.principal_de(s),
            "candidatas": (list(conjunto.candidatas(s)) if not s.bloqueada
                           and not conjunto.principal_de(s).protocolo_pagamento else []),
            "saldo": sal, "fim_vigencia": s.lote.contrato.fim_efetivo(),
            "historico": _historico(s), "linha": _linha(s, hoje),
            "aviso_antecedencia": regras.aviso_antecedencia(
                s.data_evento, hoje, s.lote.contrato.antecedencia_minima_dias,
                s.lote.contrato.numero) if not s.bloqueada else "",
            "migalhas": _migalhas(("Solicitações", reverse("coffee:solicitacoes")), (str(s), "")),
        })
        from .views_painel import contexto_da_folha  # o painel importa daqui

        ctx.update(contexto_da_folha(request, s))
        ctx["origem"] = ganchos.cartao(request.user, s)
    else:
        ctx["migalhas"] = _migalhas(("Solicitações", reverse("coffee:solicitacoes")),
                                    ("Nova solicitação", ""))
    return ctx


def _gravar(request: HttpRequest, form: FormularioSolicitacao, s: Solicitacao | None,
            duplicada: Solicitacao | None):
    origem = None
    if s is None and (achada := ganchos.resolver(request.user, form.cleaned_data.get("origem"))):
        origem = (achada[0].chave, achada[1], achada[2].rotulo)  # revalidada no POST
    try:
        r = pedidos.salvar(request.user, form.cleaned_data, s,
                           retroativo=form.cleaned_data.get("retroativo", False),
                           justificativa=form.cleaned_data.get("justificativa", ""),
                           duplicada_de=duplicada,
                           versao=form.cleaned_data.get("versao") if s is not None else None,
                           origem=origem)
    except pedidos.PedidoInvalido as exc:
        form.add_error(exc.campo if exc.campo in form.fields else None, str(exc))
        return None
    if r.aviso:
        messages.warning(request, r.aviso)
    return r.solicitacao


@require_http_methods(["GET", "POST"])
def nova(request: HttpRequest) -> HttpResponse:
    _exigir(request)
    duplicada = None
    if (pk := _inteiro(request.GET.get("duplicar") or request.POST.get("duplicada_de"))):
        duplicada = get_object_or_404(Solicitacao, pk=pk)
    if request.method == "POST":
        form = FormularioSolicitacao(request.POST)
        if form.is_valid() and (s := _gravar(request, form, None, duplicada)) is not None:
            messages.success(request, f"Solicitação {s.numero} registrada no {s.lote} "
                                      f"({s.lote.contrato.fornecedor}). A ordem de serviço já "
                                      "pode ser gerada.")
            return redirect("coffee:solicitacoes")
        messages.error(request, "Corrija os campos destacados para continuar.")
        return render(request, "coffee/folha.html", _contexto(request, form, None, duplicada),
                      status=422)
    inicial: dict = {}
    if duplicada is not None:
        inicial = {**pedidos.dados_para_duplicar(duplicada), "duplicada_de": duplicada.pk}
    if (achada := ganchos.resolver(request.user, request.GET.get("origem"))):
        inicial.update({**achada[2].iniciais, "origem": f"{achada[0].chave}:{achada[1]}"})
        messages.info(request, f"Preenchida a partir de {achada[2].rotulo}: confira e "
                               "complete antes de registrar.")
    if (inicio := _data(request.GET.get("inicio"))):
        inicial["data_evento"] = inicio
    return render(request, "coffee/folha.html",
                  _contexto(request, FormularioSolicitacao(initial=inicial), None, duplicada))


@require_http_methods(["GET", "POST"])
def solicitacao(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(request)
    s = get_object_or_404(_base(), pk=pk)
    if request.method == "POST":
        if s.bloqueada:
            messages.error(request, regras.MSG_BLOQUEADA)
            return redirect("coffee:solicitacao", pk=pk)
        form = FormularioSolicitacao(request.POST, solicitacao=s)
        if form.is_valid() and _gravar(request, form, s, None) is not None:
            messages.success(request, "Solicitação de coffee break atualizada.")
            return redirect("coffee:solicitacoes")
        messages.error(request, "Corrija os campos destacados para continuar.")
        return render(request, "coffee/folha.html", _contexto(request, form, s), status=422)
    return render(request, "coffee/folha.html",
                  _contexto(request, FormularioSolicitacao(solicitacao=s), s))


@require_GET
def lote_do_municipio(request: HttpRequest) -> HttpResponse:
    """Trecho da folha: o lote que o município recebe (lote, fornecedor, contrato, saldo,
    empenho, vigência) — ou por que nenhum atende."""
    _exigir(request)
    info, erro = None, ""
    texto = (request.GET.get("municipio") or "").strip()
    data = _data(request.GET.get("data_evento")) or _data(
        request.GET.get("data_solicitacao")) or timezone.localdate()
    if texto:
        try:
            municipio = resolver_municipio(texto)
        except ValidationError as exc:
            erro = " ".join(exc.messages)
        else:
            info = queries.lote_para(municipio, data) if municipio.uf == "PR" else None
            if info is None and not erro:
                erro = (regras.MSG_SEM_LOTE.format(municipio=f"{municipio.nome}/{municipio.uf}")
                        if municipio.uf == "PR" else "Escolha um município do Paraná.")
    return render(request, "coffee/_lote.html", {
        "erro": erro, "lote": info.lote if info else None, "sal": info.saldo if info else None,
        "fim": info.fim if info else None, "proximidade": info.proximidade if info else "",
        "vencido": info.vencido if info else False})


def _acao(request: HttpRequest, pk: int, fazer, sucesso: str) -> HttpResponse:
    _exigir(request)
    get_object_or_404(Solicitacao, pk=pk)
    try:
        resultado = fazer()
    except pedidos.PedidoInvalido as exc:
        messages.error(request, str(exc))
        return redirect("coffee:solicitacao", pk=pk)
    messages.success(request, sucesso.format(r=resultado))
    return redirect("coffee:solicitacoes" if isinstance(resultado, str)
                    else reverse("coffee:solicitacao", args=[pk]))


@require_POST
def salvar_financeiro(request: HttpRequest, pk: int) -> HttpResponse:
    """Etapas 2 e 3: nota fiscal, ofício, protocolo e pagamento."""
    _exigir(request)
    s = get_object_or_404(_base(), pk=pk)
    if s.bloqueada:
        messages.error(request, regras.MSG_BLOQUEADA)
        return redirect("coffee:solicitacao", pk=pk)
    form_fin = FormularioFinanceiro(request.POST, solicitacao=s)
    if form_fin.is_valid():
        try:
            financeiro.salvar_financeiro(request.user, pk, form_fin.cleaned_data,
                                         versao=form_fin.cleaned_data.get("versao") or "")
        except pedidos.PedidoInvalido as exc:
            form_fin.add_error(exc.campo if exc.campo in form_fin.fields else None, str(exc))
        else:
            messages.success(request, "Nota, ofício e pagamento salvos.")
            return redirect(reverse("coffee:solicitacao", args=[pk]) + "#pagamento")
    messages.error(request, "Corrija os campos destacados para continuar.")
    return render(request, "coffee/folha.html",
                  _contexto(request, FormularioSolicitacao(solicitacao=s), s, form_fin=form_fin),
                  status=422)


@require_GET
def documento(request: HttpRequest, pk: int, tipo: str) -> HttpResponse:
    """O documento em PDF (visualizar; ?baixar=1 baixa) ou a prévia em tela (?formato=html).
    Com pendência, volta à folha dizendo o que falta."""
    from django.http import Http404
    from django.middleware.csp import get_nonce

    _exigir(request)
    if tipo not in documentos.TIPOS:
        raise Http404
    s = get_object_or_404(_base(), pk=pk)
    if request.GET.get("formato") == "html":
        faltas = documentos.pendencias(tipo, s)
        if faltas:
            messages.error(request, " ".join(faltas))
            return redirect(reverse("coffee:solicitacao", args=[pk]) + "#documentos")
        nonce = str(get_nonce(request) or "")
        return HttpResponse(documentos.html(tipo, s, nonce=nonce, tela=True))
    try:
        arq = vias.obter(request.user, s, tipo)
    except pedidos.PedidoInvalido as exc:
        messages.error(request, str(exc))
        return redirect(reverse("coffee:solicitacao", args=[pk]) + "#documentos")
    except RuntimeError as exc:  # sem o motor de PDF
        messages.error(request, str(exc))
        return redirect(reverse("coffee:solicitacao", args=[pk]) + "#documentos")
    resposta = HttpResponse(arq.conteudo, content_type="application/pdf")
    modo = "attachment" if request.GET.get("baixar") == "1" else "inline"
    from django.utils.http import content_disposition_header
    resposta["Content-Disposition"] = (content_disposition_header(modo == "attachment", arq.nome)
                                       or modo)
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Cache-Control"] = "private, no-store"
    return resposta


def _acao_pdf(request: HttpRequest, pk: int, fazer) -> HttpResponse:
    _exigir(request)
    get_object_or_404(Solicitacao, pk=pk)
    try:
        r = fazer()
    except pedidos.PedidoInvalido as exc:
        messages.error(request, str(exc))
    else:
        (messages.warning if r.aviso else messages.success)(request, r.mensagem)
    return redirect(reverse("coffee:solicitacao", args=[pk]) + "#pdfs")


@require_POST
def anexar_pdf(request: HttpRequest, pk: int, qual: str) -> HttpResponse:
    if qual not in ("nota", "ob"):
        from django.http import Http404
        raise Http404
    fazer = pdfs.anexar_nota if qual == "nota" else pdfs.anexar_ob
    return _acao_pdf(request, pk, lambda: fazer(request.user, pk, request.FILES.get("arquivo")))


@require_POST
def remover_pdf(request: HttpRequest, pk: int, qual: str) -> HttpResponse:
    if qual not in ("nota", "ob"):
        from django.http import Http404
        raise Http404
    fazer = pdfs.remover_nota if qual == "nota" else pdfs.remover_ob
    return _acao_pdf(request, pk, lambda: fazer(request.user, pk))


@require_GET
def baixar_pdf(request: HttpRequest, pk: int, qual: str) -> StreamingHttpResponse:
    from django.http import FileResponse, Http404

    _exigir(request)
    s = get_object_or_404(Solicitacao, pk=pk)
    arquivo = s.nota_pdf if qual == "nota" else s.ob_pdf if qual == "ob" else None
    if not arquivo:
        raise Http404
    rotulo = f"NF {s.nota_fiscal}" if qual == "nota" else f"OB {s.ob_numero or s.pk}"
    nome = re.sub(r"[^\w .-]", "-", f"{rotulo} - {s}")[:120]
    resposta = FileResponse(arquivo.open("rb"), as_attachment=True, filename=f"{nome}.pdf",
                            content_type="application/pdf")
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Cache-Control"] = "private, no-store"
    return resposta


@require_POST
def anexar_assinada(request: HttpRequest, pk: int, tipo: str) -> HttpResponse:
    return _acao(request, pk, lambda: vias.anexar_assinada(
        request.user, pk, tipo, request.FILES.get("arquivo")), vias.MSG_ANEXADA)


@require_POST
def remover_assinada(request: HttpRequest, pk: int, tipo: str) -> HttpResponse:
    return _acao(request, pk, lambda: vias.remover_assinada(request.user, pk, tipo),
                 vias.MSG_REMOVIDA)


@require_POST
def pagamento_conjunto(request: HttpRequest, pk: int) -> HttpResponse:
    """Marca as OS do mesmo lote que vão no mesmo ofício e no mesmo protocolo."""
    ids = [int(x) for x in request.POST.getlist("juntas") if x.isdecimal() and len(x) <= 9]
    return _acao(request, pk, lambda: conjunto.definir(request.user, pk, ids),
                 "Pagamento conjunto atualizado.")


@require_POST
def andamento(request: HttpRequest, pk: int) -> HttpResponse:
    """Registra só o próximo marco, com anotação opcional."""
    form = FormularioAndamento(request.POST)
    form.is_valid()
    return _acao(request, pk, lambda: financeiro.registrar_marco(
        request.user, pk, form.cleaned_data.get("valor", ""),
        form.cleaned_data.get("anotacao", "")), "Andamento registrado: {r.situacao_rotulo}.")


@require_POST
def reabrir(request: HttpRequest, pk: int) -> HttpResponse:
    return _acao(request, pk, lambda: financeiro.reabrir_correcao(
        request.user, pk, request.POST.get("motivo") or ""),
        "Solicitação reaberta para correção. O que mudar fica no histórico.")


@require_POST
def encerrar_correcao(request: HttpRequest, pk: int) -> HttpResponse:
    return _acao(request, pk, lambda: financeiro.encerrar_correcao(request.user, pk),
                 "Correção encerrada: a solicitação voltou a ficar só para consulta.")


@require_POST
def cancelar(request: HttpRequest, pk: int) -> HttpResponse:
    return _acao(request, pk, lambda: pedidos.cancelar(request.user, pk,
                                                       request.POST.get("motivo") or ""),
                 "Solicitação cancelada — a quantidade voltou ao saldo do lote.")


@require_POST
def reativar(request: HttpRequest, pk: int) -> HttpResponse:
    return _acao(request, pk, lambda: pedidos.reativar(request.user, pk),
                 "Solicitação reativada e saldo consumido.")


@require_POST
def excluir(request: HttpRequest, pk: int) -> HttpResponse:
    return _acao(request, pk, lambda: pedidos.excluir(request.user, pk),
                 "Solicitação {r} excluída — a quantidade voltou ao saldo do lote.")


@require_GET
def lotes(request: HttpRequest) -> HttpResponse:
    """Lotes com o saldo: "R de T unidades" e o selo de consumo (verde < 70%, âmbar ≥ 70%,
    vermelho ≥ 90%)."""
    _exigir(request)
    situacao = request.GET.get("situacao") or "ativos"
    qs = (Lote.objects.select_related("contrato__fornecedor").prefetch_related(
        "municipios", "contrato__aditivos").order_by("-exercicio", "numero", "pk"))
    if situacao == "ativos":
        qs = qs.filter(ativo=True)
    elif situacao == "inativos":
        qs = qs.filter(ativo=False)
    lista_lotes = list(qs)
    sal = queries.saldos(lista_lotes)
    hoje = timezone.localdate()
    linhas = []
    for lote in lista_lotes:
        fim = lote.contrato.fim_efetivo()
        linhas.append({"lote": lote, "saldo": sal[lote.pk], "fim": fim,
                       "vencido": bool(fim and fim < hoje)})
    origem = (virada.exercicio_de_origem()
              if policies.pode_gerir_cadastros(request.user, "lotes") else None)
    proximo = origem + 1 if origem else None
    return render(request, "coffee/lotes.html", {
        "linhas": linhas,
        "situacao": situacao, "pode_gerir": policies.pode_gerir_cadastros(request.user),
        "proximo_exercicio": proximo,
        "situacoes": (("ativos", "Vigentes"), ("inativos", "Encerrados"), ("todos", "Todos")),
        "migalhas": _migalhas(("Lotes", "")),
    })


# ---------------------------------------------------------------- certidões (CB5a)
@require_GET
def certidoes(request: HttpRequest) -> HttpResponse:
    """Quadro das certidões por fornecedor com lote ativo; ?anexar=<fornecedor>:<tipo> abre a
    janela do anexo já com o fornecedor e o tipo."""
    from . import certidoes as certs
    from .dominio_certidoes import ROTULOS

    _exigir(request)
    hoje = timezone.localdate()
    fornecedores = list(certs.fornecedores_com_lote_ativo())
    anexar_f, anexar_t = None, ""
    fid, _, tipo = (request.GET.get("anexar") or "").partition(":")
    if fid.isdecimal() and tipo in ROTULOS:
        anexar_f = next((f for f in fornecedores if f.pk == int(fid)), None)
        anexar_t = tipo if anexar_f else ""
    return render(request, "coffee/certidoes.html", {
        "quadros": [(f, certs.quadro(f, hoje)) for f in fornecedores],
        "anexar_f": anexar_f, "anexar_t": anexar_t,
        "anexar_rotulo": ROTULOS.get(anexar_t, ""),
        "migalhas": _migalhas(("Certidões", "")),
    })


@require_POST
def anexar_certidao(request: HttpRequest) -> HttpResponse:
    from . import certidoes as certs

    _exigir(request)
    fid = request.POST.get("fornecedor") or ""
    tipo = request.POST.get("tipo") or ""
    if not fid.isdecimal():
        return redirect("coffee:certidoes")
    get_object_or_404(Fornecedor, pk=int(fid))
    try:
        c = certs.anexar(request.user, int(fid), tipo, request.FILES.get("arquivo"),
                         _data(request.POST.get("validade")))
    except pedidos.PedidoInvalido as exc:
        messages.error(request, str(exc))
        return redirect(reverse("coffee:certidoes") + f"?anexar={fid}:{tipo}")
    texto, aviso = certs.mensagem(c)
    (messages.warning if aviso else messages.success)(request, texto)
    return redirect(reverse("coffee:certidoes") + f"#fornecedor-{fid}")


@require_GET
def arquivo_certidao(request: HttpRequest, pk: int) -> StreamingHttpResponse:
    from django.http import FileResponse

    from .models import Certidao

    _exigir(request)
    c = get_object_or_404(Certidao, pk=pk)
    nome = re.sub(r"[^\w .-]", "-", f"Certidao {c.get_tipo_display()} {c.fornecedor}")[:120]
    resposta = FileResponse(c.arquivo.open("rb"), as_attachment=True, filename=f"{nome}.pdf",
                            content_type="application/pdf")
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Cache-Control"] = "private, no-store"
    return resposta


# ---------------------------------------------------------------- protocolo (CB5c)
@require_GET
def protocolo_pagamento(request: HttpRequest, pk: int) -> HttpResponse:
    """Montar o protocolo: passo a passo, textos para copiar, a lista do anexo e os arquivos."""
    from . import protocolo

    _exigir(request)
    s = get_object_or_404(_base(), pk=pk)
    lista = protocolo.itens(request.user, s)
    return render(request, "coffee/protocolo.html", {
        "s": s, "itens": lista, "textos": protocolo.textos(s), "partes": protocolo.PARTES,
        "prontas": {i.parte for i in lista if i.pronto},
        "faltando": sum(1 for i in lista if not i.pronto),
        "migalhas": _migalhas(("Solicitações", reverse("coffee:solicitacoes")),
                              (str(s), reverse("coffee:solicitacao", args=[pk])),
                              ("Protocolo", "")),
    })


@require_POST
def baixar_protocolo(request: HttpRequest, pk: int) -> HttpResponse:
    from . import protocolo

    _exigir(request)
    get_object_or_404(Solicitacao, pk=pk)
    try:
        pacote = protocolo.baixar(request.user, pk, request.POST.getlist("partes"),
                                  request.POST.get("formato") or "zip")
    except pedidos.PedidoInvalido as exc:
        messages.error(request, str(exc))
        return redirect("coffee:protocolo", pk=pk)
    from django.utils.http import content_disposition_header
    resposta = HttpResponse(pacote.conteudo, content_type=pacote.tipo)
    resposta["Content-Disposition"] = content_disposition_header(True, pacote.nome) or "attachment"
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Cache-Control"] = "private, no-store"
    return resposta
