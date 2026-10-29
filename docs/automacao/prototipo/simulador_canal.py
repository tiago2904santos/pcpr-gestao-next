"""Simulador de canal (e-mail/WhatsApp fictício) para o protótipo — só stdlib, só local.

- `POST /canal/enviar` (cabeçalho `X-Canal-Chave`): "caixa de saída" que registra cada
  tentativa e devolve `provedor_mensagem_id`. NÃO deduplica: um envio repetido apareceria como
  dois envios. Modos injetáveis (`POST /_sim/modo`):
    - `ok`; `lento` (aceita e só responde depois de `atraso_s`);
    - `recusa_503_1x` / `recusa_503`: 503 com **corpo de recusa** (`"aceita": false`) — prova de
      que NADA foi aceito; uma vez só / sempre (C5, C6);
    - `sempre_500`: 500 sem corpo de recusa — resposta **ambígua** (o cliente não sabe se saiu);
    - `timeout_apos_aceitar`: aceita (registra o envio) e só responde depois de `atraso_s`
      (maior que o tempo-limite do n8n) — o cliente vê tempo esgotado (C5);
    - `desconectar_apos_aceitar`: aceita e derruba a conexão sem responder (RST) — o cliente vê
      ECONNRESET/"socket hang up" (C5).
- `POST /_sim/fora_do_ar` `{"segundos": N}`: fecha a porta por N s (conexão recusada de verdade,
  ECONNREFUSED) e reabre com o mesmo estado (C6).
- `GET /arquivos/{id}` (cabeçalho `X-Canal-Chave`): serve um anexo; `falhar_downloads` (em
  `/_sim/modo`) faz os próximos N downloads responderem 500 (C9).
- `POST /_sim/inbound`: simula uma mensagem recebida com 1..N anexos (`anexos: [{texto, nome}]`;
  conteúdo igual entre mensagens = mesmo SHA-256) e avisa o n8n (W4) por webhook autenticado com
  `X-Canal-Token`. Com `reentregar: N`, reentrega a MESMA mensagem enquanto a resposta não for 2xx
  (como um canal real), até N vezes. Anexo com `removido: true` é anunciado mas responde 404 no
  download; `tamanho_declarado` muda o tamanho anunciado (ex.: acima do limite).
  `recebido_ha_s` data a mensagem no passado (falha temporária persistente → fila_parada).

    python simulador_canal.py --porta 8766
    (PCPR_CANAL_CHAVE, PCPR_CANAL_TOKEN_WEBHOOK, PCPR_CANAL_URL_INBOUND por ambiente)
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import hmac
import json
import os
import re
import secrets
import socket
import struct
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import timedelta
from http.server import ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from comum import ManipuladorBase, agora_utc, corpo_json, iso_z

MODOS = {
    "ok",
    "lento",
    "recusa_503_1x",
    "recusa_503",
    "sempre_500",
    "timeout_apos_aceitar",
    "desconectar_apos_aceitar",
}


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
        self.servidor: ThreadingHTTPServer | None = None
        self.volta_em = 0.0
        self.resetar()

    def resetar(self) -> None:
        with self.trava:
            self.modo = "ok"
            self.atraso_s = 0.0
            self.falhar_downloads = 0
            self.tentativas: list[dict] = []
            self.arquivos: dict[str, bytes] = {}
            self.status_download: dict[str, int] = {}
            self.mensagens_entrada: dict[str, dict] = {}
            self.inbound: list[dict] = []
            self.downloads: list[dict] = []
            self.quedas: list[dict] = []

    def despejo(self) -> dict:
        with self.trava:
            return {
                "modo": self.modo,
                "atraso_s": self.atraso_s,
                "tentativas": list(self.tentativas),
                "aceitas": [t for t in self.tentativas if t["aceita"]],
                "inbound": list(self.inbound),
                "downloads": list(self.downloads),
                "quedas": list(self.quedas),
            }

    def _anexo(self, texto: str, nome: str, pedido: dict | None = None) -> dict:
        """`removido`: o anexo é anunciado mas não existe mais no canal (download 404);
        `status_download`: o canal responde sempre esse status ao baixar (ex.: 422, id malformado);
        `tamanho_declarado`: tamanho anunciado pelo canal (ex.: acima do limite)."""
        p = pedido or {}
        pdf = pdf_sintetico(texto)
        arq = "arq-" + hashlib.sha256(pdf).hexdigest()[:16]
        if not p.get("removido"):
            self.arquivos[arq] = pdf
        if p.get("status_download"):
            self.status_download[arq] = int(p["status_download"])
        return {
            "id": arq,
            "nome": nome,
            "mime": "application/pdf",
            "tamanho": int(p.get("tamanho_declarado") or len(pdf)),
            "sha256": hashlib.sha256(pdf).hexdigest(),
        }

    def notificar_inbound(self, b: dict) -> dict:
        mid = b.get("mensagem_id") or f"wamid.sim.{uuid.uuid4().hex[:16]}"
        with self.trava:
            msg = self.mensagens_entrada.get(mid)
            if not msg:  # a mesma mensagem reenviada traz os mesmos anexos (mesmos bytes)
                pedidos = b.get("anexos")
                if pedidos is None:
                    pedidos = [{"texto": f"Documento sintetico de teste - mensagem {mid}"}]
                anexos = [
                    self._anexo(
                        str(p.get("texto") or f"Documento sintetico {mid} anexo {i}"),
                        str(p.get("nome") or f"documento-{i + 1}.pdf"),
                        p,
                    )
                    for i, p in enumerate(pedidos)
                ]
                msg = {
                    "canal": b.get("canal", "email"),
                    "mensagem_id": mid,
                    "remetente": b.get("remetente", "+5500000000001"),
                    # `recebido_ha_s`: mensagem que chegou ao canal há tempo (fila parada, §3.7)
                    "recebido_em": iso_z(
                        agora_utc() - timedelta(seconds=float(b.get("recebido_ha_s") or 0))
                    ),
                    "em_resposta_a_comunicacao": b.get("em_resposta_a_comunicacao"),
                    "anexos": anexos,
                }
                self.mensagens_entrada[mid] = msg
        corpo = corpo_json(msg)
        entregas: list[dict[str, Any]] = []
        for i in range(1 + max(0, int(b.get("reentregar", 0)))):
            if i:
                time.sleep(float(b.get("intervalo_s", 0.5)))
            registro: dict[str, Any] = {"mensagem_id": mid, "em": time.time(), "status": None}
            try:
                req = urllib.request.Request(
                    self.url_inbound,
                    data=corpo,
                    headers={
                        "Content-Type": "application/json",
                        "X-Canal-Token": self.token_webhook,
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=90) as resp:
                    registro["status"] = resp.status
                    registro["resposta"] = resp.read().decode("utf-8", "replace")[:300]
            except urllib.error.HTTPError as exc:
                registro["status"] = exc.code
                registro["resposta"] = exc.read().decode("utf-8", "replace")[:300]
            except (urllib.error.URLError, OSError) as exc:
                registro["erro"] = repr(exc)
            registro["ms"] = round((time.time() - registro["em"]) * 1000, 1)
            with self.trava:
                self.inbound.append(registro)
            entregas.append(registro)
            if registro["status"] and 200 <= registro["status"] < 300:
                break
        return {
            **entregas[-1],
            "entregas": [x["status"] for x in entregas],
            "ms_entregas": [x["ms"] for x in entregas],
            "arquivos": msg["anexos"],
            "arquivo": (msg["anexos"] or [None])[0],
        }


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
                fixo = est.status_download.get(m.group(1))
                falhar = est.falhar_downloads > 0
                if falhar:
                    est.falhar_downloads -= 1
                est.downloads.append(
                    {
                        "arquivo": m.group(1),
                        "em": time.time(),
                        "status": fixo or (500 if falhar else (200 if dados is not None else 404)),
                    }
                )
            if fixo:
                return self.responder(fixo, {"erro": "download recusado (simulado)"})
            if falhar:
                return self.responder(500, {"erro": "falha simulada no download"})
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
            if "modo" in b and b["modo"] not in MODOS:
                return self.responder(400, {"erro": f"modo deve ser um de {sorted(MODOS)}"})
            with est.trava:
                est.modo = b.get("modo", est.modo)
                est.atraso_s = float(b.get("atraso_s", 0))
                est.falhar_downloads = int(b.get("falhar_downloads", est.falhar_downloads))
            return self.responder(
                200,
                {
                    "modo": est.modo,
                    "atraso_s": est.atraso_s,
                    "falhar_downloads": est.falhar_downloads,
                },
            )
        if caminho == "/_sim/fora_do_ar":
            segundos = float(b.get("segundos", 5))
            with est.trava:
                est.volta_em = time.time() + segundos
                est.quedas.append({"de": time.time(), "segundos": segundos})
            self.responder(200, {"fora_do_ar_s": segundos})
            servidor = est.servidor
            if servidor is not None:  # shutdown espera o laço sair: em outra thread
                threading.Thread(target=servidor.shutdown, daemon=True).start()
            return None
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
            recusar = modo == "recusa_503" or (modo == "recusa_503_1x" and anteriores == 0)
            ambigua = modo == "sempre_500"
            if recusar:
                tentativa.update(status=503, recusa=True)
            elif ambigua:
                tentativa["status"] = 500  # o simulador sabe que não saiu; o cliente, não
            else:
                tentativa.update(
                    aceita=True, status=200, provedor_mensagem_id=f"sim-{uuid.uuid4().hex[:20]}"
                )
                if modo == "timeout_apos_aceitar":
                    tentativa["resposta"] = "atrasada (depois do tempo-limite do cliente)"
                if modo == "desconectar_apos_aceitar":
                    tentativa.update(status=None, resposta="conexão derrubada sem resposta")
            est.tentativas.append(tentativa)  # registrado ao receber (o provedor já tem a msg)
        if recusar:
            return self.responder(
                503,
                {
                    "erro": "indisponivel_temporariamente",
                    "aceita": False,
                    "mensagem": "Canal recusou a mensagem: nada foi enviado; tente de novo.",
                },
                {"Retry-After": "1"},
            )
        if ambigua:
            return self.responder(500, {"erro": "erro interno do provedor (simulado)"})
        if modo == "desconectar_apos_aceitar":
            return self._derrubar()
        if modo in ("lento", "timeout_apos_aceitar") and atraso:
            time.sleep(atraso)  # a mensagem saiu; só a resposta demora
        return self.responder(
            200, {"provedor_mensagem_id": tentativa["provedor_mensagem_id"], "status": "aceita"}
        )

    def _derrubar(self) -> None:
        """Fecha a conexão com RST (SO_LINGER ligado com 0 s), sem escrever resposta."""
        self.close_connection = True
        linger = struct.pack("HH", 1, 0) if os.name == "nt" else struct.pack("ii", 1, 0)
        with contextlib.suppress(OSError):
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
        self.connection.close()


class Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        return  # conexões derrubadas de propósito não poluem o log


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
    print(json.dumps({"simulador": "canal", "porta": a.porta}), flush=True)
    while True:  # /_sim/fora_do_ar derruba o laço; a porta fica fechada até `volta_em`
        srv = Servidor((a.host, a.porta), Manipulador)
        srv.estado = estado  # type: ignore[attr-defined]
        estado.servidor = srv
        srv.serve_forever()
        srv.server_close()
        espera = estado.volta_em - time.time()
        if espera > 0:
            time.sleep(espera)


if __name__ == "__main__":
    main()
