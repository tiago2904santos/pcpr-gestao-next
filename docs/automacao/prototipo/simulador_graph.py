"""Simulador LOCAL da WhatsApp Business Platform (Cloud API / Graph API) — frente WA-3.

Só biblioteca padrão, só 127.0.0.1, dados 100% sintéticos. NADA aqui fala com a Meta: o
simulador existe justamente para provar os fluxos sem conta, número, app ou token reais.
Reproduz as regras da documentação oficial resumidas em `../whatsapp-viabilidade.md` §6:

- `POST /v21.0/{phone_number_id}/messages` (template, text, document) com `Authorization:
  Bearer`; modelo só se `APPROVED` no registro local; texto livre/documento fora da janela de
  24 h → erro 131047 (síncrono, ou assíncrono por status `failed`, configurável — a
  documentação consultada não deixa claro qual dos dois a Meta usa; o protótipo trata ambos);
- `POST /v21.0/{phone_number_id}/media` (upload multipart) → `id`;
- `GET /v21.0/{media_id}` → `{url, mime_type, sha256, file_size, id}`; a URL expira (300 s por
  padrão, configurável) e o download exige Bearer; URL vencida → 404;
- emissor de webhooks para um callback configurável, no formato oficial
  (`entry[].changes[].value.messages|statuses`), assinado com `X-Hub-Signature-256:
  sha256=<HMAC-SHA256(App Secret, corpo bruto)>`, com reentrega (duplicatas) e status fora de
  ordem; verificação GET (`hub.mode`, `hub.verify_token`, `hub.challenge`).

Controles de teste em `/_sim/*`.

    python simulador_graph.py --porta 8767
    (GRAPH_SIM_TOKEN, GRAPH_SIM_APP_SECRET por variável de ambiente)
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import itertools
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from comum import ManipuladorBase, ler_multipart

VERSAO = "v21.0"
NUMERO_ID = "100000000000001"  # phone_number_id fictício
WABA_ID = "200000000000002"
NUMERO_EXIBIDO = "550030000001"  # DDD 00 não existe
LIMITE_DOCUMENTO = 100 * 1024 * 1024  # 100 MB (documento)
JANELA_S = 24 * 3600
VALIDADE_MIDIA_RECEBIDA_S = 7 * 24 * 3600
_seq = itertools.count(1)


def pdf_sintetico(marcador: str) -> bytes:
    """PDF mínimo válido; o texto (marcador) fica legível nos bytes para a varredura do TW13."""
    seguro = re.sub(r"[^A-Za-z0-9 .:_-]", "_", marcador)
    conteudo = f"BT /F1 12 Tf 72 770 Td ({seguro}) Tj ET".encode()
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


def erro_graph(codigo: int, mensagem: str, titulo: str | None = None, detalhe: str = "") -> dict:
    """Corpo de erro no formato da Graph API (`error.code`, `error_data.details`, `fbtrace_id`)."""
    return {
        "error": {
            "message": mensagem,
            "type": "OAuthException",
            "code": codigo,
            "error_data": {"messaging_product": "whatsapp", "details": detalhe or mensagem},
            "error_subcode": None,
            "fbtrace_id": "SIM" + secrets.token_hex(8),
            **({"title": titulo} if titulo else {}),
        }
    }


ERROS_131047 = {
    "code": 131047,
    "title": "Re-engagement message",
    "message": "Re-engagement message",
    "error_data": {
        "details": "Message failed to send because more than 24 hours have passed since the "
        "customer last replied to this number."
    },
}


class EstadoGraph:
    def __init__(self, token: str, app_secret: str) -> None:
        self.trava = threading.RLock()
        self.token = token
        self.app_secret = app_secret.encode()
        self.resetar()

    def resetar(self) -> None:
        with self.trava:
            self.templates: dict[str, dict] = {
                "pcpr_km_vespera_v1": {"status": "APPROVED", "idioma": "pt_BR", "parametros": 2},
                "pcpr_documentos_disponiveis_v1": {
                    "status": "APPROVED",
                    "idioma": "pt_BR",
                    "parametros": 2,
                },
                "pcpr_aviso_pendencia_v1": {
                    "status": "PENDING",
                    "idioma": "pt_BR",
                    "parametros": 1,
                },
            }
            self.janelas: dict[str, float] = {}  # wa_id → última mensagem do usuário (epoch)
            self.mensagens: list[dict] = []  # envios pela API (aceitos e recusados)
            self.midias: dict[str, dict] = {}
            self.urls: dict[str, dict] = {}
            self.metadados: list[dict] = []  # GET /{media_id}
            self.downloads: list[dict] = []
            self.uploads: list[dict] = []
            self.entregas: dict[str, dict] = {}  # webhooks emitidos (corpo e assinatura exatos)
            self.verificacoes: list[dict] = []
            self.requisicoes_negadas: list[dict] = []
            self.callback_url: str | None = None
            self.base_midia_webhook = "http://127.0.0.1:8767"
            self.url_ttl_s = 300.0
            self.expirar_proximas_urls = 0
            self.corromper_proximos_downloads = 0
            self.modo_131047 = "sincrono"
            self.atraso_status_assincrono_s = 0.5

    # ---------------------------------------------------------------- utilidades
    def novo_wamid(self, prefixo: str = "OUT") -> str:
        bruto = f"{prefixo}{next(_seq):06d}{secrets.token_hex(6)}".encode()
        return "wamid.SIM" + prefixo + base64.urlsafe_b64encode(bruto).decode().rstrip("=")

    def novo_media_id(self, prefixo: str) -> str:
        """Ids numéricos como os da Meta; o prefixo distingue fases/variantes no TW13."""
        return prefixo + f"{secrets.randbelow(10**11):011d}"

    def janela_aberta(self, wa_id: str) -> bool:
        ultima = self.janelas.get(wa_id)
        return ultima is not None and time.time() - ultima < JANELA_S

    def url_para(self, media_id: str, base: str) -> tuple[str, str]:
        m = self.midias[media_id]
        tok = f"urlSIM-{m['fase']}-{secrets.token_urlsafe(12)}"
        expira = time.time() + self.url_ttl_s
        if self.expirar_proximas_urls > 0:
            self.expirar_proximas_urls -= 1
            expira = time.time() - 1  # nasce vencida (TW10)
        self.urls[tok] = {"media_id": media_id, "expira": expira}
        qs = urlencode({"mid": media_id, "ext": int(time.time()), "hash": tok})
        return f"{base}/lookaside/whatsapp_business/attachments/?{qs}", tok

    def assinar(self, corpo: bytes) -> str:
        return "sha256=" + hmac.new(self.app_secret, corpo, hashlib.sha256).hexdigest()

    # ---------------------------------------------------------------- webhooks
    def _valor_base(self) -> dict:
        return {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": NUMERO_EXIBIDO, "phone_number_id": NUMERO_ID},
        }

    def _envelope(self, valores: list[dict]) -> dict:
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": WABA_ID,
                    "changes": [{"value": v, "field": "messages"} for v in valores],
                }
            ],
        }

    def mensagem_recebida(self, b: dict) -> dict:
        """Usuário fictício escreve para a empresa: abre a janela de 24 h e gera o valor do
        webhook `messages` (e a mídia, se for documento)."""
        de = re.sub(r"\D", "", str(b["de"]))
        fase = str(b.get("fase", "X"))
        tipo = b.get("tipo", "document")
        wamid = self.novo_wamid("IN" + fase)
        msg: dict[str, Any] = {
            "from": de,
            "id": wamid,
            "timestamp": str(int(time.time())),
            "type": tipo,
        }
        if b.get("contexto_wamid"):
            msg["context"] = {"from": NUMERO_EXIBIDO, "id": b["contexto_wamid"]}
        midia = None
        if tipo in ("document", "image"):
            dados = pdf_sintetico(f"PCPR-DOC-SINTETICO-{fase} {wamid}")
            media_id = self.novo_media_id(b.get("prefixo_midia", "93033"))
            sha_hex = hashlib.sha256(dados).hexdigest()
            self.midias[media_id] = {
                "dados": dados,
                "mime": "application/pdf",
                "sha256": sha_hex,
                "criada": time.time(),
                "origem": "recebida",
                "fase": fase,
                "filename": b.get("nome_arquivo", "termo-assinado.pdf"),
            }
            # No webhook o sha256 vem em base64 nos exemplos observados (não confirmado na doc
            # oficial); no GET da mídia, em hex. O fluxo aceita os dois formatos.
            midia = {
                "mime_type": "application/pdf",
                "sha256": base64.b64encode(bytes.fromhex(sha_hex)).decode(),
                "id": media_id,
            }
            if tipo == "document":
                midia["filename"] = self.midias[media_id]["filename"]
            if b.get("incluir_url", True):  # desde 16/10/2025 o webhook traz a URL
                midia["url"], _ = self.url_para(media_id, self.base_midia_webhook)
            msg[tipo] = midia
        elif tipo == "text":
            msg["text"] = {"body": b.get("texto", "Olá, mensagem sintética de teste.")}
        valor = {
            **self._valor_base(),
            "contacts": [
                {
                    "profile": {"name": b.get("nome_perfil", f"Servidora SINTETICA-{fase}")},
                    "wa_id": de,
                }
            ],
            "messages": [msg],
        }
        self.janelas[de] = time.time()
        return {"valor": valor, "wamid": wamid, "media_id": midia and midia["id"]}

    def valor_status(self, b: dict) -> dict:
        envio = next((m for m in self.mensagens if m.get("wamid") == b["wamid"]), None)
        para = re.sub(r"\D", "", str(b.get("para") or (envio or {}).get("para") or ""))
        st: dict[str, Any] = {
            "id": b["wamid"],
            "status": b["status"],
            "timestamp": str(int(b.get("timestamp") or time.time())),
            "recipient_id": para,
        }
        cb = (envio or {}).get("biz_opaque_callback_data")
        if cb and not b.get("sem_callback_data"):
            st["biz_opaque_callback_data"] = cb
        if b["status"] in ("sent", "delivered", "read"):
            st["conversation"] = {
                "id": "CONVSIM" + secrets.token_hex(6),
                "origin": {"type": "utility"},
            }
            st["pricing"] = {
                "billable": True,
                "pricing_model": "PMP",
                "category": "utility",
                "type": "regular",
            }
        if b["status"] == "failed":
            st["errors"] = [b.get("erro") or ERROS_131047]
        return {**self._valor_base(), "statuses": [st]}

    def registrar_entrega(self, valores: list[dict], destino: str | None = None) -> dict:
        corpo = json.dumps(self._envelope(valores), ensure_ascii=False).encode("utf-8")
        eid = f"ent{next(_seq):05d}"
        reg = {
            "id": eid,
            "corpo": corpo,
            "assinatura": self.assinar(corpo),
            "destino": destino or self.callback_url,
            "tentativas": [],
        }
        self.entregas[eid] = reg
        return reg

    def entregar(self, eid: str, modo: str = "normal") -> dict:
        """POST do webhook no callback. `modo` adultera a entrega (TW6)."""
        with self.trava:
            reg = self.entregas[eid]
            corpo, assinatura, destino = reg["corpo"], reg["assinatura"], reg["destino"]
        if not destino:
            return {"status": None, "erro": "callback não configurado"}
        enviado = corpo
        cab = {"Content-Type": "application/json", "User-Agent": "facebookexternalua (simulador)"}
        if modo == "normal":
            cab["X-Hub-Signature-256"] = assinatura
        elif modo == "segredo_errado":
            cab["X-Hub-Signature-256"] = (
                "sha256=" + hmac.new(b"segredo-errado", corpo, hashlib.sha256).hexdigest()
            )
        elif modo == "corpo_alterado":  # assinado o original; enviado com 1 espaço a mais
            cab["X-Hub-Signature-256"] = assinatura
            enviado = corpo + b" "
        elif modo == "sha1":  # formato antigo X-Hub-Signature (sha1) no cabeçalho novo
            cab["X-Hub-Signature-256"] = (
                "sha1=" + hmac.new(self.app_secret, corpo, hashlib.sha1).hexdigest()
            )
        elif modo != "sem_assinatura":
            raise ValueError(modo)
        t0 = time.time()
        tentativa: dict[str, Any] = {"modo": modo, "em": t0, "status": None}
        try:
            req = urllib.request.Request(destino, data=enviado, headers=cab, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                tentativa["status"] = resp.status
                resp.read()
        except urllib.error.HTTPError as exc:
            tentativa["status"] = exc.code
            exc.read()
        except (urllib.error.URLError, OSError) as exc:
            tentativa["erro"] = repr(exc)[:300]
        tentativa["ms"] = round((time.time() - t0) * 1000, 1)
        with self.trava:
            reg["tentativas"].append(tentativa)
        return {"entrega_id": eid, **tentativa}

    def verificar_callback(self, b: dict) -> dict:
        destino = b.get("destino") or self.callback_url
        desafio = str(b.get("challenge") or secrets.randbelow(10**9))
        qs = urlencode(
            {
                "hub.mode": b.get("modo", "subscribe"),
                "hub.verify_token": b.get("verify_token", ""),
                "hub.challenge": desafio,
            }
        )
        reg: dict[str, Any] = {"desafio": desafio, "status": None, "corpo": None}
        try:
            with urllib.request.urlopen(f"{destino}?{qs}", timeout=30) as resp:
                reg["status"] = resp.status
                reg["corpo"] = resp.read().decode("utf-8", "replace")[:200]
                reg["content_type"] = resp.headers.get("Content-Type")
        except urllib.error.HTTPError as exc:
            reg["status"] = exc.code
            reg["corpo"] = exc.read().decode("utf-8", "replace")[:200]
        except (urllib.error.URLError, OSError) as exc:
            reg["erro"] = repr(exc)[:300]
        reg["confere"] = reg["status"] == 200 and (reg["corpo"] or "").strip() == desafio
        with self.trava:
            self.verificacoes.append(reg)
        return reg

    def despejo(self) -> dict:
        with self.trava:
            return {
                "templates": self.templates,
                "janelas": dict(self.janelas),
                "mensagens": list(self.mensagens),
                "midias": {
                    k: {kk: vv for kk, vv in v.items() if kk != "dados"}
                    | {"tamanho": len(v["dados"])}
                    for k, v in self.midias.items()
                },
                "metadados": list(self.metadados),
                "downloads": list(self.downloads),
                "uploads": list(self.uploads),
                "entregas": [
                    {
                        "id": r["id"],
                        "destino": r["destino"],
                        "tamanho": len(r["corpo"]),
                        "tentativas": r["tentativas"],
                    }
                    for r in self.entregas.values()
                ],
                "verificacoes": list(self.verificacoes),
                "requisicoes_negadas": list(self.requisicoes_negadas),
                "config": {
                    "callback_url": self.callback_url,
                    "url_ttl_s": self.url_ttl_s,
                    "modo_131047": self.modo_131047,
                    "expirar_proximas_urls": self.expirar_proximas_urls,
                },
            }


# ==================================================================== HTTP


class Manipulador(ManipuladorBase):
    server_version = "SimuladorGraph/0.1"

    @property
    def estado(self) -> EstadoGraph:
        return self.server.estado  # type: ignore[attr-defined]

    def _bearer_ok(self) -> bool:
        recebido = (self.headers.get("Authorization") or "").encode()
        return hmac.compare_digest(recebido, f"Bearer {self.estado.token}".encode())

    def _negar(self, caminho: str) -> None:
        with self.estado.trava:
            self.estado.requisicoes_negadas.append(
                {"caminho": caminho.split("?")[0], "em": time.time()}
            )
        self.responder(
            401,
            erro_graph(190, "Invalid OAuth access token - Cannot parse access token"),
            {"WWW-Authenticate": 'OAuth "Facebook Platform" "invalid_token"'},
        )

    def rotear(self, metodo: str) -> None:
        url = urlsplit(self.path)
        caminho = url.path.rstrip("/") or "/"
        if caminho.startswith("/_sim"):
            return self._controle(metodo, caminho)
        if caminho == "/lookaside/whatsapp_business/attachments":
            return self._download(parse_qs(url.query))
        m = re.fullmatch(rf"/{VERSAO}/(\d+)/(messages|media)", caminho)
        if m and metodo == "POST":
            if not self._bearer_ok():
                return self._negar(caminho)
            if m.group(1) != NUMERO_ID:
                return self.responder(
                    400,
                    erro_graph(
                        100,
                        f"Unsupported post request. Object with ID '{m.group(1)}' does not exist",
                    ),
                )
            return self._mensagem() if m.group(2) == "messages" else self._upload()
        m = re.fullmatch(rf"/{VERSAO}/(\d+)", caminho)
        if m and metodo == "GET":
            if not self._bearer_ok():
                return self._negar(caminho)
            return self._metadados(m.group(1))
        return self.responder(400, erro_graph(100, "Unknown path components (simulador)"))

    # ------------------------------------------------------------ envio
    def _mensagem(self) -> None:
        est = self.estado
        b = self.corpo_dict()
        tipo = b.get("type")
        para = re.sub(r"\D", "", str(b.get("to") or ""))
        reg: dict[str, Any] = {
            "em": time.time(),
            "para": para,
            "tipo": tipo,
            "aceita": False,
            "biz_opaque_callback_data": b.get("biz_opaque_callback_data"),
        }

        def recusar(status: int, codigo: int, msg: str, detalhe: str = "") -> None:
            reg.update(erro_codigo=codigo, status=status)
            with est.trava:
                est.mensagens.append(reg)
            self.responder(status, erro_graph(codigo, msg, detalhe=detalhe))

        if b.get("messaging_product") != "whatsapp":
            return recusar(400, 100, "(#100) The parameter messaging_product is required.")
        if not 10 <= len(para) <= 15:
            return recusar(400, 100, "(#100) Invalid parameter", "to: número inválido")
        with est.trava:
            janela = est.janela_aberta(para)
        if tipo == "template":
            t = b.get("template") or {}
            reg["template"] = t.get("name")
            params = [
                p.get("text")
                for c in t.get("components") or []
                if c.get("type") == "body"
                for p in c.get("parameters") or []
            ]
            reg["parametros"] = params
            registro = est.templates.get(str(t.get("name")))
            idioma = ((t.get("language") or {}).get("code")) or ""
            if not registro or registro["status"] != "APPROVED" or registro["idioma"] != idioma:
                return recusar(
                    404 if not registro else 400,
                    132001,
                    "(#132001) Template name does not exist in the translation",
                    f"template name ({t.get('name')}) does not exist in {idioma} "
                    "(ou não está APPROVED)",
                )
            if len(params) != registro["parametros"]:
                return recusar(
                    400,
                    132000,
                    "(#132000) Number of parameters does not match the expected number of params",
                )
        elif tipo in ("text", "document"):
            if tipo == "text":
                corpo_txt = str((b.get("text") or {}).get("body") or "")
                if not 1 <= len(corpo_txt) <= 4096:
                    return recusar(400, 100, "(#100) Invalid parameter", "text.body")
                reg["texto_tamanho"] = len(corpo_txt)
            else:
                doc = b.get("document") or {}
                if doc.get("link"):
                    return recusar(
                        400, 100, "(#100) Invalid parameter", "o protótipo só aceita document.id"
                    )
                with est.trava:
                    midia = est.midias.get(str(doc.get("id") or ""))
                if not midia or midia["origem"] != "upload":
                    return recusar(400, 131053, "(#131053) Media upload error", "media id inválido")
                reg.update(documento_id=doc.get("id"), filename=doc.get("filename"))
            if not janela and est.modo_131047 == "sincrono":
                return recusar(
                    400,
                    131047,
                    "(#131047) Re-engagement message",
                    ERROS_131047["error_data"]["details"],
                )
        else:
            return recusar(400, 100, "(#100) Invalid parameter", f"type {tipo!r} não simulado")
        wamid = est.novo_wamid("OUT")
        reg.update(aceita=True, status=200, wamid=wamid, janela_aberta=janela)
        with est.trava:
            est.mensagens.append(reg)
        if tipo in ("text", "document") and not janela and est.modo_131047 == "assincrono":
            # aceita na API e falha depois, por webhook de status (comportamento alternativo)
            reg["falha_assincrona"] = 131047

            def falhar_depois() -> None:
                time.sleep(est.atraso_status_assincrono_s)
                with est.trava:
                    e = est.registrar_entrega(
                        [est.valor_status({"wamid": wamid, "status": "failed"})]
                    )
                est.entregar(e["id"])

            threading.Thread(target=falhar_depois, daemon=True).start()
        self.responder(
            200,
            {
                "messaging_product": "whatsapp",
                "contacts": [{"input": str(b.get("to")), "wa_id": para}],
                "messages": [{"id": wamid, "message_status": "accepted"}],
            },
        )

    def _upload(self) -> None:
        est = self.estado
        campos, arquivos = ler_multipart(self.headers.get("Content-Type", ""), self.corpo_bruto())
        arq = arquivos.get("file")
        if campos.get("messaging_product") != "whatsapp" or not arq:
            return self.responder(
                400, erro_graph(100, "(#100) Param file / messaging_product is required")
            )
        if len(arq["dados"]) > LIMITE_DOCUMENTO:
            return self.responder(400, erro_graph(131052, "(#131052) Media file too large"))
        media_id = est.novo_media_id("94044")
        with est.trava:
            est.midias[media_id] = {
                "dados": arq["dados"],
                "mime": campos.get("type") or arq["content_type"],
                "sha256": hashlib.sha256(arq["dados"]).hexdigest(),
                "criada": time.time(),
                "origem": "upload",
                "fase": "OUT",
                "filename": arq["filename"],
            }
            est.uploads.append(
                {
                    "media_id": media_id,
                    "sha256": est.midias[media_id]["sha256"],
                    "tamanho": len(arq["dados"]),
                    "mime": est.midias[media_id]["mime"],
                    "em": time.time(),
                }
            )
        self.responder(200, {"id": media_id})

    # ------------------------------------------------------------ mídia
    def _metadados(self, media_id: str) -> None:
        est = self.estado
        host = self.headers.get("Host") or "127.0.0.1:8767"
        with est.trava:
            m = est.midias.get(media_id)
            vencida = bool(m) and time.time() - m["criada"] > VALIDADE_MIDIA_RECEBIDA_S
            est.metadados.append({"media_id": media_id, "em": time.time(), "existe": bool(m)})
            if not m or vencida:
                return self.responder(
                    404, erro_graph(100, "(#100) Unsupported get request. Object does not exist")
                )
            url, _ = est.url_para(media_id, f"http://{host}")
        self.responder(
            200,
            {
                "messaging_product": "whatsapp",
                "url": url,
                "mime_type": m["mime"],
                "sha256": m["sha256"],
                "file_size": len(m["dados"]),
                "id": media_id,
            },
        )

    def _download(self, qs: dict) -> None:
        est = self.estado
        tok = (qs.get("hash") or [""])[0]
        reg: dict[str, Any] = {"em": time.time(), "bearer": self._bearer_ok(), "status": None}
        with est.trava:
            u = est.urls.get(tok)
            reg["media_id"] = u and u["media_id"]
            if not reg["bearer"]:
                reg["status"] = 401
                est.downloads.append(reg)
                return self.responder(401, erro_graph(190, "Invalid OAuth access token"))
            if not u or u["expira"] < time.time():
                reg["status"] = 404
                reg["vencida"] = bool(u)
                est.downloads.append(reg)
                return self.responder(404, b"URL expired (simulador)", tipo="text/plain")
            m = est.midias[u["media_id"]]
            dados = m["dados"]
            if est.corromper_proximos_downloads > 0:
                est.corromper_proximos_downloads -= 1
                dados = dados + b"%corrompido-pelo-simulador\n"
                reg["corrompido"] = True
            reg["status"] = 200
            est.downloads.append(reg)
        self.responder(
            200,
            dados,
            {"Content-Disposition": f'attachment; filename="{m["filename"]}"'},
            tipo=m["mime"],
        )

    # ------------------------------------------------------------ controle
    def _controle(self, metodo: str, caminho: str) -> None:
        est = self.estado
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
        if caminho == "/_sim/config":
            with est.trava:
                for k in (
                    "callback_url",
                    "base_midia_webhook",
                    "url_ttl_s",
                    "expirar_proximas_urls",
                    "corromper_proximos_downloads",
                    "modo_131047",
                    "atraso_status_assincrono_s",
                ):
                    if k in b:
                        setattr(est, k, b[k])
            return self.responder(200, est.despejo()["config"])
        if caminho == "/_sim/templates":
            with est.trava:
                est.templates[b["nome"]] = {
                    "status": b.get("status", "APPROVED"),
                    "idioma": b.get("idioma", "pt_BR"),
                    "parametros": int(b.get("parametros", 1)),
                }
            return self.responder(200, est.templates[b["nome"]])
        if caminho == "/_sim/janela":
            wa = re.sub(r"\D", "", str(b["wa_id"]))
            with est.trava:
                if b.get("ultima_em") is None:
                    est.janelas.pop(wa, None)
                else:
                    est.janelas[wa] = float(b["ultima_em"])
            return self.responder(200, {"wa_id": wa, "aberta": est.janela_aberta(wa)})
        if caminho == "/_sim/envelhecer_midia":
            with est.trava:
                est.midias[b["media_id"]]["criada"] -= float(b.get("segundos", 8 * 86400))
            return self.responder(200, {"ok": True})
        if caminho in ("/_sim/receber", "/_sim/status", "/_sim/lote"):
            with est.trava:
                if caminho == "/_sim/receber":
                    r = est.mensagem_recebida(b)
                    valores, info = [r["valor"]], {"wamid": r["wamid"], "media_id": r["media_id"]}
                elif caminho == "/_sim/status":
                    valores, info = [est.valor_status(b)], {"wamid": b["wamid"]}
                else:
                    valores, info = [], {"itens": []}
                    for ev in b["eventos"]:
                        if ev.get("status"):
                            valores.append(est.valor_status(ev))
                            info["itens"].append({"wamid": ev["wamid"]})
                        else:
                            r = est.mensagem_recebida(ev)
                            valores.append(r["valor"])
                            info["itens"].append({"wamid": r["wamid"], "media_id": r["media_id"]})
                reg = est.registrar_entrega(valores, b.get("destino"))
            entregas = [est.entregar(reg["id"], b.get("modo", "normal"))]
            for _ in range(int(b.get("duplicar", 0))):  # reentrega idêntica (mesmos bytes)
                entregas.append(est.entregar(reg["id"]))
            return self.responder(200, {**info, "entrega_id": reg["id"], "entregas": entregas})
        if caminho == "/_sim/reentregar":
            saida = [est.entregar(b["entrega_id"], b.get("modo", "normal"))]
            for _ in range(int(b.get("vezes", 1)) - 1):
                saida.append(est.entregar(b["entrega_id"], b.get("modo", "normal")))
            return self.responder(200, {"entregas": saida})
        if caminho == "/_sim/verificar":
            return self.responder(200, est.verificar_callback(b))
        if (
            caminho == "/_sim/assinar"
        ):  # para os testes conferirem a assinatura de forma independente
            corpo = base64.b64decode(b["corpo_b64"])
            return self.responder(200, {"assinatura": est.assinar(corpo)})
        return self.responder(404, {"erro": "rota de controle inexistente"})


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--porta", type=int, default=8767)
    a = p.parse_args()
    estado = EstadoGraph(
        os.environ.get("GRAPH_SIM_TOKEN") or secrets.token_urlsafe(32),
        os.environ.get("GRAPH_SIM_APP_SECRET") or secrets.token_hex(16),
    )
    srv = ThreadingHTTPServer((a.host, a.porta), Manipulador)
    srv.daemon_threads = True
    srv.estado = estado  # type: ignore[attr-defined]
    print(json.dumps({"simulador": "graph", "porta": a.porta, "versao": VERSAO}), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
