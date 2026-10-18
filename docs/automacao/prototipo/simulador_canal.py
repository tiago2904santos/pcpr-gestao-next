"""Simulador de canal (e-mail/WhatsApp fictício) para o protótipo — só stdlib, só local.

- `POST /canal/enviar` (cabeçalho `X-Canal-Chave`): "caixa de saída" que registra cada
  tentativa, com falha injetável (`ok`, `falha_1x`, `sempre_500`, `lento`) e devolve
  `provedor_mensagem_id`. NÃO deduplica: um envio repetido apareceria como dois envios.
- `GET /arquivos/{id}` (cabeçalho `X-Canal-Chave`): serve o PDF sintético de uma mensagem.
- `POST /_sim/inbound`: simula uma mensagem recebida com anexo e avisa o n8n (W4) por webhook
  autenticado com `X-Canal-Token`.

    python simulador_canal.py --porta 8766
    (PCPR_CANAL_CHAVE, PCPR_CANAL_TOKEN_WEBHOOK, PCPR_CANAL_URL_INBOUND por ambiente)
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from comum import ManipuladorBase, agora_utc, corpo_json, iso_z

MODOS = {"ok", "falha_1x", "sempre_500", "lento"}


def pdf_sintetico(texto: str) -> bytes:
    """PDF mínimo válido (1 página, Helvetica) com um texto ASCII."""
    seguro = re.sub(r"[^A-Za-z0-9 .:_-]", "_", texto)
    conteudo = f"BT /F1 14 Tf 72 770 Td ({seguro}) Tj ET".encode()
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(conteudo)).encode() + b" >>\nstream\n" + conteudo + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    saida = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objetos, start=1):
        offsets.append(len(saida))
        saida += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        saida += f"{off:010d} 00000 n \n".encode()
    saida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(saida)


class EstadoCanal:
    def __init__(self, chave: str, token_webhook: str, url_inbound: str) -> None:
        self.trava = threading.RLock()
        self.chave = chave
        self.token_webhook = token_webhook
        self.url_inbound = url_inbound
        self.resetar()

    def resetar(self) -> None:
        with self.trava:
            self.modo = "ok"
            self.atraso_s = 0.0
            self.tentativas: list[dict] = []
            self.arquivos: dict[str, bytes] = {}
            self.mensagens_entrada: dict[str, dict] = {}
            self.inbound: list[dict] = []
            self.downloads: list[dict] = []

    def despejo(self) -> dict:
        with self.trava:
            return {
                "modo": self.modo,
                "atraso_s": self.atraso_s,
                "tentativas": list(self.tentativas),
                "aceitas": [t for t in self.tentativas if t["aceita"]],
                "inbound": list(self.inbound),
                "downloads": list(self.downloads),
            }

    def notificar_inbound(self, b: dict) -> dict:
        mid = b.get("mensagem_id") or f"wamid.sim.{uuid.uuid4().hex[:16]}"
        with self.trava:
            msg = self.mensagens_entrada.get(mid)
            if not msg:
                pdf = pdf_sintetico(f"Documento sintetico de teste - mensagem {mid}")
                arq = "arq-" + hashlib.sha256(pdf).hexdigest()[:16]
                self.arquivos[arq] = pdf
                msg = {
                    "canal": b.get("canal", "whatsapp"),
                    "mensagem_id": mid,
                    "remetente": b.get("remetente", "+5500000000001"),
                    "recebido_em": iso_z(agora_utc()),
                    "em_resposta_a_comunicacao": b.get("em_resposta_a_comunicacao"),
                    "arquivo": {
                        "id": arq,
                        "nome": "documento-assinado.pdf",
                        "mime": "application/pdf",
                        "tamanho": len(pdf),
                        "sha256": hashlib.sha256(pdf).hexdigest(),
                    },
                }
                self.mensagens_entrada[mid] = msg
        corpo = corpo_json(msg)
        registro: dict[str, Any] = {"mensagem_id": mid, "em": time.time(), "status": None}
        try:
            req = urllib.request.Request(
                self.url_inbound,
                data=corpo,
                headers={"Content-Type": "application/json", "X-Canal-Token": self.token_webhook},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                registro["status"] = resp.status
        except urllib.error.HTTPError as exc:
            registro["status"] = exc.code
        except (urllib.error.URLError, OSError) as exc:
            registro["erro"] = repr(exc)
        with self.trava:
            self.inbound.append(registro)
        return {**registro, "arquivo": msg["arquivo"]}


class Manipulador(ManipuladorBase):
    server_version = "SimuladorCanal/0.1"

    @property
    def estado(self) -> EstadoCanal:
        return self.server.estado  # type: ignore[attr-defined]

    def _autorizado(self) -> bool:
        recebida = (self.headers.get("X-Canal-Chave") or "").encode()
        return hmac.compare_digest(recebida, self.estado.chave.encode())

    def rotear(self, metodo: str) -> None:
        est = self.estado
        caminho = urlsplit(self.path).path.rstrip("/")
        if caminho == "/canal/enviar" and metodo == "POST":
            return self._enviar()
        m = re.fullmatch(r"/arquivos/([A-Za-z0-9-]+)", caminho)
        if m and metodo == "GET":
            if not self._autorizado():
                return self.responder(401, {"erro": "chave inválida"})
            with est.trava:
                dados = est.arquivos.get(m.group(1))
                est.downloads.append({"arquivo": m.group(1), "em": time.time()})
            if dados is None:
                return self.responder(404, {"erro": "arquivo inexistente"})
            return self.responder(
                200,
                dados,
                {"Content-Disposition": 'attachment; filename="documento-assinado.pdf"'},
                tipo="application/pdf",
            )
        if caminho == "/_sim/saude":
            return self.responder(200, {"ok": True})
        if caminho == "/_sim/estado":
            return self.responder(200, est.despejo())
        if metodo != "POST":
            return self.responder(405, {"erro": "use POST"})
        b = self.corpo_dict()
        if caminho == "/_sim/resetar":
            est.resetar()
            return self.responder(200, {"ok": True})
        if caminho == "/_sim/modo":
            if b.get("modo") not in MODOS:
                return self.responder(400, {"erro": f"modo deve ser um de {sorted(MODOS)}"})
            with est.trava:
                est.modo = b["modo"]
                est.atraso_s = float(b.get("atraso_s", 0))
            return self.responder(200, {"modo": est.modo, "atraso_s": est.atraso_s})
        if caminho == "/_sim/inbound":
            return self.responder(200, est.notificar_inbound(b))
        return self.responder(404, {"erro": "rota inexistente"})

    def _enviar(self) -> None:
        est = self.estado
        if not self._autorizado():
            return self.responder(401, {"erro": "chave inválida"})
        b = self.corpo_dict()
        chave = str(b.get("idempotencia_canal") or "")
        tentativa = {
            "em": time.time(),
            "comunicacao_id": b.get("comunicacao_id"),
            "idempotencia_canal": chave,
            "destino": b.get("destino"),
            "aceita": False,
            "status": None,
            "provedor_mensagem_id": None,
        }
        with est.trava:
            anteriores = sum(1 for t in est.tentativas if t["idempotencia_canal"] == chave)
            modo, atraso = est.modo, est.atraso_s
            falhar = modo == "sempre_500" or (modo == "falha_1x" and anteriores == 0)
            if not falhar:
                tentativa.update(
                    aceita=True, status=200, provedor_mensagem_id=f"sim-{uuid.uuid4().hex[:20]}"
                )
            else:
                tentativa["status"] = 500
            est.tentativas.append(tentativa)  # registrado ao receber (o provedor já tem a msg)
        if modo == "lento" and atraso:
            time.sleep(atraso)  # a mensagem saiu; só a resposta demora
        if falhar:
            return self.responder(500, {"erro": "falha simulada do provedor"})
        return self.responder(
            200, {"provedor_mensagem_id": tentativa["provedor_mensagem_id"], "status": "aceita"}
        )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--porta", type=int, default=8766)
    a = p.parse_args()
    estado = EstadoCanal(
        os.environ.get("PCPR_CANAL_CHAVE") or secrets.token_urlsafe(24),
        os.environ.get("PCPR_CANAL_TOKEN_WEBHOOK") or secrets.token_urlsafe(24),
        os.environ.get("PCPR_CANAL_URL_INBOUND", "http://127.0.0.1:5678/webhook/canal-recebimento"),
    )
    srv = ThreadingHTTPServer((a.host, a.porta), Manipulador)
    srv.daemon_threads = True
    srv.estado = estado  # type: ignore[attr-defined]
    print(json.dumps({"simulador": "canal", "porta": a.porta}), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
