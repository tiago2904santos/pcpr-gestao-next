"""Editor de documento dos documentos fora do ofício — termo e OS (ADR 0018).

``<pc-editor-documento>`` fala com estas visões por JSON, pelas mesmas rotas relativas do
editor do ofício (estado, salvar, restaurar/<n>, modelo, original, paginas, presenca,
textos). Cada documento diz, num `Adaptador`, onde está o objeto, como saem os dados e o
modelo e quais serviços gravam; aqui só há autorização, leitura e formato. Toda escrita
passa pelo serviço do documento (termos.py, ordens.py).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .documentos.regioes import bloco_original, impressao
from .views_editor import _corpo_json, _erro, _presenca, _versao_json


@dataclass(frozen=True)
class Adaptador:
    rotulos: dict[str, str]                          # região → rótulo (barra do editor)
    obter: Callable[[HttpRequest, int, str], Any]    # o documento (Http404 se não puder ver)
    dados: Callable[[Any, str], dict]                # dados do documento (sem fixar nada)
    html_modelo: Callable[[dict], str]               # o modelo, sem texto editado
    regioes_modelo: Callable[[dict], dict[str, str]]
    versoes: Callable[[Any, str], Any]               # consulta das versões
    vigente: Callable[[Any, str], Any]
    salvar: Callable[..., Any]                       # (obj, usuario, chave, regioes, versao_base)
    restaurar: Callable[..., Any]                    # (obj, usuario, chave, numero)
    modelo: Callable[..., Any]                       # (obj, usuario, chave)
    pode_editar: Callable[[Any, Any], bool]
    invalido: type[Exception]
    conflito: type[Exception]
    regioes_vigentes: Callable[[Any], dict] = dict  # o texto editado em vigor (páginas)
    # O documento com o texto editado (para contar páginas). Sem ele, uma folha só.
    html_documento: Callable[[dict, dict], str] | None = None


def montar(ad: Adaptador) -> dict[str, Callable]:
    """As visões do editor para um tipo de documento (`chave` é opcional na rota)."""

    def estado_de(request: HttpRequest, obj, chave: str, *, registrar: bool = False) -> dict:
        vigente = ad.vigente(obj, chave)
        versoes = list(ad.versoes(obj, chave).select_related("criado_por", "restaurada_de")
                       .order_by("-numero"))
        desatualizadas: list[str] = []
        if vigente is not None and not vigente.do_modelo:
            originais = ad.regioes_modelo(ad.dados(obj, chave))
            desatualizadas = [r for r, marca in vigente.impressoes.items()
                              if r in originais and impressao(originais[r]) != marca]
        return {
            "tipo": type(obj).__name__.lower(),
            "pode_editar": ad.pode_editar(request.user, obj),
            "pode_gerir_textos": False,
            "versao_oficio": None,
            "edicao": _versao_json(vigente) if vigente else None,
            "versoes": [_versao_json(v) for v in versoes],
            "desatualizadas": desatualizadas,
            "campos": [],
            "pendencias": [],
            "presenca": _presenca(obj, f"{type(obj).__name__}-{chave}", request.user,
                                  registrar=registrar),
            "regioes": [{"chave": c, "rotulo": r} for c, r in ad.rotulos.items()],
        }

    def executar(request: HttpRequest, obj, chave: str, comando) -> JsonResponse:
        try:
            resultado = comando()
        except ad.conflito as exc:
            return JsonResponse({"erro": str(exc), "conflito": True,
                                 **estado_de(request, obj, chave)}, status=409)
        except ad.invalido as exc:
            return _erro(str(exc))
        except PermissionDenied as exc:
            return _erro(str(exc) or "Sem permissão.", 403)
        obj.refresh_from_db()
        return JsonResponse({"resultado": resultado, **estado_de(request, obj, chave)})

    @require_GET
    def estado(request: HttpRequest, pk: int, chave: str = "") -> JsonResponse:
        obj = ad.obter(request, pk, chave)
        return JsonResponse(estado_de(request, obj, chave, registrar=True))

    @require_POST
    def salvar(request: HttpRequest, pk: int, chave: str = "") -> JsonResponse:
        obj = ad.obter(request, pk, chave)
        corpo = _corpo_json(request)
        regioes = corpo.get("regioes")
        if not isinstance(regioes, dict) or not all(isinstance(v, str) for v in regioes.values()):
            return _erro("Envie as regiões como um objeto chave → HTML.")
        base = corpo.get("versao_base")
        versao_base = None
        if isinstance(base, int) or (isinstance(base, str) and base.isdigit()):
            versao_base = int(base)
        return executar(request, obj, chave, lambda: {"versao": ad.salvar(
            obj, request.user, chave, regioes, versao_base).numero})

    @require_POST
    def restaurar(request: HttpRequest, pk: int, numero: int, chave: str = "") -> JsonResponse:
        obj = ad.obter(request, pk, chave)
        return executar(request, obj, chave, lambda: {"versao": ad.restaurar(
            obj, request.user, chave, numero).numero})

    @require_POST
    def modelo(request: HttpRequest, pk: int, chave: str = "") -> JsonResponse:
        obj = ad.obter(request, pk, chave)

        def comando():
            e = ad.modelo(obj, request.user, chave)
            return {"versao": e.numero if e else 0}
        return executar(request, obj, chave, comando)

    @require_GET
    def original(request: HttpRequest, pk: int, chave: str = "") -> JsonResponse:
        """HTML de um bloco como o modelo o gera agora (para "voltar ao original" por bloco)."""
        obj = ad.obter(request, pk, chave)
        bloco = (request.GET.get("bloco") or "").strip()
        html = bloco_original(ad.html_modelo(ad.dados(obj, chave)), bloco)
        if html is None:
            raise Http404
        return JsonResponse({"bloco": bloco, "html": html})

    @require_GET
    def paginas(request: HttpRequest, pk: int, chave: str = "") -> JsonResponse:
        """Total de páginas e página inicial de cada bloco, pelo mesmo motor do PDF. O termo
        e a OS cabem numa folha (sem `html_documento`): o editor só mostra o número."""
        obj = ad.obter(request, pk, chave)
        if ad.html_documento is None:
            return JsonResponse({"total": 1, "blocos": {}})
        from weasyprint import HTML

        from .documentos.pdf import _BLOCO, ASSETS, buscar_recurso
        dados = ad.dados(obj, chave)
        html = ad.html_documento(dados, ad.regioes_vigentes(obj))
        html = _BLOCO.sub(lambda m: f'<{m.group(1)} id="b-{m.group(3)}"{m.group(2)}>', html)
        doc = HTML(string=html, base_url=str(ASSETS), url_fetcher=buscar_recurso()).render()
        blocos: dict[str, int] = {}
        for numero, pagina in enumerate(doc.pages, start=1):
            for ancora in pagina.anchors:
                if ancora.startswith("b-"):
                    blocos.setdefault(ancora[2:], numero)
        return JsonResponse({"total": len(doc.pages), "blocos": blocos})

    @require_POST
    def presenca(request: HttpRequest, pk: int, chave: str = "") -> JsonResponse:
        obj = ad.obter(request, pk, chave)
        return JsonResponse({"presenca": _presenca(obj, f"{type(obj).__name__}-{chave}",
                                                   request.user, registrar=True)})

    @require_http_methods(["GET", "POST"])
    def textos(request: HttpRequest, pk: int, chave: str = "") -> JsonResponse:
        """Textos prontos são do ofício e da justificativa: aqui a lista é vazia."""
        ad.obter(request, pk, chave)
        return JsonResponse({"textos": []})

    return {"estado": estado, "salvar": salvar, "restaurar": restaurar, "modelo": modelo,
            "original": original, "paginas": paginas, "presenca": presenca, "textos": textos}


# ---------------------------------------------------------------- termo de autorização
def _termo(request: HttpRequest, pk: int, chave: str):
    from . import policies, termos
    from .models import TermoAutorizacao
    termo = TermoAutorizacao.objects.select_related("unidade", "oficio").filter(pk=pk).first()
    if termo is None or not policies.pode_ver_termo(request.user, termo) \
            or not policies.pode_ver_documento_termo(request.user, termo):
        raise Http404
    if chave not in {d["chave"] for d in termos.documentos_do_termo(termo)}:
        raise Http404
    return termo


def _adaptador_termo() -> Adaptador:
    from . import policies, termos
    return Adaptador(
        rotulos={"corpo": "Texto do termo", "assinaturas": "Assinaturas"},
        obter=_termo,
        dados=termos.dados_do_documento,
        html_modelo=termos.html_do_modelo,
        regioes_modelo=termos.regioes_do_modelo,
        versoes=termos._versoes,
        vigente=termos.edicao_vigente,
        salvar=lambda o, u, c, r, b: termos.salvar_texto(o, u, c, r, versao_base=b),
        restaurar=termos.restaurar_texto,
        modelo=termos.voltar_texto_ao_modelo,
        pode_editar=policies.pode_editar_termo,
        invalido=termos.TermoInvalido,
        conflito=termos.ConflitoDeEdicao,
    )


# ---------------------------------------------------------------- ordem de serviço
def _ordem(request: HttpRequest, pk: int, chave: str):
    from . import ordens, policies
    from .models import OrdemServico
    ordem = ordens.com_dados(OrdemServico.objects.all()).filter(pk=pk).first()
    if ordem is None or not policies.pode_ver_ordem(request.user, ordem) \
            or not policies.pode_ver_documento_ordem(request.user, ordem):
        raise Http404
    return ordem


def _adaptador_ordem() -> Adaptador:
    from . import ordens, policies
    return Adaptador(
        rotulos={"corpo": "Texto da OS", "assinatura": "Assinatura"},
        obter=_ordem,
        dados=lambda o, _c: ordens.dados_do_documento(o, fixar=False),
        html_modelo=ordens.html_do_modelo,
        regioes_modelo=ordens.regioes_do_modelo,
        versoes=lambda o, _c: ordens._versoes(o),
        vigente=lambda o, _c: ordens.edicao_vigente(o),
        salvar=lambda o, u, _c, r, b: ordens.salvar_texto(o, u, r, versao_base=b),
        restaurar=lambda o, u, _c, n: ordens.restaurar_texto(o, u, n),
        modelo=lambda o, u, _c: ordens.voltar_texto_ao_modelo(o, u),
        pode_editar=policies.pode_editar_ordem,
        invalido=ordens.OrdemInvalida,
        conflito=ordens.ConflitoDeEdicao,
    )


# ---------------------------------------------------------------- plano de trabalho
def _plano(request: HttpRequest, pk: int, chave: str):
    from . import planos, policies
    from .models import PlanoTrabalho
    plano = planos.com_dados(PlanoTrabalho.objects.all()).filter(pk=pk).first()
    if plano is None or not policies.pode_ver_plano(request.user, plano) \
            or not policies.pode_ver_documento_plano(request.user, plano):
        raise Http404
    return plano


def _adaptador_plano() -> Adaptador:
    from . import planos, policies
    return Adaptador(
        rotulos={"corpo": "Plano", "fecho": "Coordenação e considerações",
                 "assinatura": "Assinatura"},
        obter=_plano,
        dados=lambda o, _c: planos.dados_do_documento(o, fixar=False),
        html_modelo=planos.html_do_modelo,
        regioes_modelo=planos.regioes_do_modelo,
        versoes=lambda o, _c: planos._versoes(o),
        vigente=lambda o, _c: planos.edicao_vigente(o),
        salvar=lambda o, u, _c, r, b: planos.salvar_texto(o, u, r, versao_base=b),
        restaurar=lambda o, u, _c, n: planos.restaurar_texto(o, u, n),
        modelo=lambda o, u, _c: planos.voltar_texto_ao_modelo(o, u),
        pode_editar=policies.pode_editar_plano,
        invalido=planos.PlanoInvalido,
        conflito=planos.ConflitoDeEdicao,
        # O plano tem várias páginas: o editor mostra quantas, como no ofício.
        regioes_vigentes=planos.regioes_vigentes,
        html_documento=lambda d, r: planos.html_do_documento(d, regioes=r),
    )


@require_POST
def aplicar_em_todos_termo(request: HttpRequest, pk: int, chave: str) -> JsonResponse:
    """Leva o texto editado deste documento do termo para os outros (o que é texto comum;
    termos.aplicar_texto_em_todos). O editor pergunta antes ("Aplicar em todos os termos?")."""
    from . import termos
    obj = _termo(request, pk, chave)
    try:
        atualizados, ficaram = termos.aplicar_texto_em_todos(obj, request.user, chave)
    except termos.TermoInvalido as exc:
        return _erro(str(exc))
    except PermissionDenied as exc:
        return _erro(str(exc) or "Sem permissão.", 403)
    return JsonResponse({"atualizados": atualizados, "ficaram": ficaram})


termo = montar(_adaptador_termo())
ordem = montar(_adaptador_ordem())
plano = montar(_adaptador_plano())
