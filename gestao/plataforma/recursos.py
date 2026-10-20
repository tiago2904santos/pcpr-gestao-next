"""Recursos opcionais que se ligam e desligam pela configuração (ADR 0050).

Três chaves, todas lidas do ambiente (`config/settings/base.py`):

- `IA_HABILITADA` — assistência por IA (sugestões, Central de ajuda, worker `processar_ia`);
- `AUTOMACAO_HABILITADA` — automações (módulo Automação, API, webhooks, comunicações
  automáticas, eventos ao n8n, worker `processar_automacao`). As Pendências e os envios
  manuais pelo WhatsApp do operador continuam: não dependem desta chave;
- `EPROTOCOLO_HABILITADO` — integração e atalhos do eProtocolo (consulta de andamento, dados
  para copiar). O número do protocolo continua sendo digitado à mão.

Desligado, o recurso some do menu, os botões não aparecem e as rotas respondem 404. Nada é
apagado: religar a chave devolve tudo como estava.

A plataforma não conhece os contextos: cada um registra as próprias rotas (`registrar_rotas`,
pelo namespace de URL) e marca as views avulsas com `@exige(recurso)`.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from django.conf import settings
from django.http import Http404

IA = "ia"
AUTOMACAO = "automacao"
EPROTOCOLO = "eprotocolo"

_CHAVES = {IA: "IA_HABILITADA", AUTOMACAO: "AUTOMACAO_HABILITADA",
           EPROTOCOLO: "EPROTOCOLO_HABILITADO"}
_ROTAS: dict[str, str] = {}  # namespace de URL → recurso

F = TypeVar("F", bound=Callable[..., Any])


def ligado(recurso: str) -> bool:
    """O recurso está ligado? Chave desconhecida é erro de programação (KeyError)."""
    return bool(getattr(settings, _CHAVES[recurso], True))


def todos() -> dict[str, bool]:
    """{recurso: ligado} — o que os templates leem como `recursos.ia`, `recursos.eprotocolo`…"""
    return {recurso: ligado(recurso) for recurso in _CHAVES}


def registrar_rotas(namespace: str, recurso: str) -> None:
    """Todas as rotas do namespace respondem 404 quando o recurso estiver desligado."""
    if recurso not in _CHAVES:
        raise KeyError(recurso)
    _ROTAS[namespace] = recurso


def recurso_das_rotas(namespaces: list[str]) -> str | None:
    for namespace in namespaces:
        if namespace in _ROTAS:
            return _ROTAS[namespace]
    return None


def exigir(recurso: str) -> None:
    if not ligado(recurso):
        raise Http404("Recurso desligado.")


def exige(recurso: str) -> Callable[[F], F]:
    """Decorador de view: 404 quando o recurso estiver desligado."""
    if recurso not in _CHAVES:
        raise KeyError(recurso)

    def decorar(view: F) -> F:
        @wraps(view)
        def envolvida(*args: Any, **kwargs: Any) -> Any:
            exigir(recurso)
            return view(*args, **kwargs)

        return envolvida  # type: ignore[return-value]

    return decorar
