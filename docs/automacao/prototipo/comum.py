"""Utilitários compartilhados pelos simuladores (somente biblioteca padrão)."""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import re
import time
from datetime import UTC, datetime
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler
from typing import Any

# ---------------------------------------------------------------- assinatura de eventos

CABECALHO_ASSINATURA = "X-PCPR-Assinatura"
CABECALHO_EVENTO_ID = "X-PCPR-Evento-Id"
_RE_ASSINATURA = re.compile(r"^t=(\d+),v1=([a-f0-9]{64})$")


def assinar(segredo: bytes, corpo: bytes, t: int | None = None) -> str:
    """HMAC-SHA256 sobre `timestamp + "." + corpo_bruto` → `t=<unix>,v1=<hex>`."""
    t = int(time.time()) if t is None else t
    mac = hmac.new(segredo, str(t).encode() + b"." + corpo, hashlib.sha256).hexdigest()
    return f"t={t},v1={mac}"


def verificar(segredo: bytes, corpo: bytes, cabecalho: str, tolerancia_s: int = 300) -> bool:
    """Referência da verificação que o W1 faz no n8n (usada nos testes do próprio emissor)."""
    m = _RE_ASSINATURA.match(cabecalho or "")
    if not m:
        return False
    t = int(m.group(1))
    if abs(time.time() - t) > tolerancia_s:
        return False
    esperado = hmac.new(segredo, str(t).encode() + b"." + corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, m.group(2))


# ---------------------------------------------------------------- tempo


def agora_utc() -> datetime:
    return datetime.now(UTC)


def iso_z(d: datetime) -> str:
    return d.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def corpo_json(obj: Any) -> bytes:
    """JSON compacto em UTF-8 (sem escapar acentos: prova que o n8n trata o corpo bruto)."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


# ---------------------------------------------------------------- multipart


def ler_multipart(content_type: str, corpo: bytes) -> tuple[dict[str, str], dict[str, dict]]:
    """Lê multipart/form-data sem o módulo `cgi` (removido no 3.13).

    Devolve (campos de texto, arquivos{nome: {filename, content_type, dados}}).
    """
    cabecalho = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
    msg = BytesParser(policy=HTTP).parsebytes(cabecalho + corpo)
    campos: dict[str, str] = {}
    arquivos: dict[str, dict] = {}
    if not msg.is_multipart():
        return campos, arquivos
    for parte in msg.iter_parts():
        nome = parte.get_param("name", header="content-disposition")
        if not nome:
            continue
        dados = parte.get_payload(decode=True) or b""
        filename = parte.get_filename()
        if filename is not None:
            arquivos[nome] = {
                "filename": filename,
                "content_type": parte.get_content_type(),
                "dados": dados,
            }
        else:
            charset = parte.get_content_charset() or "utf-8"
            campos[nome] = dados.decode(charset)
    return campos, arquivos


# ---------------------------------------------------------------- HTTP


class ManipuladorBase(BaseHTTPRequestHandler):
    """Handler com helpers de JSON; subclasses implementam `rotear(metodo)`."""

    protocol_version = "HTTP/1.1"
    server_version = "SimuladorPCPR/0.1"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:  # silencioso; o estado tem o log
        return

    # leitura ------------------------------------------------------------
    def corpo_bruto(self) -> bytes:
        if hasattr(self, "_corpo"):
            return self._corpo
        n = int(self.headers.get("Content-Length") or 0)
        self._corpo = self.rfile.read(n) if n else b""
        return self._corpo

    def corpo_dict(self) -> dict:
        bruto = self.corpo_bruto()
        if not bruto:
            return {}
        try:
            valor = json.loads(bruto)
        except ValueError:
            return {}
        return valor if isinstance(valor, dict) else {}

    # escrita ------------------------------------------------------------
    def responder(
        self,
        status: int,
        corpo: Any = None,
        cabecalhos: dict[str, str] | None = None,
        tipo: str = "application/json; charset=utf-8",
    ) -> None:
        if isinstance(corpo, bytes | bytearray):
            dados = bytes(corpo)
        elif corpo is None:
            dados = b""
        else:
            dados = corpo_json(corpo)
        self.send_response(status)
        if dados:
            self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        for k, v in (cabecalhos or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if dados and self.command != "HEAD":
            self.wfile.write(dados)

    def do_GET(self) -> None:
        self._despachar("GET")

    def do_POST(self) -> None:
        self._despachar("POST")

    def _despachar(self, metodo: str) -> None:
        try:
            self.rotear(metodo)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # o simulador nunca derruba a conexão sem resposta
            with contextlib.suppress(OSError):
                self.responder(500, {"codigo": "erro_interno", "mensagem": repr(exc)})

    def rotear(self, metodo: str) -> None:  # pragma: no cover - abstrato
        raise NotImplementedError
