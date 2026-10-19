"""Adaptadores da porta do WhatsApp: simulado (padrão) e Cloud API (Meta, oficial).

O simulado não usa rede: devolve um wamid determinístico (`wamid.SIM.…`) e lê a mídia que o
simulador da tela guardou no armazenamento (`automacao/simulador/<id>`). Ele também ensaia
as falhas (temporária, definitiva, incerta) quando a mensagem pede (`simular`), para a fila
de exceções poder ser exercitada sem a Meta.

O da Cloud API segue a referência (docs/integrations/whatsapp-cloud-api-referencia.md):
versão fixa, `appsecret_proof` em toda chamada, `biz_opaque_callback_data` com o id interno,
erros classificados pelo `code`, mídia baixada só de hosts da Meta (o Bearer nunca vai para
outro endereço) e conferida pelo tamanho, tipo e sha256 (base64 ou hex).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from typing import Any

from .config import BASE_URL, Configuracao
from .erros import (
    BLOQUEIO_DE_CONTA,
    FORA_DA_JANELA,
    TEMPORARIOS,
    CanalBloqueado,
    ConfiguracaoIncompleta,
    FalhaDefinitiva,
    FalhaTemporaria,
    MidiaInvalida,
    ResultadoIncerto,
)
from .porta import Anexo, Envio, MensagemSaida, MidiaBaixada, Origem
from .transporte import NaoEnviado, Resposta, TalvezEnviado, Transporte, transporte_https

log = logging.getLogger("gestao.integracoes.whatsapp")

LIMITE_RESPOSTA = 256 * 1024
#: Bytes mágicos dos tipos aceitos como documento recebido.
ASSINATURAS = {
    "application/pdf": (b"%PDF-",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}
HOSTS_DE_MIDIA = ("fbsbx.com", "facebook.com", "fbcdn.net", "whatsapp.net")
PREFIXO_SIMULADO = "automacao/simulador/"


def tipo_pelos_bytes(conteudo: bytes) -> str:
    """O tipo real do arquivo pelos primeiros bytes (o que a pessoa diz que é não vale)."""
    for mime, assinaturas in ASSINATURAS.items():
        if any(conteudo.startswith(a) for a in assinaturas):
            return mime
    return ""


def conferir_sha256(conteudo: bytes, informado: str) -> str:
    """Devolve o hex; levanta MidiaInvalida se o hash informado (base64 ou hex) não bate."""
    real = hashlib.sha256(conteudo).hexdigest()
    informado = (informado or "").strip()
    if not informado:
        return real
    if len(informado) == 64 and all(c in "0123456789abcdefABCDEF" for c in informado):
        esperado = informado.lower()
    else:
        try:
            esperado = base64.b64decode(informado, validate=True).hex()
        except (binascii.Error, ValueError):
            raise MidiaInvalida("Hash do arquivo em formato desconhecido.", "hash") from None
    if not hmac.compare_digest(real, esperado):
        raise MidiaInvalida("O arquivo não confere com o hash informado pela Meta.", "hash")
    return real


def _validar_midia(conteudo: bytes, limite: int, informado: str) -> MidiaBaixada:
    if len(conteudo) > limite:
        raise MidiaInvalida(f"Arquivo acima de {limite // (1024 * 1024)} MB.", "grande")
    if not conteudo:
        raise MidiaInvalida("Arquivo vazio.", "vazio")
    mime = tipo_pelos_bytes(conteudo)
    if not mime:
        raise MidiaInvalida("Tipo de arquivo não aceito: envie PDF, JPG ou PNG.", "tipo")
    return MidiaBaixada(conteudo=conteudo, mime=mime, sha256_hex=conferir_sha256(conteudo,
                                                                                 informado))


# ------------------------------------------------------------------- simulado
class AdaptadorSimulado:
    """Sem rede. O wamid é determinístico pela referência (mesma tentativa → mesmo id)."""

    origem = Origem.SIMULADO

    def enviar(self, mensagem: MensagemSaida, simular: str = "") -> Envio:
        if not mensagem.para.isdigit() or not 10 <= len(mensagem.para) <= 15:
            raise FalhaDefinitiva("Número em formato inválido.", "100")
        if simular == "temporaria":
            raise FalhaTemporaria("Falha temporária simulada (limite de vazão).", "130429")
        if simular == "definitiva":
            raise FalhaDefinitiva("Falha definitiva simulada (número sem WhatsApp).", "131026")
        if simular == "incerta":
            raise ResultadoIncerto("Resultado incerto simulado (tempo esgotado).", "tempo")
        semente = hashlib.sha256(mensagem.referencia.encode()).hexdigest()[:32].upper()
        return Envio(mensagem_id=f"wamid.SIM.{semente}", wa_id=mensagem.para,
                     origem=Origem.SIMULADO)

    def baixar_midia(self, anexo: Anexo, limite: int) -> MidiaBaixada:
        from django.core.files.storage import default_storage

        caminho = PREFIXO_SIMULADO + "".join(c for c in anexo.midia_id if c.isalnum())
        if not anexo.midia_id or not default_storage.exists(caminho):
            raise MidiaInvalida("Mídia simulada não encontrada (ou já expirada).", "404")
        with default_storage.open(caminho, "rb") as arquivo:
            conteudo = arquivo.read(limite + 1)
        return _validar_midia(conteudo, limite, anexo.sha256)

    def descartar_midia(self, anexo: Anexo) -> None:
        """A mídia simulada é lida uma vez: transferida (ou recusada de vez), sai do
        armazenamento — senão cada simulação deixava o original para sempre."""
        from django.core.files.storage import default_storage

        caminho = PREFIXO_SIMULADO + "".join(c for c in anexo.midia_id if c.isalnum())
        if anexo.midia_id and default_storage.exists(caminho):
            default_storage.delete(caminho)

    def marcar_lida(self, mensagem_id: str) -> None:
        return None


# ------------------------------------------------------------------ Cloud API
def classificar(status: int, dados: dict[str, Any]) -> Exception:
    """Erro da Graph API → exceção do nosso vocabulário (pelo `code`, nunca pelo HTTP)."""
    bruto = dados.get("error")
    erro: dict[str, Any] = bruto if isinstance(bruto, dict) else {}
    codigo = str(erro.get("code") or "")
    detalhe = str((erro.get("error_data") or {}).get("details") or "")[:200]
    if not codigo:
        if status >= 500:
            return ResultadoIncerto(f"A Meta respondeu HTTP {status} sem dizer o erro.",
                                    f"http{status}")
        return FalhaDefinitiva(f"A Meta recusou o pedido (HTTP {status}).", f"http{status}")
    texto = f"Erro {codigo} da Cloud API" + (f": {detalhe}" if detalhe else "")
    if codigo in TEMPORARIOS:
        return FalhaTemporaria(texto, codigo, espera_segundos=60 if codigo == "131056" else None)
    if codigo in BLOQUEIO_DE_CONTA or (codigo.isdigit() and 200 <= int(codigo) <= 299):
        return CanalBloqueado(texto, codigo)
    if codigo == FORA_DA_JANELA:
        return FalhaDefinitiva("Fora da janela de 24 h: só um modelo aprovado pode iniciar a "
                               "conversa.", codigo)
    return FalhaDefinitiva(texto, codigo)


def _json(bruto: bytes) -> dict[str, Any]:
    try:
        dados = json.loads(bruto.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}


class AdaptadorCloudApi:
    origem = Origem.CLOUD_API

    def __init__(self, config: Configuracao, transporte: Transporte | None = None):
        if config.faltantes():
            raise ConfiguracaoIncompleta(
                "Cloud API sem credenciais: faltam " + ", ".join(config.faltantes())
                + " (variáveis WHATSAPP_* no servidor).")
        if config.bloqueado_no_ambiente:
            raise ConfiguracaoIncompleta("O PREVIEW público nunca usa a Cloud API.")
        self.config = config
        self._transporte = transporte or transporte_https
        self._prova = hmac.new(config.app_secret.encode(), config.access_token.encode(),
                               hashlib.sha256).hexdigest()

    def _url(self, caminho: str, **parametros: str) -> str:
        consulta = urllib.parse.urlencode({**parametros, "appsecret_proof": self._prova})
        return f"{BASE_URL}/{self.config.versao}/{caminho}?{consulta}"

    def _chamar(self, metodo: str, url: str, corpo: dict[str, Any] | None, timeout: float,
                limite: int = LIMITE_RESPOSTA) -> Resposta:
        cabecalhos = {"Authorization": f"Bearer {self.config.access_token}",
                      "Accept": "application/json"}
        bruto = None
        if corpo is not None:
            bruto = json.dumps(corpo, ensure_ascii=False).encode()
            cabecalhos["Content-Type"] = "application/json"
        inicio = time.monotonic()
        try:
            resposta = self._transporte(metodo, url, cabecalhos, bruto, timeout, limite)
        finally:
            log.info("whatsapp %s %s em %dms", metodo, urllib.parse.urlsplit(url).path,
                     (time.monotonic() - inicio) * 1000)
        return resposta

    def _corpo(self, m: MensagemSaida) -> dict[str, Any]:
        corpo: dict[str, Any] = {"messaging_product": "whatsapp", "recipient_type": "individual",
                                 "to": f"+{m.para}", "biz_opaque_callback_data": m.referencia}
        if m.modelo is not None:
            componentes = []
            if m.modelo.parametros:
                componentes.append({"type": "body", "parameters": [
                    {"type": "text", "text": p[:1024]} for p in m.modelo.parametros]})
            corpo["type"] = "template"
            corpo["template"] = {"name": m.modelo.nome, "language": {"code": m.modelo.idioma},
                                 "components": componentes}
        else:
            corpo["type"] = "text"
            corpo["text"] = {"preview_url": False, "body": m.texto[:4096]}
        if m.responder_a:
            corpo["context"] = {"message_id": m.responder_a}
        return corpo

    def enviar(self, mensagem: MensagemSaida, simular: str = "") -> Envio:
        url = self._url(f"{self.config.phone_number_id}/messages")
        try:
            resposta = self._chamar("POST", url, self._corpo(mensagem), self.config.timeout_envio)
        except NaoEnviado as erro:
            raise FalhaTemporaria("Sem conexão com a Meta (o pedido não saiu).", "rede") from erro
        except TalvezEnviado as erro:
            raise ResultadoIncerto("A conexão caiu esperando a Meta: não dá para saber se a "
                                   "mensagem saiu.", "tempo") from erro
        dados = _json(resposta.corpo)
        if resposta.status >= 400 or "error" in dados:
            raise classificar(resposta.status, dados)
        mensagens = dados.get("messages") if isinstance(dados.get("messages"), list) else []
        primeira = mensagens[0] if mensagens and isinstance(mensagens[0], dict) else {}
        mensagem_id = str(primeira.get("id") or "")
        if not mensagem_id:
            raise ResultadoIncerto("A Meta respondeu sem o id da mensagem.", "sem_id")
        if len(mensagem_id) > 300:  # o teto dos modelos e do contrato; cortar casaria errado
            raise ResultadoIncerto("A Meta respondeu um id de mensagem fora do formato.",
                                   "id_longo")
        contatos = dados.get("contacts") if isinstance(dados.get("contacts"), list) else []
        contato = contatos[0] if contatos and isinstance(contatos[0], dict) else {}
        return Envio(mensagem_id=mensagem_id, wa_id=str(contato.get("wa_id") or "")[:20],
                     usuario_id=str(contato.get("user_id") or "")[:140],
                     situacao=str(primeira.get("message_status") or "accepted")[:40],
                     origem=Origem.CLOUD_API)

    def _url_de_midia(self, anexo: Anexo) -> tuple[str, str, int | None]:
        url = self._url(anexo.midia_id, phone_number_id=self.config.phone_number_id)
        try:
            resposta = self._chamar("GET", url, None, self.config.timeout_envio)
        except (NaoEnviado, TalvezEnviado) as erro:
            raise FalhaTemporaria("Sem conexão com a Meta para buscar a mídia.", "rede") from erro
        dados = _json(resposta.corpo)
        if resposta.status >= 400 or "error" in dados:
            erro_meta = classificar(resposta.status, dados)
            if isinstance(erro_meta, ResultadoIncerto):  # consulta: repetir é seguro
                raise FalhaTemporaria(str(erro_meta), erro_meta.codigo)
            raise erro_meta
        tamanho = str(dados.get("file_size") or "")
        return (str(dados.get("url") or ""), str(dados.get("sha256") or anexo.sha256),
                int(tamanho) if tamanho.isdigit() else None)

    def baixar_midia(self, anexo: Anexo, limite: int) -> MidiaBaixada:
        if not anexo.midia_id or not anexo.midia_id.isalnum():
            raise MidiaInvalida("Id de mídia inválido.", "id")
        url, sha, tamanho = self._url_de_midia(anexo)
        for tentativa in (1, 2):
            if tamanho is not None and tamanho > limite:
                raise MidiaInvalida(f"Arquivo acima de {limite // (1024 * 1024)} MB.", "grande")
            partes = urllib.parse.urlsplit(url)
            host = (partes.hostname or "").lower()
            if partes.scheme != "https" or not any(host == h or host.endswith("." + h)
                                                   for h in HOSTS_DE_MIDIA):
                raise MidiaInvalida("Endereço de mídia fora dos domínios da Meta.", "host")
            try:
                resposta = self._transporte("GET", url, {
                    "Authorization": f"Bearer {self.config.access_token}"}, None,
                    self.config.timeout_midia, limite)
            except (NaoEnviado, TalvezEnviado) as erro:
                raise FalhaTemporaria("A mídia não chegou da Meta.", "rede") from erro
            if resposta.status >= 400:
                # Token ou conta recusados entre a consulta e o download (190, 131031…): o
                # corpo diz o código, e o canal tem de bloquear como no envio.
                dados = _json(resposta.corpo)
                if "error" in dados:
                    erro_meta = classificar(resposta.status, dados)
                    if isinstance(erro_meta, CanalBloqueado):
                        raise erro_meta
            if resposta.status == 404 and tentativa == 1:  # URL vencida (vale 5 min): pede outra
                url, sha, tamanho = self._url_de_midia(anexo)
                continue
            if resposta.status >= 400:
                raise FalhaTemporaria(f"Download da mídia recusado (HTTP {resposta.status}).",
                                      f"http{resposta.status}")
            if resposta.truncada:
                raise MidiaInvalida(f"Arquivo acima de {limite // (1024 * 1024)} MB.", "grande")
            return _validar_midia(resposta.corpo, limite, sha)
        raise FalhaTemporaria("A mídia não está mais disponível na Meta.", "404")

    def marcar_lida(self, mensagem_id: str) -> None:
        url = self._url(f"{self.config.phone_number_id}/messages")
        try:
            self._chamar("POST", url, {"messaging_product": "whatsapp", "status": "read",
                                       "message_id": mensagem_id}, self.config.timeout_envio)
        except (NaoEnviado, TalvezEnviado):
            log.info("whatsapp: confirmação de leitura não saiu (sem efeito para o fluxo)")
