"""Editor de documento dentro do visualizador (ADR 0018).

A folha HTML do documento é mostrada num iframe da mesma origem; o componente
``<pc-editor-documento>`` torna as regiões editáveis e fala com estas visões por JSON.
Toda escrita passa por ``services``; aqui só há autorização, leitura e formato.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.middleware.csp import get_nonce
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.csp import CSP
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csp import csp_override
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import policies, services
from .documentos.campos import campos_do_documento
from .documentos.dados import dados_do_oficio
from .documentos.pdf import (
    html_do_documento,
    html_do_modelo,
    paginas_do_documento,
    regioes_do_modelo,
)
from .documentos.regioes import bloco_original, impressao
from .models import Documento, EdicaoDocumento, Oficio

TIPOS = {t.value for t in Documento.Tipo}
PRESENCA_SEGUNDOS = 90


def _documento(request: HttpRequest, pk: int, tipo: str) -> Oficio:
    if tipo not in TIPOS:
        raise Http404
    oficio = get_object_or_404(
        Oficio.objects.select_related("unidade", "unidade__configuracao", "viatura",
                                      "viatura__combustivel", "sede", "transporte_combustivel"),
        pk=pk)
    if not policies.pode_ver(request.user, oficio):
        raise Http404
    return oficio


def _corpo_json(request: HttpRequest) -> dict[str, Any]:
    try:
        corpo = json.loads(request.body or b"{}")
    except ValueError:
        return {}
    return corpo if isinstance(corpo, dict) else {}


def _erro(mensagem: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"erro": mensagem}, status=status)


def _versao_json(e: EdicaoDocumento) -> dict[str, Any]:
    return {
        "numero": e.numero, "acao": e.acao, "acao_rotulo": e.get_acao_display(),
        "do_modelo": e.do_modelo, "blocos_alterados": e.blocos_alterados,
        "restaurada_de": e.restaurada_de.numero if e.restaurada_de is not None else None,
        "criado_por": str(e.criado_por) if e.criado_por_id else "",
        "criado_em": timezone.localtime(e.criado_em).isoformat(timespec="minutes"),
        "quando": f"{timezone.localtime(e.criado_em):%d/%m %H:%M}",
    }


def _presenca(oficio: Oficio, tipo: str, usuario, *, registrar: bool) -> list[dict[str, str]]:
    chave = f"editor:{oficio.pk}:{tipo}"
    agora = timezone.now()
    presentes: dict[str, dict[str, Any]] = cache.get(chave) or {}
    presentes = {k: v for k, v in presentes.items()
                 if (agora - datetime.fromisoformat(v["em"])).total_seconds()
                 < PRESENCA_SEGUNDOS}
    if registrar:
        presentes[str(usuario.pk)] = {"nome": str(usuario), "em": agora.isoformat()}
        cache.set(chave, presentes, PRESENCA_SEGUNDOS * 2)
    return [{"nome": v["nome"]} for k, v in presentes.items() if k != str(usuario.pk)]


def _estado(request: HttpRequest, oficio: Oficio, tipo: str, *,
            registrar_presenca: bool = False) -> dict[str, Any]:
    dados = dados_do_oficio(oficio)
    vigente = services.edicao_vigente(oficio, tipo)
    versoes = list(EdicaoDocumento.objects.filter(oficio=oficio, tipo=tipo)
                   .select_related("criado_por", "restaurada_de").order_by("-numero"))
    desatualizadas: list[str] = []
    if vigente is not None and not vigente.do_modelo:
        originais = regioes_do_modelo(tipo, dados)
        desatualizadas = [chave for chave, marca in vigente.impressoes.items()
                          if chave in originais and impressao(originais[chave]) != marca]
    campos = []
    pendencias = []
    for c in campos_do_documento(tipo):
        valor = str(getattr(oficio, c.atributo) or "")
        vazio = not valor.strip()
        if c.chave == "custeio_instituicao" and oficio.custeio != Oficio.Custeio.OUTRA_INSTITUICAO:
            continue
        campos.append({"chave": c.chave, "rotulo": c.rotulo, "valor": valor,
                       "obrigatorio": c.obrigatorio, "vazio": vazio, "secao": c.secao,
                       "multilinha": c.multilinha})
        if vazio and (c.obrigatorio or c.chave == "custeio_instituicao"):
            pendencias.append({"chave": c.chave, "mensagem": f"Falta: {c.rotulo}"})
    return {
        "tipo": tipo,
        "pode_editar": policies.pode_editar_texto(request.user, oficio),
        "pode_gerir_textos": policies.pode_gerir_textos_prontos(request.user),
        "versao_oficio": oficio.versao,
        "edicao": _versao_json(vigente) if vigente else None,
        "versoes": [_versao_json(v) for v in versoes],
        "desatualizadas": desatualizadas,
        "campos": campos,
        "pendencias": pendencias,
        "presenca": _presenca(oficio, tipo, request.user, registrar=registrar_presenca),
        "regioes": [{"chave": chave, "rotulo": rotulo} for chave, rotulo in ROTULOS[tipo].items()],
    }


ROTULOS = {
    "oficio": {"cabecalho": "Identificação", "corpo": "Corpo do ofício",
               "rodape": "Assinatura e destinatário"},
    "justificativa": {"corpo": "Justificativa", "rodape": "Assinatura"},
}


# ---------------------------------------------------------------- folha (iframe)
# Mesma exceção da minuta em PDF: só a própria origem pode emoldurar a folha; e o estilo do
# documento (o mesmo que vai ao PDF) entra com o nonce da requisição. Vale para toda folha
# de documento num visualizador (ofício, justificativa, termo, OS).
def _moldura(politica: dict):
    """CSP com a moldura da própria origem — e o X-Frame-Options coerente com ela (os
    navegadores atuais seguem o CSP, mas os dois cabeçalhos não devem se contradizer)."""
    def decorar(view):
        return xframe_options_sameorigin(csp_override(politica)(view))
    return decorar


moldura_da_folha = _moldura({**settings.SECURE_CSP, "frame-ancestors": [CSP.SELF],
                             "style-src": [CSP.SELF, CSP.NONCE]})
# O PDF que o visualizador mostra no modo "PDF" (termos, OS): só a moldura muda.
moldura_do_pdf = _moldura({**settings.SECURE_CSP, "frame-ancestors": [CSP.SELF]})


@require_GET
@moldura_da_folha
def folha(request: HttpRequest, pk: int, tipo: str) -> HttpResponse:
    """O documento como HTML, com o texto editado em vigor (ou a versão pedida em ?versao=)."""
    oficio = _documento(request, pk, tipo)
    dados = dados_do_oficio(oficio)
    pedido = request.GET.get("versao")
    marcados: set[str] = set()
    if pedido is not None and pedido.isdigit():
        numero = int(pedido)
        if numero == 0:
            regioes: dict[str, str] = {}
        else:
            edicao = get_object_or_404(EdicaoDocumento, oficio=oficio, tipo=tipo, numero=numero)
            regioes = dict(edicao.regioes)
            marcados = {b["chave"] for b in edicao.blocos_alterados}
    else:
        vigente = services.edicao_vigente(oficio, tipo)
        regioes = dict(vigente.regioes) if vigente else {}
        marcados = {b["chave"] for b in vigente.blocos_alterados} if vigente else set()
    # O nonce é preguiçoso (e falso até ser lido): convertê-lo aqui gera o valor e garante
    # que o cabeçalho o carregue.
    preguicoso = get_nonce(request)
    nonce = str(preguicoso) if preguicoso is not None else ""
    html = html_do_documento(tipo, dados, previa=True, folha=True, nonce=nonce,
                             regioes=regioes, blocos_alterados=marcados)
    resposta = HttpResponse(html)
    resposta["Cache-Control"] = "no-store"
    return resposta


def resposta_de_folha(request: HttpRequest, gerar, erros: tuple[type[Exception], ...] = (),
                      erro: Exception | None = None) -> HttpResponse:
    """Folha de documento para o iframe do visualizador (termos, OS): `gerar(nonce)` devolve
    o HTML. Um erro esperado (ex.: unidade sem configuração) vira uma folha com o aviso, no
    lugar do documento — o visualizador nunca fica em branco."""
    preguicoso = get_nonce(request)
    nonce = str(preguicoso) if preguicoso is not None else ""
    try:
        if erro is not None:  # o erro já aconteceu (ex.: no PDF do visualizador)
            raise erro
        html = gerar(nonce)
    except erros as exc:
        html = render_to_string("viagens/documentos/_sem_folha.html", {"mensagem": str(exc)})
    resposta = HttpResponse(html)
    resposta["Cache-Control"] = "no-store"
    return resposta


def primeiro_erro(form) -> str:
    """O primeiro erro do formulário, com o nome do campo, para a linha de status do
    autosave (a tela mostra todos quando se salva pelo botão)."""
    for nome, erros in form.errors.items():
        rotulo = form.fields[nome].label if nome in form.fields else ""
        texto = erros[0] if erros else ""
        return f"Não salvo: {rotulo} — {texto}" if rotulo else f"Não salvo: {texto}"
    return "Não salvo."


# ---------------------------------------------------------------- estado e escrita (JSON)
@require_GET
def estado(request: HttpRequest, pk: int, tipo: str) -> JsonResponse:
    oficio = _documento(request, pk, tipo)
    return JsonResponse(_estado(request, oficio, tipo, registrar_presenca=True))


def _executar(request: HttpRequest, oficio: Oficio, tipo: str, comando) -> JsonResponse:
    try:
        resultado = comando()
    except services.ConflitoDeEdicao as exc:
        return JsonResponse({"erro": str(exc), "conflito": True,
                             **_estado(request, oficio, tipo)}, status=409)
    except services.RegraViolada as exc:
        return _erro(str(exc))
    except PermissionDenied as exc:
        return _erro(str(exc) or "Sem permissão.", 403)
    oficio.refresh_from_db()
    return JsonResponse({"resultado": resultado, **_estado(request, oficio, tipo)})


@require_POST
def salvar(request: HttpRequest, pk: int, tipo: str) -> JsonResponse:
    oficio = _documento(request, pk, tipo)
    corpo = _corpo_json(request)
    regioes = corpo.get("regioes")
    if not isinstance(regioes, dict) or not all(isinstance(v, str) for v in regioes.values()):
        return _erro("Envie as regiões como um objeto chave → HTML.")
    base = corpo.get("versao_base")
    versao_base = None
    if isinstance(base, int) or (isinstance(base, str) and base.isdigit()):
        versao_base = int(base)

    def comando():
        e = services.salvar_texto_do_documento(oficio, request.user, tipo, regioes,
                                               versao_base=versao_base)
        return {"versao": e.numero}
    return _executar(request, oficio, tipo, comando)


@require_POST
def restaurar(request: HttpRequest, pk: int, tipo: str, numero: int) -> JsonResponse:
    oficio = _documento(request, pk, tipo)

    def comando():
        e = services.restaurar_texto_do_documento(oficio, request.user, tipo, numero)
        return {"versao": e.numero}
    return _executar(request, oficio, tipo, comando)


@require_POST
def modelo(request: HttpRequest, pk: int, tipo: str) -> JsonResponse:
    oficio = _documento(request, pk, tipo)

    def comando():
        e = services.voltar_texto_ao_modelo(oficio, request.user, tipo)
        return {"versao": e.numero if e else 0}
    return _executar(request, oficio, tipo, comando)


@require_http_methods(["POST", "PATCH"])
def campo(request: HttpRequest, pk: int, tipo: str, chave: str) -> JsonResponse:
    """Grava um campo vinculado editado de dentro da folha."""
    oficio = _documento(request, pk, tipo)
    corpo = _corpo_json(request)
    valor = corpo.get("valor")
    if not isinstance(valor, str):
        return _erro("Envie o valor como texto.")
    versao = corpo.get("versao")
    versao = int(versao) if isinstance(versao, int) else None

    def comando():
        atual = services.salvar_campo_do_documento(oficio, request.user, chave, valor,
                                                   versao=versao)
        from .documentos.campos import CAMPOS
        return {"chave": chave, "valor": str(getattr(atual, CAMPOS[chave].atributo) or ""),
                "versao_oficio": atual.versao}
    return _executar(request, oficio, tipo, comando)


@require_GET
def original(request: HttpRequest, pk: int, tipo: str) -> JsonResponse:
    """HTML de um bloco como o modelo o gera agora (para "voltar ao original" por bloco)."""
    oficio = _documento(request, pk, tipo)
    chave = (request.GET.get("bloco") or "").strip()
    html = bloco_original(html_do_modelo(tipo, dados_do_oficio(oficio)), chave)
    if html is None:
        raise Http404
    return JsonResponse({"bloco": chave, "html": html})


@require_GET
def paginas(request: HttpRequest, pk: int, tipo: str) -> JsonResponse:
    """Total de páginas e página inicial de cada bloco, calculados pelo mesmo motor do PDF."""
    oficio = _documento(request, pk, tipo)
    regioes = services.regioes_vigentes(oficio, tipo)
    return JsonResponse(paginas_do_documento(tipo, dados_do_oficio(oficio), regioes))


@require_POST
def presenca(request: HttpRequest, pk: int, tipo: str) -> JsonResponse:
    oficio = _documento(request, pk, tipo)
    return JsonResponse({"presenca": _presenca(oficio, tipo, request.user, registrar=True)})


# ---------------------------------------------------------------- textos prontos
def _texto_json(m) -> dict[str, Any]:
    return {"id": m.pk, "nome": m.nome, "texto": m.texto, "tipo": m.tipo,
            "tipo_rotulo": m.get_tipo_display(), "padrao_sistema": m.padrao_sistema}


@require_http_methods(["GET", "POST"])
def textos(request: HttpRequest, pk: int, tipo: str) -> JsonResponse:
    oficio = _documento(request, pk, tipo)
    if request.method == "POST":
        corpo = _corpo_json(request)
        try:
            m = services.criar_texto_pronto(request.user, tipo, str(corpo.get("nome") or ""),
                                            str(corpo.get("texto") or ""))
        except services.RegraViolada as exc:
            return _erro(str(exc))
        except PermissionDenied as exc:
            return _erro(str(exc), 403)
        return JsonResponse({"criado": _texto_json(m),
                             "textos": [_texto_json(t) for t in services.textos_prontos(tipo)]},
                            status=201)
    del oficio
    return JsonResponse({"textos": [_texto_json(t) for t in services.textos_prontos(tipo)]})


@require_POST
def remover_texto(request: HttpRequest, pk: int, tipo: str, texto_id: int) -> JsonResponse:
    _documento(request, pk, tipo)
    try:
        services.desativar_texto_pronto(request.user, texto_id)
    except services.RegraViolada as exc:
        return _erro(str(exc))
    except PermissionDenied as exc:
        return _erro(str(exc), 403)
    return JsonResponse({"textos": [_texto_json(t) for t in services.textos_prontos(tipo)]})
