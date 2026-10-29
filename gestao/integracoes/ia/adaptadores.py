"""Adaptadores da porta de IA: simulado (padrão), gravado (testes) e Anthropic (real).

- **Simulado:** sem rede e sem custo. Devolve a `resposta_simulada` que quem pediu montou
  pelo caminho determinístico (regra/modelo de texto) e conta os tokens localmente — assim o
  fluxo inteiro (limites, orçamento, validação, revisão humana) roda no PREVIEW e nos testes.
  Ensaia falhas quando o pedido traz `simular` (`indisponivel`, `taxa`, `tempo`, `recusa`,
  `invalida`).
- **Gravado:** devolve, na ordem, respostas gravadas (dicts ou exceções) — testes
  determinísticos do caminho de IA sem provedor.
- **Anthropic:** Messages API por HTTPS (`POST /v1/messages`), saída estruturada por JSON
  Schema (`output_config.format`), esforço baixo, sem ferramentas. Recusa por política o
  pedido com texto de documento (ADR 0041: nada de documento a IA externa) e nunca carrega no
  PREVIEW. Logs sem texto do pedido nem da resposta: só uso, modelo, tokens, duração e código.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from . import config as cfg
from . import esquema as esq
from .erros import (
    BloqueadoPorPolitica,
    ConfiguracaoIncompleta,
    FalhaDefinitiva,
    LimiteDeTaxa,
    ProvedorIndisponivel,
    Recusa,
    SaidaInvalida,
    TempoEsgotado,
)
from .porta import Origem, PedidoIA, RespostaIA
from .protecao import envolver, estimar_tokens
from .transporte import NaoEnviado, TalvezEnviado, Transporte, transporte_https

log = logging.getLogger("gestao.integracoes.ia")

LIMITE_RESPOSTA = 512 * 1024
MODELO_SIMULADO = "simulado-deterministico"


def _ensaiar_falha(simular: str) -> None:
    if simular == "indisponivel":
        raise ProvedorIndisponivel("Provedor de IA indisponível (simulado).", "529")
    if simular == "taxa":
        raise LimiteDeTaxa("Limite de taxa do provedor (simulado).", "429", espera_segundos=1)
    if simular == "tempo":
        raise TempoEsgotado("Tempo esgotado esperando o provedor (simulado).", "tempo")
    if simular == "recusa":
        raise Recusa("O modelo declinou o pedido (simulado).", "refusal")


# ------------------------------------------------------------------ simulado
class AdaptadorSimulado:
    origem = Origem.SIMULADO
    modelo = MODELO_SIMULADO
    aceita_documentos = True  # nada sai do servidor

    def gerar(self, pedido: PedidoIA) -> RespostaIA:
        inicio = time.monotonic()
        _ensaiar_falha(pedido.simular)
        if pedido.simular == "invalida" or pedido.resposta_simulada is None:
            texto = '{"resposta": "fora do esquema"}'
        else:
            texto = json.dumps(pedido.resposta_simulada, ensure_ascii=False)
        dados = json.loads(texto)
        entrada = estimar_tokens(pedido.instrucoes + envolver(pedido.dados))
        return RespostaIA(dados=dados, texto_bruto=texto, modelo=self.modelo,
                          origem=self.origem, tokens_entrada=entrada,
                          tokens_saida=estimar_tokens(texto),
                          duracao_ms=int((time.monotonic() - inicio) * 1000),
                          motivo_parada="end_turn", tokens_estimados=True)


# ------------------------------------------------------------------ gravado
class AdaptadorGravado:
    """Cada item: dict (o JSON da resposta) ou exceção. `modelo` define o preço estimado."""

    origem = Origem.GRAVADO
    aceita_documentos = True

    def __init__(self, respostas: list[dict | str | Exception], modelo: str = cfg.MODELO_PADRAO,
                 tokens: tuple[int, int] = (1200, 400)):
        self.respostas = list(respostas)
        self.modelo = modelo
        self.tokens = tokens
        self.pedidos: list[PedidoIA] = []

    def gerar(self, pedido: PedidoIA) -> RespostaIA:
        self.pedidos.append(pedido)
        if not self.respostas:
            raise AssertionError("Chamada à IA sem resposta gravada.")
        item = self.respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        texto = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        try:
            dados = json.loads(texto)
        except ValueError as erro:
            raise SaidaInvalida("A resposta gravada não é JSON.", "json") from erro
        if not isinstance(dados, dict):
            raise SaidaInvalida("A resposta não é um objeto JSON.", "json")
        return RespostaIA(dados=dados, texto_bruto=texto, modelo=self.modelo, origem=self.origem,
                          tokens_entrada=self.tokens[0], tokens_saida=self.tokens[1],
                          motivo_parada="end_turn")


# ------------------------------------------------------------------ Anthropic
class AdaptadorAnthropic:
    origem = Origem.ANTHROPIC
    aceita_documentos = False  # ADR 0041 — só uma ADR nova muda isto

    def __init__(self, configuracao: cfg.Configuracao, transporte: Transporte | None = None):
        if not configuracao.api_key:
            raise ConfiguracaoIncompleta("Falta a chave do provedor de IA (IA_API_KEY).")
        if configuracao.bloqueado_no_ambiente:
            raise BloqueadoPorPolitica("O PREVIEW público nunca chama um provedor de IA.",
                                       "preview")
        self.c = configuracao
        self.modelo = configuracao.modelo
        self._transporte = transporte or transporte_https

    def corpo(self, pedido: PedidoIA) -> dict[str, Any]:
        corpo: dict[str, Any] = {
            "model": self.modelo,
            "max_tokens": min(pedido.max_tokens_saida, self.c.max_tokens_saida),
            "system": pedido.instrucoes,
            "messages": [{"role": "user", "content": envolver(pedido.dados)}],
            "output_config": {
                "effort": self.c.esforco,
                "format": {"type": "json_schema", "schema": esq.para_api(pedido.esquema)},
            },
        }
        if self.c.fallback_no_servidor:
            corpo["fallbacks"] = "default"
        return corpo

    def cabecalhos(self) -> dict[str, str]:
        c = {"content-type": "application/json", "x-api-key": self.c.api_key,
             "anthropic-version": cfg.VERSAO_API}
        if self.c.fallback_no_servidor:
            c["anthropic-beta"] = cfg.BETA_FALLBACK
        return c

    def gerar(self, pedido: PedidoIA) -> RespostaIA:
        if pedido.contem_documento:
            raise BloqueadoPorPolitica(
                "Texto de documento não vai a provedor externo de IA (ADR 0041).", "documento")
        corpo = json.dumps(self.corpo(pedido), ensure_ascii=False).encode()
        inicio = time.monotonic()
        timeout = min(pedido.tempo_limite_s, self.c.timeout)
        try:
            resposta = self._transporte("POST", f"{self.c.base_url}/v1/messages",
                                        self.cabecalhos(), corpo, timeout, LIMITE_RESPOSTA)
        except NaoEnviado as erro:
            raise ProvedorIndisponivel("Sem conexão com o provedor de IA.", "conexao") from erro
        except TalvezEnviado as erro:
            raise TempoEsgotado("O provedor de IA não respondeu a tempo.", "tempo") from erro
        duracao = int((time.monotonic() - inicio) * 1000)
        id_req = resposta.cabecalhos.get("request-id", "")
        log.info("ia uso=%s modelo=%s status=%s ms=%s req=%s", pedido.uso, self.modelo,
                 resposta.status, duracao, id_req)
        dados = _json(resposta.corpo)
        if resposta.status >= 400:
            _erro_http(resposta.status, dados, resposta.cabecalhos)
        if resposta.truncada:
            raise SaidaInvalida("Resposta do provedor grande demais.", "truncada")
        return _ler(dados, pedido, self.modelo, duracao, id_req)


def _json(corpo: bytes) -> dict:
    try:
        dados = json.loads(corpo or b"{}")
    except ValueError:
        return {}
    return dados if isinstance(dados, dict) else {}


def _erro_http(status: int, dados: dict, cabecalhos: dict[str, str]) -> None:
    tipo = str((dados.get("error") or {}).get("type") or status)
    if status == 429:
        try:
            espera = int(cabecalhos.get("retry-after", "30"))
        except ValueError:
            espera = 30
        raise LimiteDeTaxa("Limite de taxa do provedor de IA.", tipo, espera_segundos=espera)
    if status in (408, 504):
        raise TempoEsgotado("O provedor de IA não respondeu a tempo.", tipo)
    if status >= 500:  # inclui 529 (overloaded_error)
        raise ProvedorIndisponivel("Provedor de IA indisponível.", tipo)
    if status in (401, 403):
        raise ConfiguracaoIncompleta("Credencial do provedor de IA recusada.", tipo)
    raise FalhaDefinitiva(f"O provedor de IA recusou o pedido ({status}).", tipo)


def _ler(dados: dict, pedido: PedidoIA, modelo: str, duracao: int, id_req: str) -> RespostaIA:
    parada = str(dados.get("stop_reason") or "")
    if parada == "refusal":
        raise Recusa("O modelo declinou o pedido.", "refusal")
    if parada == "max_tokens":
        raise SaidaInvalida("A resposta passou do limite de tokens de saída.", "max_tokens")
    texto = "".join(b.get("text", "") for b in dados.get("content") or []
                    if isinstance(b, dict) and b.get("type") == "text").strip()
    try:
        saida = json.loads(texto)
    except ValueError as erro:
        raise SaidaInvalida("A resposta não é JSON.", "json") from erro
    if not isinstance(saida, dict):
        raise SaidaInvalida("A resposta não é um objeto JSON.", "json")
    uso = dados.get("usage") or {}
    return RespostaIA(
        dados=saida, texto_bruto=texto, modelo=str(dados.get("model") or modelo),
        origem=Origem.ANTHROPIC,
        # Escrita em cache custa 1,25× a entrada: entra assim na conta, para não subestimar.
        tokens_entrada=int(uso.get("input_tokens") or 0)
        + -(-int(uso.get("cache_creation_input_tokens") or 0) * 5 // 4),
        tokens_saida=int(uso.get("output_tokens") or 0),
        tokens_cache_lidos=int(uso.get("cache_read_input_tokens") or 0),
        duracao_ms=duracao, id_requisicao=id_req, motivo_parada=parada)
