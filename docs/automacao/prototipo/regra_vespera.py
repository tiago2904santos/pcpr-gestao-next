"""Regra da véspera (função pura, sem I/O e sem relógio implícito).

Envio do link de quilometragem (e afins) às 09:00 de America/Sao_Paulo do dia anterior ao
início da viagem. Se a viagem for confirmada depois desse instante e ainda não começou,
envia na hora; se já começou, envia na hora com aviso. Reagendamento recalcula e invalida a
comunicação anterior por versão; cancelamento cancela.

Este módulo é a referência executável da regra para o protótipo. No PCPR real ela iria para
`gestao/viagens/dominio/` (Python puro), com o mesmo conjunto de testes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
HORA_ENVIO = time(9, 0)

AVISO_VIAGEM_JA_INICIADA = "viagem_ja_iniciada"


@dataclass(frozen=True)
class DecisaoEnvio:
    """Quando enviar. `enviar_em` sempre com fuso America/Sao_Paulo."""

    enviar_em: datetime
    imediato: bool
    aviso: str | None = None


@dataclass(frozen=True)
class ViagemRef:
    versao: int
    inicio: datetime
    cancelada: bool = False


@dataclass(frozen=True)
class ComunicacaoRef:
    id: int
    versao_viagem: int
    estado: str  # agendada | enviando | enviada | falhou | cancelada


@dataclass(frozen=True)
class Plano:
    """O que fazer com as comunicações de uma viagem depois de um fato de negócio."""

    cancelar_id: int | None = None
    motivo_cancelamento: str | None = None
    criar: DecisaoEnvio | None = None
    ignorado: str | None = None  # motivo de não fazer nada


def _exigir_fuso(nome: str, valor: datetime) -> None:
    if valor.tzinfo is None or valor.utcoffset() is None:
        raise ValueError(f"{nome} precisa ter fuso horário explícito (datetime 'aware').")


def instante_vespera(inicio: datetime) -> datetime:
    """09:00 (America/Sao_Paulo) do dia anterior à DATA LOCAL do início."""
    _exigir_fuso("inicio", inicio)
    data_local = inicio.astimezone(FUSO).date()
    return datetime.combine(data_local - timedelta(days=1), HORA_ENVIO, tzinfo=FUSO)


def calcular_envio(inicio: datetime, agora: datetime) -> DecisaoEnvio:
    """Decide quando enviar a comunicação de véspera.

    - antes de D-1 09:00 → agenda para D-1 09:00;
    - entre D-1 09:00 (inclusive) e o início → envia já;
    - no início ou depois → envia já, com aviso `viagem_ja_iniciada`.
    """
    _exigir_fuso("inicio", inicio)
    _exigir_fuso("agora", agora)
    alvo = instante_vespera(inicio)
    agora_local = agora.astimezone(FUSO)
    if agora < alvo:
        return DecisaoEnvio(enviar_em=alvo, imediato=False)
    if agora < inicio:
        return DecisaoEnvio(enviar_em=agora_local, imediato=True)
    return DecisaoEnvio(enviar_em=agora_local, imediato=True, aviso=AVISO_VIAGEM_JA_INICIADA)


def planejar(viagem: ViagemRef, atual: ComunicacaoRef | None, agora: datetime) -> Plano:
    """Aplica a regra a um fato da viagem (confirmação, reagendamento, cancelamento).

    A comunicação guarda a versão da viagem com que foi calculada. Versão nova → a anterior
    (se ainda não saiu) é cancelada como obsoleta e uma nova é calculada. Fato antigo (versão
    menor que a da comunicação) é ignorado: trata eventos fora de ordem.
    """
    # Só o que ainda não saiu pode ser cancelado. "enviando" já está com o canal: segue e o
    # resultado é conferido (uma mensagem nova corrige, se for o caso).
    pendente = atual is not None and atual.estado == "agendada"
    # Fato antigo (versão menor que a da comunicação atual) é ignorado ANTES de tudo, inclusive
    # do cancelamento: um "viagem cancelada" atrasado não pode cancelar a comunicação calculada
    # depois dele (revisão do PR #23, apontamento C4).
    if atual is not None and viagem.versao < atual.versao_viagem:
        return Plano(ignorado="versao_antiga")
    if viagem.cancelada:
        if atual is not None and pendente:
            return Plano(cancelar_id=atual.id, motivo_cancelamento="viagem_cancelada")
        return Plano(ignorado="nada_pendente")
    if atual is None:
        return Plano(criar=calcular_envio(viagem.inicio, agora))
    if viagem.versao == atual.versao_viagem:
        return Plano(ignorado="mesma_versao")
    nova = calcular_envio(viagem.inicio, agora)
    if pendente:
        return Plano(cancelar_id=atual.id, motivo_cancelamento="obsoleta", criar=nova)
    # Já enviada para a data antiga: a nova data pede novo envio (decisão a validar com o negócio).
    return Plano(criar=nova)
