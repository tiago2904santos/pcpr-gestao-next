"""Escolha do adaptador, execução com limites e diagnóstico seguro (sem segredo).

`executar` aplica, nesta ordem: teto de entrada (caracteres e tokens estimados), política de
documentos (ADR 0041), tentativas só para falha temporária (com espera curta), tempo-limite
por chamada e validação da saída contra o esquema. Nunca levanta: devolve `Execucao`, com
`ok=False` e o código do motivo — quem chamou segue pelo caminho determinístico.

Custos são sempre **estimados** (tokens × tabela de preços): nunca "cobrados".
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from . import config as cfg
from . import esquema as esq
from .adaptadores import AdaptadorAnthropic, AdaptadorSimulado
from .erros import (
    BloqueadoPorPolitica,
    ErroIA,
    FalhaTemporaria,
    ProvedorIndisponivel,
    SaidaInvalida,
)
from .porta import Origem, PedidoIA, PortaIA, RespostaIA
from .protecao import envolver, estimar_tokens, hash_do_contexto


@dataclass(frozen=True)
class Limites:
    max_entrada_caracteres: int = 24_000
    max_tokens_saida: int = 1500
    tempo_limite_s: float = 30.0
    max_tentativas: int = 2


@dataclass(frozen=True)
class Execucao:
    ok: bool
    dados: dict[str, Any] | None
    resposta: RespostaIA | None
    erro_codigo: str
    erro: str
    tentativas: int
    hash_contexto: str
    tokens_entrada: int
    tokens_saida: int
    custo_estimado: Decimal
    modelo: str
    origem: str


def adaptador(configuracao: cfg.Configuracao | None = None) -> PortaIA:
    """Anthropic só com modo real configurado e fora do PREVIEW; senão, simulado."""
    configuracao = configuracao or cfg.carregar()
    if configuracao.real:
        return AdaptadorAnthropic(configuracao)
    return AdaptadorSimulado()


def tokens_de_entrada(pedido: PedidoIA) -> int:
    return estimar_tokens(pedido.instrucoes + envolver(pedido.dados))


def custo_maximo(pedido: PedidoIA, porta: PortaIA) -> Decimal:
    """O pior caso de UMA chamada (entrada estimada + todo o teto de saída): é o que se
    reserva do orçamento antes de chamar."""
    if porta.origem == Origem.SIMULADO:
        return Decimal(0)
    entrada, saida = tokens_de_entrada(pedido), pedido.max_tokens_saida
    configuracao = getattr(porta, "c", None)
    if getattr(configuracao, "fallback_no_servidor", False):
        # Com o fallback no servidor, a resposta pode vir de outro modelo (e a liquidação
        # usa o preço dele): reservar pelo mais caro da tabela, nunca pelo principal.
        return max(cfg.custo_estimado(m, entrada, saida) for m in cfg.PRECOS)
    return cfg.custo_estimado(porta.modelo, entrada, saida)


def executar(pedido: PedidoIA, porta: PortaIA, limites: Limites | None = None, *,
             dormir: Callable[[float], None] = time.sleep) -> Execucao:
    limites = limites or Limites()
    pedido = PedidoIA(**{**pedido.__dict__,
                         "max_tokens_saida": min(pedido.max_tokens_saida,
                                                 limites.max_tokens_saida),
                         "tempo_limite_s": min(pedido.tempo_limite_s, limites.tempo_limite_s)})
    hash_ctx = hash_do_contexto(pedido.instrucoes, pedido.dados, pedido.esquema)
    simulado = porta.origem == Origem.SIMULADO

    def falha(codigo: str, mensagem: str, tentativas: int, custo: Decimal) -> Execucao:
        return Execucao(False, None, None, codigo, mensagem, tentativas, hash_ctx, 0, 0,
                        custo, porta.modelo, str(porta.origem))

    mensagem = pedido.instrucoes + envolver(pedido.dados)
    if len(mensagem) > limites.max_entrada_caracteres:
        return falha("entrada_grande", "A entrada passa do limite deste uso.", 0, Decimal(0))
    if pedido.contem_documento and not porta.aceita_documentos:
        return falha("documento", "Texto de documento não vai a provedor externo de IA "
                                  "(ADR 0041).", 0, Decimal(0))
    custo_falhas = Decimal(0)
    tentativa = 0
    resposta: RespostaIA | None = None
    while tentativa < max(1, limites.max_tentativas):
        tentativa += 1
        try:
            resposta = porta.gerar(pedido)
            break
        except FalhaTemporaria as erro:
            # Conexão recusada não chegou ao provedor; o resto pode ter consumido tokens.
            if not (isinstance(erro, ProvedorIndisponivel) and erro.codigo == "conexao") \
                    and not simulado:
                custo_falhas += custo_maximo(pedido, porta)
            if tentativa >= limites.max_tentativas:
                return falha(erro.codigo, str(erro), tentativa, custo_falhas)
            dormir(min(float(erro.espera_segundos or 1), 5.0))
        except BloqueadoPorPolitica as erro:
            return falha(erro.codigo, str(erro), tentativa, custo_falhas)
        except ErroIA as erro:
            if not simulado:
                custo_falhas += custo_maximo(pedido, porta)
            return falha(erro.codigo, str(erro), tentativa, custo_falhas)
    if resposta is None:  # pragma: no cover — o laço sempre devolve ou quebra
        return falha("sem_resposta", "Sem resposta do provedor.", tentativa, custo_falhas)
    custo = (Decimal(0) if simulado else cfg.custo_estimado(
        resposta.modelo, resposta.tokens_entrada, resposta.tokens_saida,
        resposta.tokens_cache_lidos)) + custo_falhas
    erros = esq.validar(resposta.dados, pedido.esquema)
    if erros:
        invalida = SaidaInvalida("A resposta não segue o esquema: " + "; ".join(erros[:3]),
                                 "esquema")
        return Execucao(False, None, resposta, invalida.codigo, str(invalida), tentativa,
                        hash_ctx,
                        resposta.tokens_entrada, resposta.tokens_saida, custo,
                        resposta.modelo, str(resposta.origem))
    return Execucao(True, resposta.dados, resposta, "", "", tentativa, hash_ctx,
                    resposta.tokens_entrada, resposta.tokens_saida, custo, resposta.modelo,
                    str(resposta.origem))


def diagnostico() -> dict[str, object]:
    """Resumo para a tela de configuração e o comando `ia_check` — nunca o segredo."""
    c = cfg.carregar()
    preco = cfg.preco_de(c.modelo)
    return {
        "modo": c.modo,
        "estado": c.descricao(),
        "modo_real": c.real,
        "modelo": c.modelo,
        "preco_estimado": (f"US$ {preco.entrada} entrada / US$ {preco.saida} saída por milhão "
                           "de tokens" if preco else "fora da tabela (estima pelo mais caro)"),
        "api_key": "configurada" if c.api_key else "(não configurada)",
        "base_url": c.base_url,
        "timeout": c.timeout,
        "max_tentativas": c.max_tentativas,
        "max_tokens_saida": c.max_tokens_saida,
        "limite_entrada_caracteres": c.limite_entrada_caracteres,
        "esforco": c.esforco,
        "documentos_ao_provedor_real": "bloqueados (ADR 0041)",
        "faltam_para_real": c.faltantes() if c.modo == cfg.ANTHROPIC else [],
        "bloqueado_no_ambiente": c.bloqueado_no_ambiente,
    }
