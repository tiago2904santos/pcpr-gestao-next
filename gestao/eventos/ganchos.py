"""Ganchos de Eventos Sociais para a integração com Viagens (E4) sem Eventos importar
Viagens: o contexto de Viagens registra aqui, no `ready`, como resume, gera e encerra a viagem
de uma solicitação. Sem registro (Viagens fora do ar ou desligado), a folha simplesmente não
mostra a seção da viagem e o despacho segue igual — a viagem é consequência do deferimento,
nunca condição para ele (referência: "a geração não derruba o despacho")."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IntegracaoViagem:
    # (usuário, solicitação) → o que a folha mostra: viagens geradas, se pode gerar, por que
    # não pode, as unidades possíveis e a sugerida.
    resumo: Callable[[Any, Any], dict[str, Any]]
    # (usuário, solicitação, unidade_id) → a viagem criada; levanta ValueError com o motivo.
    gerar: Callable[[Any, Any, int | None], Any]
    # (usuário, solicitação, motivo) → "cancelada", "avisada" ou "" (não havia viagem).
    encerrar: Callable[[Any, Any, str], str]


_INTEGRACAO: list[IntegracaoViagem] = []


def registrar_viagem(integracao: IntegracaoViagem) -> None:
    _INTEGRACAO[:] = [integracao]


def viagem() -> IntegracaoViagem | None:
    return _INTEGRACAO[0] if _INTEGRACAO else None
