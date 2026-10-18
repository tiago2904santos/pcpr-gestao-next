"""O contrato com o provedor de IA, em primitivos.

`PedidoIA` → `RespostaIA`. As **instruções** são fixas e versionadas no código de quem usa
(nada vindo de pessoa, anexo ou registro entra como instrução); tudo o mais vai em
`BlocoDeDados`, que o adaptador envolve como dado citado (ver `protecao.envolver`). A saída é
sempre um JSON validado contra `esquema` — o que não valida é falha, com o caminho
determinístico de quem chamou.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class Origem(StrEnum):
    SIMULADO = "simulado"    # determinístico, sem rede
    GRAVADO = "gravado"      # respostas gravadas (testes)
    ANTHROPIC = "anthropic"  # provedor real


@dataclass(frozen=True)
class BlocoDeDados:
    """Um pedaço de dado do sistema, sempre tratado como DADO (nunca instrução)."""

    rotulo: str        # "fatos", "relato_do_servidor", "texto_da_programacao"
    conteudo: str
    origem: str = ""   # de onde veio ("Ofício · motivo", "texto colado pela pessoa")


@dataclass(frozen=True)
class PedidoIA:
    uso: str                                 # chave do uso (métrica; nunca conteúdo)
    instrucoes: str                          # fixas e versionadas
    versao_prompt: str
    dados: tuple[BlocoDeDados, ...]
    esquema: dict[str, Any]                  # JSON Schema da saída
    max_tokens_saida: int = 1500
    tempo_limite_s: float = 30.0
    contem_documento: bool = False           # texto extraído de arquivo (ADR 0041)
    resposta_simulada: dict[str, Any] | None = None  # o que o adaptador simulado devolve
    simular: str = ""                        # ensaio de falha no simulado (testes/tela)


@dataclass(frozen=True)
class RespostaIA:
    dados: dict[str, Any]
    texto_bruto: str
    modelo: str
    origem: Origem
    tokens_entrada: int = 0
    tokens_saida: int = 0
    tokens_cache_lidos: int = 0
    duracao_ms: int = 0
    id_requisicao: str = ""
    motivo_parada: str = ""
    tokens_estimados: bool = False           # contagem local (simulado), não do provedor
    extras: dict[str, Any] = field(default_factory=dict)


class PortaIA(Protocol):
    origem: Origem
    modelo: str
    #: o adaptador pode receber texto extraído de documento? (o real: nunca — ADR 0041)
    aceita_documentos: bool

    def gerar(self, pedido: PedidoIA) -> RespostaIA: ...
