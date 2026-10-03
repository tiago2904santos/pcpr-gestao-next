"""Adaptadores da porta do eProtocolo: simulado (padrão) e HTTP.

O HTTP segue a documentação oficial pública (docs/integrations/eprotocolo.md):
- token na Central de Segurança, fluxo `client_credentials`, credenciais em
  `Authorization: Basic base64(clientId:secretId)` e `scope` na requisição;
- consulta em `<base>/v3/protocolos/{protocolo}` (exemplo de composição de URL da doc).
O nome do cabeçalho do `consumerId`, o caminho de abertura e o formato das respostas não
estão na parte pública: ficam configuráveis/"a conferir" até o acesso ao treinamento.
O transporte é injetável para os testes nunca tocarem a rede.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .config import Configuracao
from .erros import ConfiguracaoIncompleta, EscritaBloqueada, Indisponivel, NaoEncontrado, Recusado
from .porta import Movimentacao, Origem, PedidoDeAbertura, ProtocoloAberto, Situacao

log = logging.getLogger("gestao.integracoes.eprotocolo")

#: (método, url, cabeçalhos, corpo, timeout) -> (status, corpo)
Transporte = Callable[[str, str, dict[str, str], bytes | None, float], tuple[int, bytes]]

CABECALHO_CONSUMER = "consumerId"  # a confirmar na documentação restrita
CAMINHO_CONSULTA = "/v3/protocolos/{numero}"


def somente_digitos(texto: str) -> str:
    return "".join(c for c in (texto or "") if c.isdigit())


# ------------------------------------------------------------------- simulado
class AdaptadorSimulado:
    """Sem rede. Números no formato certo, sempre marcados SIMULADO (não valem)."""

    origem = Origem.SIMULADO

    def autenticar(self) -> None:
        return None

    def consultar(self, numero: str) -> Situacao:
        digitos = somente_digitos(numero)
        if len(digitos) != 9:
            raise NaoEncontrado("O protocolo tem 9 dígitos.", 404)
        return Situacao(numero=digitos, situacao="Simulado — sem consulta real",
                        local_atual="", origem=Origem.SIMULADO,
                        movimentacoes=(Movimentacao(None, "Consulta simulada: a integração "
                                                    "real ainda não está configurada."),))

    def abrir(self, pedido: PedidoDeAbertura) -> ProtocoloAberto:
        # Determinístico pela chave: repetir o pedido devolve o mesmo número (idempotente).
        semente = int(hashlib.sha256(pedido.chave.encode()).hexdigest(), 16)
        return ProtocoloAberto(numero=f"{semente % 10**9:09d}", origem=Origem.SIMULADO)


# ----------------------------------------------------------------------- http
class _SemRedirecionar(urllib.request.HTTPRedirectHandler):
    """Redirecionamento vira erro: seguir um 3xx reenviaria Authorization (Basic/Bearer) e o
    consumerId para outro endereço — talvez sem TLS."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


LIMITE_RESPOSTA = 2 * 1024 * 1024  # 2 MB: resposta maior que isso não é de consulta


def transporte_urllib(metodo: str, url: str, cabecalhos: dict[str, str], corpo: bytes | None,
                      timeout: float) -> tuple[int, bytes]:
    """HTTPS com verificação de certificado sempre ligada e sem redirecionamentos."""
    import ssl

    if urllib.parse.urlsplit(url).scheme != "https":
        raise ConfiguracaoIncompleta("O eProtocolo só é chamado por HTTPS.")
    abridor = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()), _SemRedirecionar())
    pedido = urllib.request.Request(url, data=corpo, headers=cabecalhos, method=metodo)  # noqa: S310
    try:
        with abridor.open(pedido, timeout=timeout) as r:  # nosec B310 — só https (acima)
            return r.status, r.read(LIMITE_RESPOSTA)
    except urllib.error.HTTPError as erro:
        return erro.code, erro.read() or b""
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise Indisponivel("O eProtocolo não respondeu. Tente de novo em alguns minutos.") from erro


@dataclass
class _Token:
    valor: str = ""
    expira: float = 0.0


class AdaptadorHttp:
    def __init__(self, config: Configuracao, transporte: Transporte | None = None,
                 relogio: Callable[[], float] = time.monotonic):
        if config.faltantes():
            raise ConfiguracaoIncompleta(
                "Integração com o eProtocolo sem credenciais: faltam "
                + ", ".join(config.faltantes()) + " (variáveis EPROTOCOLO_* no servidor).")
        self.config = config
        self.base, self.token_url = config.urls()
        if not (self.base and self.token_url):
            raise ConfiguracaoIncompleta("Informe EPROTOCOLO_BASE_URL e EPROTOCOLO_TOKEN_URL "
                                         f"para o ambiente {config.ambiente}.")
        if any(urllib.parse.urlsplit(u).scheme != "https" for u in (self.base, self.token_url)):
            raise ConfiguracaoIncompleta("As URLs do eProtocolo precisam ser https://: as "
                                         "credenciais nunca trafegam sem TLS.")
        self._transporte = transporte or transporte_urllib
        self._relogio = relogio
        self._token = _Token()
        self.origem = Origem.EPROTOCOLO if config.oficial else Origem.TREINAMENTO

    # -- autenticação ----------------------------------------------------------
    def _obter_token(self) -> str:
        if self._token.valor and self._relogio() < self._token.expira:
            return self._token.valor
        credencial = base64.b64encode(
            f"{self.config.client_id}:{self.config.client_secret}".encode()).decode()
        corpo = urllib.parse.urlencode({"grant_type": "client_credentials",
                                        "scope": " ".join(self.config.escopos)}).encode()
        status, bruto = self._chamar("POST", self.token_url, {
            "Authorization": f"Basic {credencial}",
            "Content-Type": "application/x-www-form-urlencoded"}, corpo, autenticado=False)
        dados = _json(bruto)
        if status >= 400 or not dados.get("access_token"):
            raise Recusado("A Central de Segurança recusou as credenciais do eProtocolo "
                           f"(HTTP {status}). Confira client id, secret e escopos.", status)
        # Renova um pouco antes de vencer.
        self._token = _Token(str(dados["access_token"]),
                             self._relogio() + max(30, int(dados.get("expires_in") or 300) - 30))
        return self._token.valor

    def autenticar(self) -> None:
        self._obter_token()

    # -- chamadas --------------------------------------------------------------
    def _chamar(self, metodo: str, url: str, cabecalhos: dict[str, str], corpo: bytes | None,
                *, autenticado: bool = True) -> tuple[int, bytes]:
        if autenticado:
            cabecalhos = {"Authorization": f"Bearer {self._obter_token()}",
                          CABECALHO_CONSUMER: self.config.consumer_id,
                          "Accept": "application/json", **cabecalhos}
        inicio = time.monotonic()
        status, bruto = self._transporte(metodo, url, cabecalhos, corpo, self.config.timeout)
        log.info("eprotocolo %s %s -> %s em %dms", metodo,
                 urllib.parse.urlsplit(url).path, status, (time.monotonic() - inicio) * 1000)
        if status >= 500:
            raise Indisponivel(f"O eProtocolo está com problemas (HTTP {status}). "
                               "Tente de novo em alguns minutos.")
        return status, bruto

    def consultar(self, numero: str) -> Situacao:
        digitos = somente_digitos(numero)
        if len(digitos) != 9:
            raise NaoEncontrado("O protocolo tem 9 dígitos.", 404)
        status, bruto = self._chamar("GET", self.base + CAMINHO_CONSULTA.format(numero=digitos),
                                     {}, None)
        if status == 404:
            raise NaoEncontrado(f"Protocolo {digitos} não encontrado no eProtocolo.", 404)
        if status >= 400:
            raise Recusado(f"O eProtocolo recusou a consulta (HTTP {status}). Confira o "
                           "escopo spiserv.protocolos.consultar e o IP autorizado.", status)
        return _situacao(digitos, _json(bruto), self.origem)

    def abrir(self, pedido: PedidoDeAbertura) -> ProtocoloAberto:
        if not self.config.escrita_liberada:
            raise EscritaBloqueada("A integração está em somente consulta: abrir protocolo "
                                   "exige EPROTOCOLO_SOMENTE_LEITURA=false.")
        faltam = self.config.faltantes_para_abrir()
        if faltam:
            raise ConfiguracaoIncompleta("Faltam códigos institucionais para abrir processo: "
                                         + ", ".join(faltam) + ".")
        # O caminho e o corpo da abertura não estão na documentação pública.
        raise ConfiguracaoIncompleta("Abertura de protocolo ainda não confirmada na "
                                     "documentação oficial do eProtocolo (fase E4).")


def _json(bruto: bytes) -> dict[str, Any]:
    try:
        dados = json.loads(bruto.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _data(valor: Any) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None


def _situacao(numero: str, dados: dict[str, Any], origem: Origem) -> Situacao:
    """Mapeamento tolerante (formato real a conferir no treinamento)."""
    movs = []
    for m in dados.get("movimentacoes") or dados.get("tramitacoes") or []:
        if isinstance(m, dict):
            movs.append(Movimentacao(_data(m.get("data") or m.get("dataHora")),
                                     str(m.get("descricao") or m.get("despacho") or ""),
                                     str(m.get("local") or m.get("localDestino") or "")))
    return Situacao(numero=numero,
                    situacao=str(dados.get("situacao") or dados.get("status") or "Sem situação"),
                    local_atual=str(dados.get("localAtual") or dados.get("local") or ""),
                    movimentacoes=tuple(movs), origem=origem)
