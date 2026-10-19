"""Espião HTTP transparente entre o n8n e o PCPR REAL (suíte `testar_pcpr_real.py`).

O simulador do PCPR guardava um log de chamadas que as asserções usam ("0 chamada nova ao
PCPR", "a reserva levou 423"). O PCPR real não tem esse log, e a tabela de idempotência só guarda
2xx e 409. Este processo fica no caminho n8n → PCPR, repassa cada requisição sem alterar corpo
nem cabeçalhos (inclusive `Authorization`) ao runserver e anota só metadados: método, rota,
status, `Idempotency-Key`, `Idempotency-Replayed` e o `codigo` do corpo de erro. NÃO grava
corpo nem token.

Marcadores para o T13 (dado pessoal no n8n): da resposta do `reservar` guarda, só em memória e
só para a suíte consultar, o `destino` e o `reserva.token` — o teste precisa saber o que procurar
no banco do n8n. Nunca vão para o relatório (lá só contagens).

Injeção de falha de infraestrutura (T12): `/_espiao/falhar {"padrao": regex, "vezes": N,
"status": 500}` responde N vezes sem repassar ao PCPR — simula um proxy/servidor fora do ar, sem
mudar a API.

    python espiao_pcpr.py --porta 8775 --destino 127.0.0.1:8770
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

SALTO = {"connection", "keep-alive", "transfer-encoding", "proxy-connection", "upgrade", "te"}


class Estado:
    def __init__(self, destino: str) -> None:
        self.trava = threading.Lock()
        host, _, porta = destino.partition(":")
        self.host, self.porta = host, int(porta or 80)
        self.log: list[dict[str, Any]] = []
        self.marcadores: dict[str, set[str]] = {"destino": set(), "token_reserva": set()}
        self.falhas: list[dict[str, Any]] = []


class Manipulador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "EspiaoPCPR/0.1"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:  # silencioso
        return

    @property
    def est(self) -> Estado:
        return self.server.estado  # type: ignore[attr-defined]

    def _responder(self, status: int, corpo: bytes, tipo: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _controle(self, caminho: str, corpo: bytes) -> None:
        e = self.est
        if caminho == "/_espiao/saude":
            return self._responder(200, b'{"ok":true}')
        if caminho == "/_espiao/log":
            with e.trava:
                dados = list(e.log)
            return self._responder(200, json.dumps(dados).encode())
        if caminho == "/_espiao/marcadores":
            with e.trava:
                dados = {k: sorted(v) for k, v in e.marcadores.items()}
            return self._responder(200, json.dumps(dados).encode())
        if caminho == "/_espiao/limpar":
            with e.trava:
                e.log.clear()
            return self._responder(200, b'{"ok":true}')
        if caminho == "/_espiao/falhar":
            pedido = json.loads(corpo or b"{}")
            with e.trava:
                e.falhas.append(
                    {
                        "padrao": re.compile(pedido["padrao"]),
                        "vezes": int(pedido.get("vezes", 1)),
                        "status": int(pedido.get("status", 500)),
                    }
                )
            return self._responder(200, b'{"ok":true}')
        return self._responder(404, b'{"erro":"rota de controle inexistente"}')

    def _falha_injetada(self, caminho: str) -> int | None:
        e = self.est
        with e.trava:
            for f in e.falhas:
                if f["vezes"] > 0 and f["padrao"].search(caminho):
                    f["vezes"] -= 1
                    return f["status"]
        return None

    def _repassar(self, metodo: str) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        corpo = self.rfile.read(n) if n else b""
        caminho = self.path
        if caminho.startswith("/_espiao/"):
            return self._controle(urlsplit(caminho).path, corpo)
        t0 = time.time()
        registro: dict[str, Any] = {
            "em": t0,
            "metodo": metodo,
            "rota": urlsplit(caminho).path.removeprefix("/api/automacao/v1"),
            "chave": self.headers.get("Idempotency-Key") or "",
            "versao_esperada": self.headers.get("X-PCPR-Versao-Esperada"),
        }
        m = re.match(r"/comunicacoes/(\d+)/", registro["rota"])
        registro["comunicacao_id"] = int(m.group(1)) if m else None
        injetada = self._falha_injetada(registro["rota"])
        if injetada is not None:
            registro.update(status=injetada, injetada=True, ms=0.0)
            with self.est.trava:
                self.est.log.append(registro)
            return self._responder(injetada, b'{"erro":"falha injetada pelo espiao"}')
        cab = {k: v for k, v in self.headers.items() if k.lower() not in SALTO}
        con = http.client.HTTPConnection(self.est.host, self.est.porta, timeout=120)
        try:
            con.request(metodo, caminho, body=corpo or None, headers=cab)
            r = con.getresponse()
            dados = r.read()
            cab_resp = [(k, v) for k, v in r.getheaders() if k.lower() not in SALTO]
            status = r.status
        except OSError as exc:
            registro.update(status=502, erro=type(exc).__name__)
            with self.est.trava:
                self.est.log.append(registro)
            return self._responder(502, b'{"erro":"pcpr fora do ar (espiao)"}')
        finally:
            con.close()
        registro["status"] = status
        registro["ms"] = round((time.time() - t0) * 1000, 1)
        registro["replay"] = any(
            k.lower() == "idempotency-replayed" and v == "true" for k, v in cab_resp
        )
        try:
            j = json.loads(dados) if dados[:1] in (b"{", b"[") else None
        except ValueError:
            j = None
        if isinstance(j, dict):
            if j.get("codigo"):
                registro["codigo"] = j["codigo"]
            if registro["rota"].endswith("/reservar") and status == 200:
                with self.est.trava:
                    if j.get("destino"):
                        self.est.marcadores["destino"].add(str(j["destino"]).lstrip("+"))
                    tok = (j.get("reserva") or {}).get("token")
                    if tok:
                        self.est.marcadores["token_reserva"].add(str(tok))
            if registro["rota"].endswith("/resultado") and status == 200:
                registro["estado_depois"] = j.get("estado")
        with self.est.trava:
            self.est.log.append(registro)
        self.send_response(status)
        for k, v in cab_resp:
            if k.lower() != "content-length":
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self) -> None:
        self._repassar("GET")

    def do_POST(self) -> None:
        self._repassar("POST")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--porta", type=int, default=8775)
    p.add_argument("--destino", default="127.0.0.1:8770")
    a = p.parse_args()
    srv = ThreadingHTTPServer((a.host, a.porta), Manipulador)
    srv.daemon_threads = True
    srv.estado = Estado(a.destino)  # type: ignore[attr-defined]
    print(json.dumps({"espiao": "pcpr", "porta": a.porta, "destino": a.destino}), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
