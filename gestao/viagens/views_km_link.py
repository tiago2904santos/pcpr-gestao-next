"""Página pública do link de km (`/p/<token>/`, escopo `km`; fluxo 10-4).

A porta `/p/` (automação) já conferiu o token, a validade e a revogação, conta os erros e
põe `no-referrer`, `noindex` e `no-store` na resposta. Aqui:

- `GET /p/<token>/` — os trechos deste diário e os campos de km. Só lê: não sincroniza nem
  grava linhas. Ofício cancelado, diário de outra pessoa ou inexistente: a mesma página
  "Link indisponível" de um link vencido;
- `POST /p/<token>/salvar/` — JSON (`{"lancamentos": [...]}`, cabeçalho `X-CSRFToken`) do
  módulo `km-offline.js`, ou o formulário comum de um trecho (sem JavaScript);
- `GET /p/<token>/sw/` — o service worker da página (escopo: só este link).
"""

from __future__ import annotations

import json
import secrets
from typing import Any

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone

from gestao.automacao.views_links import indisponivel
from gestao.plataforma.middleware import ip_do_cliente

from . import km_link

TAMANHO_MAXIMO = 32 * 1024
ENVIOS_POR_JANELA, JANELA = 60, 600  # por link: 60 gravações a cada 10 minutos


def _base(request: HttpRequest, resto: str) -> str:
    return request.path[: -(len(resto) + 1)] if resto else request.path


def _excedeu(link) -> bool:
    chave = f"km-link-envios:{link.pk}"
    if cache.add(chave, 1, JANELA):
        return False
    try:
        return cache.incr(chave) > ENVIOS_POR_JANELA
    except ValueError:
        cache.set(chave, 1, JANELA)
        return False


def pagina(request: HttpRequest, link, resto: str) -> HttpResponse:
    if resto == "sw" and request.method == "GET":
        return _service_worker(request, link)
    if resto not in ("", "salvar"):
        return indisponivel(request)
    diario = km_link.diario_do_recurso(link.recurso)
    estado = km_link.situacao(link, diario)
    if not estado.disponivel or diario is None:
        return indisponivel(request)
    if request.method != "POST":
        return _pagina(request, link, diario, estado, _base(request, resto))
    if resto != "salvar":
        return HttpResponse(status=405, headers={"Allow": "GET"})
    if _excedeu(link):
        return JsonResponse({"ok": False, "codigo": "limite", "mensagem": "Muitos envios em "
                             "pouco tempo. Tente de novo em alguns minutos."}, status=429,
                            headers={"Retry-After": "60"})
    if request.content_type == "application/json":
        return _salvar_json(request, link)
    return _salvar_formulario(request, link, resto)


# ------------------------------------------------------------------ JSON (km-offline.js)
STATUS = {"formato": 400, "indisponivel": 404, "suspenso": 409, "travado": 409,
          "sem_responsavel": 409}


def _linhas_json(link) -> list[dict]:
    diario = km_link.diario_do_recurso(link.recurso)
    return [{"linha": lin.pk, "chave": lin.chave, "km_inicial": lin.km_inicial,
             "km_final": lin.km_final, "salvo": lin.salvo}
            for lin in (km_link.projecao(diario) if diario else [])]


def _salvar_json(request: HttpRequest, link) -> HttpResponse:
    if len(request.body) > TAMANHO_MAXIMO:
        return JsonResponse({"ok": False, "codigo": "tamanho",
                             "mensagem": "Envio grande demais."}, status=413)
    try:
        corpo = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        corpo = None
    if not isinstance(corpo, dict) or not isinstance(corpo.get("lancamentos"), list):
        return JsonResponse({"ok": False, "codigo": "formato",
                             "mensagem": "Formato inválido."}, status=400)
    try:
        resultados = km_link.aplicar(link, corpo["lancamentos"], ip=ip_do_cliente(request))
    except km_link.Bloqueio as b:
        return JsonResponse({"ok": False, "codigo": b.codigo, "mensagem": b.mensagem},
                            status=STATUS.get(b.codigo, 409))
    return JsonResponse({"ok": True, "resultados": [r.como_dict() for r in resultados],
                         "linhas": _linhas_json(link)})


# ------------------------------------------------------------------ formulário (sem JS)
def _salvar_formulario(request: HttpRequest, link, resto: str) -> HttpResponse:
    p = request.POST
    item: dict[str, Any] = {
        "id": p.get("id", ""), "linha": p.get("linha", ""), "chave": p.get("chave", ""),
        "campos": {c: p.get(c, "") for c in km_link.CAMPOS if c in p},
        "base": {c: p.get(f"base_{c}", "") for c in km_link.CAMPOS}}
    erro, resultado = "", None
    try:
        resultado = km_link.aplicar(link, [item], ip=ip_do_cliente(request))[0]
    except km_link.Bloqueio as b:
        erro = b.mensagem
    diario = km_link.diario_do_recurso(link.recurso)
    estado = km_link.situacao(link, diario)
    if not estado.disponivel or diario is None:
        return indisponivel(request)
    status = 200 if resultado is not None and resultado.situacao == "gravado" else (
        409 if resultado is not None and resultado.situacao == "conflito" else 400 if
        resultado is not None else 409)
    return _pagina(request, link, diario, estado, _base(request, resto), resultado=resultado,
                   digitado=item["campos"], erro=erro, status=status)


# ------------------------------------------------------------------ página
def _pagina(request: HttpRequest, link, diario, estado, base: str, *, resultado=None,
            digitado: dict | None = None, erro: str = "", status: int = 200) -> HttpResponse:
    linhas = km_link.projecao(diario)
    servidor = link.servidor
    contexto = {
        "link_id": link.pk, "base": base, "nome": (servidor.nome or "").split(" ")[0].title(),
        "valido_ate": timezone.localtime(link.expira_em),
        "somente_leitura": estado.somente_leitura, "erro": erro,
        "linhas": [_linha(lin, resultado, digitado) for lin in linhas],
        "completas": sum(1 for lin in linhas if lin.completa), "total": len(linhas),
    }
    return render(request, "viagens/km_link/pagina.html", contexto, status=status)


def _linha(lin, resultado, digitado: dict | None) -> dict:
    """Um trecho da página. Depois de um envio sem JavaScript recusado ou em conflito, os
    campos voltam com o que a pessoa digitou (e não com o valor do sistema)."""
    deste = resultado if resultado is not None and resultado.linha == lin.pk else None
    valores = {"km_inicial": lin.km_inicial, "km_final": lin.km_final}
    if deste is not None and deste.situacao != "gravado":
        valores.update(digitado or {})
    return {"l": lin, "id": secrets.token_urlsafe(12), "resultado": deste,
            "valores": valores}


def _service_worker(request: HttpRequest, link) -> HttpResponse:
    base = _base(request, "sw")
    vencido = render_to_string("viagens/km_link/vencido.html", {"link_id": link.pk})
    corpo = render_to_string("viagens/km_link/sw.js", {
        "base": base, "link_id": link.pk, "vencido": vencido,
        "expira_ms": int(link.expira_em.timestamp() * 1000)}, request=request)
    return HttpResponse(corpo, content_type="text/javascript; charset=utf-8",
                        headers={"Service-Worker-Allowed": base})
