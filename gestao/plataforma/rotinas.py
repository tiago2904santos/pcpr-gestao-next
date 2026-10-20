"""Rotinas diárias sem agendador (paridade com `core/rotinas.py` da referência): o primeiro
acesso de usuário logado do dia dispara os lembretes. Cada contexto registra as suas
(`registrar_rotina`, chamado no `ready` do app) — a plataforma não conhece os módulos.

Cada rotina é idempotente (avisa uma vez só) e roda protegida: a falha de uma vira log e não
impede as outras nem a página que a pessoa abriu. Quem tiver cron usa o comando
`rodar_rotinas_diarias`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

_ROTINAS: list[tuple[str, Callable[[date], object]]] = []
_RECURSO_DA_ROTINA: dict[str, str] = {}
_ultimo_dia_visto = ""  # evita ir ao banco a cada requisição deste processo


def registrar_rotina(nome: str, funcao: Callable[[date], object],
                     recurso: str | None = None) -> None:
    """`recurso` (plataforma.recursos): com ele desligado, a rotina não roda."""
    if all(n != nome for n, _ in _ROTINAS):
        _ROTINAS.append((nome, funcao))
    if recurso is not None:
        _RECURSO_DA_ROTINA[nome] = recurso


def rodar(hoje: date | None = None) -> dict[str, str]:
    """Todas as rotinas, cada uma protegida da falha das outras."""
    hoje = hoje or timezone.localdate()
    resultado: dict[str, str] = {}
    from .recursos import ligado

    for nome, funcao in _ROTINAS:
        if nome in _RECURSO_DA_ROTINA and not ligado(_RECURSO_DA_ROTINA[nome]):
            resultado[nome] = "desligada"
            continue
        try:
            with transaction.atomic():
                resultado[nome] = str(funcao(hoje))
            logger.info("Rotina diária %s: %s.", nome, resultado[nome])
        except Exception:
            logger.exception("Rotina diária %s falhou.", nome)
            resultado[nome] = "falhou"
    return resultado


def rodar_se_for_hora(hoje: date | None = None) -> bool:
    """Roda as rotinas se ainda não rodaram hoje (em nenhum processo); True se rodou agora."""
    global _ultimo_dia_visto
    from .models import RotinaDoDia

    hoje = hoje or timezone.localdate()
    if _ultimo_dia_visto == hoje.isoformat():
        return False
    _ultimo_dia_visto = hoje.isoformat()
    try:
        with transaction.atomic():
            marca = RotinaDoDia.objects.create(dia=hoje)
    except IntegrityError:
        return False  # outro processo já rodou (ou está rodando) hoje
    marca.resultado = rodar(hoje)
    marca.save(update_fields=["resultado"])
    return True


def esquecer_o_dia() -> None:
    """Para os testes: o processo volta a consultar o banco."""
    global _ultimo_dia_visto
    _ultimo_dia_visto = ""
