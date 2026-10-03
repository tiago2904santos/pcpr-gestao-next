"""O contrato com o eProtocolo, em termos do nosso domínio.

Os contextos só conhecem estes tipos. O formato real das respostas da API ainda não é
público (vem com o credenciamento — docs/integrations/eprotocolo.md); o mapeamento fica no
adaptador HTTP e é conferido quando houver acesso ao ambiente de treinamento.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class Origem(StrEnum):
    """De onde veio o número do protocolo (igual à referência)."""

    MANUAL = "manual"            # digitado por uma pessoa
    EPROTOCOLO = "eprotocolo"    # aberto em produção: vale como protocolo oficial
    TREINAMENTO = "treinamento"  # aberto no barramento de teste: NÃO vale
    SIMULADO = "simulado"        # gerado aqui, sem sair para a rede: NÃO vale


@dataclass(frozen=True)
class Movimentacao:
    em: datetime | None
    descricao: str
    local: str = ""


@dataclass(frozen=True)
class Situacao:
    numero: str
    situacao: str
    local_atual: str = ""
    movimentacoes: tuple[Movimentacao, ...] = field(default_factory=tuple)
    origem: Origem = Origem.SIMULADO

    @property
    def ultima(self) -> Movimentacao | None:
        return self.movimentacoes[-1] if self.movimentacoes else None


@dataclass(frozen=True)
class PedidoDeAbertura:
    """O que se manda para abrir um processo a partir de um documento nosso."""

    resumo: str          # assunto/detalhamento do processo
    interessado: str     # unidade ou pessoa interessada
    chave: str           # idempotência: o mesmo pedido não abre dois processos


@dataclass(frozen=True)
class ProtocoloAberto:
    numero: str          # 9 dígitos, sem pontuação
    origem: Origem


class PortaEprotocolo(Protocol):
    def autenticar(self) -> None: ...

    def consultar(self, numero: str) -> Situacao: ...

    def abrir(self, pedido: PedidoDeAbertura) -> ProtocoloAberto: ...
