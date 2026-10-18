"""Frente WA-3: WhatsApp oficial (Cloud API) PRONTO E DESLIGADO — testes TW0–TW16.

    .venv/Scripts/python.exe docs/automacao/prototipo/testar_whatsapp.py
        [--manter]          não remove contêiner/simuladores no fim (depuração)
        [--sem-exportar]    não grava docs/automacao/n8n/w2,w6,w7,w8*.json
        [--apenas TW1,TW8]  só alguns cenários (TW13 precisa dos blocos anteriores)
        [--anexar-regressao CAMINHO]  só anexa ao resultados-whatsapp.json o resumo de um
                                      relatório da suíte principal (T1–T13) e sai

Nada fala com a Meta: o "WhatsApp" é o simulador local da Graph API (`simulador_graph.py`,
127.0.0.1:8767), números fictícios +5500…, segredos sintéticos gerados a cada execução. No
contêiner do n8n, graph.facebook.com e afins apontam para 127.0.0.1 (chamada acidental falha
localmente) e a proteção SSRF só libera host.docker.internal.

Sobe o simulador do PCPR (:8765, canal WhatsApp BLOQUEADO por padrão — os testes ligam só no
simulador) e o da Graph API (:8767), importa W1–W8 num n8n 2.43.7 descartável (:5678), publica
SÓ localmente, roda os cenários, mede a retenção de dados pessoais no banco/disco do n8n nas
variantes de recebimento V1 (webhook no n8n, W7) e V2 (webhook direto no PCPR), despublica,
exporta W2/W6/W7/W8 com `"active": false` e remove tudo. Relatório em
`resultados/resultados-whatsapp.json` (a evidência da suíte principal fica em
`resultados/resultados.json` e não é tocada).
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import construir_workflows as cw  # noqa: E402
import n8n_local  # noqa: E402
from regra_vespera import FUSO  # noqa: E402
from testar_prototipo import assentar, checar, esperar, http  # noqa: E402

REPO = RAIZ.parents[2]
DOCS_N8N = REPO / "docs" / "automacao" / "n8n"
SAIDA = RAIZ / "resultados"
RELATORIO = SAIDA / "resultados-whatsapp.json"
SIM = "http://127.0.0.1:8765"
GRAPH = "http://127.0.0.1:8767"
N8N = n8n_local.URL
API = f"{SIM}/api/automacao/v1"
CALLBACK = {"V1": f"{N8N}/webhook/whatsapp", "V2": f"{SIM}/canais/whatsapp/webhook"}
# de onde quem baixa a mídia enxerga o simulador da Graph API
BASE_MIDIA = {"V1": "http://host.docker.internal:8767", "V2": GRAPH}
# qualquer chamada acidental à Meta, de dentro do contêiner, cai em 127.0.0.1
SUMIDOURO = [
    "graph.facebook.com:127.0.0.1",
    "graph.whatsapp.com:127.0.0.1",
    "lookaside.fbsbx.com:127.0.0.1",
    "facebook.com:127.0.0.1",
    "www.facebook.com:127.0.0.1",
]
ARQUIVOS_EXPORTAR = {cw.W2: cw.ARQUIVOS[cw.W2], **cw.ARQUIVOS_WHATSAPP}

SEGREDOS = {
    "token_api": secrets.token_urlsafe(32),
    "hmac": secrets.token_hex(32),
    "canal_chave": secrets.token_urlsafe(24),
    "canal_webhook": secrets.token_urlsafe(24),
    "disparo": secrets.token_urlsafe(24),
    "n8n_cripto": secrets.token_hex(32),
    "wa_token": "EAASIM" + secrets.token_urlsafe(40),  # forma de token Meta, mas sintético
    "wa_app_secret": secrets.token_hex(16),
    "wa_chave_verify": secrets.token_hex(32),
}
# verify token = HMAC-SHA256(chave da credencial, rótulo público) — o W7 calcula igual
SEGREDOS["wa_verify_token"] = hmac.new(
    SEGREDOS["wa_chave_verify"].encode(), cw.VERIFY_TOKEN_MENSAGEM.encode(), hashlib.sha256
).hexdigest()

T: dict[str, Any] = {"varreduras": {}}
_seq_tel: dict[str, int] = {}


# ===================================================================== utilidades


def telefone(grupo: str) -> str:
    """Números fictícios por grupo (DDD 00 não existe): o grupo vira marcador no TW13."""
    _seq_tel[grupo] = _seq_tel.get(grupo, 0) + 1
    return f"+{grupo}{_seq_tel[grupo]:05d}"


GRUPOS = {"V1": "55009111", "V2": "55009222", "OUT": "55009333", "M1": "55009555"}
GRUPOS.update({"M2": "55009666", "OUTM": "55009777"})


def sim(caminho: str, corpo: Any = None) -> Any:
    st, b = http("POST" if corpo is not None else "GET", SIM + caminho, corpo)
    checar(st == 200, f"simulador PCPR {caminho} → {st} {b}")
    return b


def graph(caminho: str, corpo: Any = None) -> Any:
    st, b = http("POST" if corpo is not None else "GET", GRAPH + caminho, corpo, timeout=120)
    checar(st == 200, f"simulador Graph {caminho} → {st} {b}")
    return b


def est() -> dict:
    return sim("/_sim/estado")


def gst() -> dict:
    return graph("/_sim/estado")


def com(e: dict, cid: int) -> dict:
    return next(c for c in e["comunicacoes"] if c["id"] == cid)


def chamadas(e: dict, padrao: str, cid: int | None = None) -> list[dict]:
    return [
        r
        for r in e["log"]
        if re.fullmatch(padrao, r["rota"]) and (cid is None or r.get("comunicacao_id") == cid)
    ]


def msgs(g: dict, destino: str) -> list[dict]:
    alvo = re.sub(r"\D", "", destino)
    return [m for m in g["mensagens"] if m["para"] == alvo]


def http_bruto(
    metodo: str, url: str, corpo: bytes | None = None, cab: dict | None = None
) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=corpo, headers=cab or {}, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def multipart(campos: dict[str, str], arquivos: dict[str, tuple[str, str, bytes]]) -> tuple:
    fronteira = "----pcprwa" + secrets.token_hex(8)
    partes = []
    for k, v in campos.items():
        partes.append(
            f'--{fronteira}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        )
    for k, (nome, tipo, dados) in arquivos.items():
        partes.append(
            (
                f'--{fronteira}\r\nContent-Disposition: form-data; name="{k}"; '
                f'filename="{nome}"\r\nContent-Type: {tipo}\r\n\r\n'
            ).encode()
            + dados
            + b"\r\n"
        )
    partes.append(f"--{fronteira}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={fronteira}"


def acumular_midias() -> None:
    """Guarda os ids de mídia de cada fase antes de o simulador zerar (marcadores do TW13)."""
    try:
        g = gst()
    except Exception:  # simulador ainda não subiu
        return
    for mid, m in g["midias"].items():
        T.setdefault("midias", {}).setdefault(m["fase"], set()).add(mid)


def resetar(variante: str = "V1", ligar: bool = True) -> None:
    acumular_midias()
    sim("/_sim/resetar", {})
    if ligar:  # padrão do simulador do PCPR = BLOQUEADO; liga só aqui, no simulador
        sim("/_sim/canais", {"whatsapp": "ligado", "whatsapp_entrada": "ligado"})
    graph("/_sim/resetar", {})
    usar(variante)


def usar(variante: str) -> None:
    graph(
        "/_sim/config",
        {
            "callback_url": CALLBACK[variante],
            "base_midia_webhook": BASE_MIDIA[variante],
            "modo_131047": "sincrono",
            "url_ttl_s": 300,
        },
    )


def com_wa(destino: str, **opcoes: Any) -> dict:
    return sim("/_sim/comunicacoes", {"canal": "whatsapp", "destino": destino, **opcoes})


def esperar_estado(cid: int, estados: tuple[str, ...], timeout: float = 30) -> dict:
    return esperar(
        lambda: (c := com(est(), cid)) and c["estado"] in estados and c,
        timeout,
        f"comunicação {cid} não chegou a {estados}",
    )


def reconciliar() -> tuple[int, Any]:
    return http(
        "POST",
        f"{N8N}/webhook/pcpr-reconciliar",
        {},
        {"X-Disparo-Token": SEGREDOS["disparo"]},
        timeout=120,
    )


def recebimentos_de(e: dict, wamid: str) -> list[dict]:
    return [
        r for r in e["recebimentos"] if (r.get("campos") or {}).get("mensagem_id_canal") == wamid
    ]


# ===================================================================== cenários: envio (W6)


def tw0() -> dict:
    """O simulador aplica as regras oficiais (senão um W6 'passando' não provaria nada)."""
    resetar()
    a = {"Authorization": f"Bearer {SEGREDOS['wa_token']}"}
    msg = f"{GRAPH}/v21.0/{cw.NUMERO_ID_PADRAO}/messages"
    para = re.sub(r"\D", "", telefone(GRUPOS["OUT"]))
    texto = {"messaging_product": "whatsapp", "to": para, "type": "text", "text": {"body": "x"}}

    def modelo(nome: str, n: int) -> dict:
        return {
            "messaging_product": "whatsapp",
            "to": para,
            "type": "template",
            "template": {
                "name": nome,
                "language": {"code": "pt_BR"},
                "components": [{"type": "body", "parameters": [{"type": "text", "text": "v"}] * n}],
            },
        }

    r = {}
    st, b = http("POST", msg, texto)
    r["sem_bearer"] = [st, b["error"]["code"]]
    st, b = http("POST", msg, texto, a)
    r["texto_fora_da_janela"] = [st, b["error"]["code"]]
    st, b = http("POST", msg, modelo("pcpr_aviso_pendencia_v1", 1), a)
    r["modelo_pending"] = [st, b["error"]["code"]]
    st, b = http("POST", msg, modelo("pcpr_km_vespera_v1", 1), a)
    r["modelo_parametros_errados"] = [st, b["error"]["code"]]
    st, b = http("POST", msg, modelo("pcpr_km_vespera_v1", 2), a)
    r["modelo_aprovado"] = [st, bool(b["messages"][0]["id"].startswith("wamid."))]
    pdf = b"%PDF-1.4\n% PCPR-DOC-SINTETICO-OUT TW0\n%%EOF\n"
    corpo, tipo = multipart(
        {"messaging_product": "whatsapp", "type": "application/pdf"},
        {"file": ("tw0.pdf", "application/pdf", pdf)},
    )
    st, b = http_bruto(
        "POST", f"{GRAPH}/v21.0/{cw.NUMERO_ID_PADRAO}/media", corpo, {**a, "Content-Type": tipo}
    )
    mid = json.loads(b)["id"]
    r["upload"] = st
    st, meta = http("GET", f"{GRAPH}/v21.0/{mid}", cab=a)
    r["metadados"] = [st, meta["sha256"] == hashlib.sha256(pdf).hexdigest(), meta["file_size"]]
    r["download_sem_bearer"] = http_bruto("GET", meta["url"])[0]
    st, dados = http_bruto("GET", meta["url"], cab=a)
    r["download_com_bearer"] = [st, dados == pdf]
    graph("/_sim/config", {"url_ttl_s": 1})
    _, meta2 = http("GET", f"{GRAPH}/v21.0/{mid}", cab=a)
    time.sleep(1.6)
    r["download_url_vencida"] = http_bruto("GET", meta2["url"], cab=a)[0]
    doc = {
        "messaging_product": "whatsapp",
        "to": para,
        "type": "document",
        "document": {"id": mid, "filename": "tw0.pdf"},
    }
    st, b = http("POST", msg, doc, a)
    r["documento_fora_da_janela"] = [st, b["error"]["code"]]
    amostra = b'{"object":"whatsapp_business_account","teste":"Concei\xc3\xa7\xc3\xa3o"}'
    ass = graph("/_sim/assinar", {"corpo_b64": base64.b64encode(amostra).decode()})["assinatura"]
    calc = hmac.new(SEGREDOS["wa_app_secret"].encode(), amostra, hashlib.sha256).hexdigest()
    r["assinatura_x_hub_confere"] = ass == "sha256=" + calc
    checar(r["sem_bearer"] == [401, 190], f"sem Bearer: {r['sem_bearer']}")
    checar(r["texto_fora_da_janela"] == [400, 131047], f"janela: {r['texto_fora_da_janela']}")
    checar(r["modelo_pending"][1] == 132001, f"modelo não aprovado: {r['modelo_pending']}")
    checar(r["modelo_parametros_errados"][1] == 132000, f"{r['modelo_parametros_errados']}")
    checar(r["modelo_aprovado"] == [200, True], f"modelo aprovado: {r['modelo_aprovado']}")
    checar(r["metadados"][:2] == [200, True], f"metadados {r['metadados']}")
    checar(r["download_sem_bearer"] == 401, f"download sem Bearer: {r['download_sem_bearer']}")
    checar(r["download_com_bearer"] == [200, True], "download com Bearer")
    checar(r["download_url_vencida"] == 404, f"URL vencida: {r['download_url_vencida']}")
    checar(r["documento_fora_da_janela"] == [400, 131047], f"{r['documento_fora_da_janela']}")
    checar(r["assinatura_x_hub_confere"], "X-Hub-Signature-256 do simulador não confere")
    return r


def tw1() -> dict:
    resetar()
    destino = telefone(GRUPOS["OUT"])
    r = com_wa(destino, tipo="link_km", forma="modelo")
    cid = r["comunicacao_id"]
    checar([e["entrega"]["status"] for e in r["eventos"]] == [202], f"n8n: {r['eventos']}")
    c = esperar_estado(cid, ("enviada", "falhou"))
    assentar(3)
    e, g = est(), gst()
    m = msgs(g, destino)
    checar(c["estado"] == "enviada", f"estado {c['estado']} ({c.get('motivo')})")
    checar(len(m) == 1, f"esperada 1 mensagem na Graph API, houve {len(m)}")
    checar(m[0]["tipo"] == "template" and m[0]["aceita"], f"mensagem: {m[0]}")
    checar(m[0]["template"] == "pcpr_km_vespera_v1", f"modelo {m[0]['template']}")
    checar(
        m[0]["parametros"] == ["Fulana", f"https://pcpr.example.invalid/km/c{cid}"],
        f"variáveis {m[0]['parametros']}",
    )
    checar(m[0]["biz_opaque_callback_data"] == f"com:{cid}", "biz_opaque_callback_data")
    wamid = m[0]["wamid"]
    c = com(e, cid)
    checar(c["provedor_mensagem_id"] == wamid, "wamid não registrado no PCPR")
    checar(e["com_por_wamid"].get(wamid) == cid, "mapeamento wamid → comunicação ausente")
    res = [x for x in chamadas(e, r"/comunicacoes/\d+/resultado", cid) if x["status"] == 200]
    reservas = [x for x in chamadas(e, r"/comunicacoes/\d+/reservar", cid) if x["status"] == 200]
    checar(len(res) == 1 and len(reservas) == 1, f"resultados {res} reservas {reservas}")
    T["tw1"] = {"cid": cid, "wamid": wamid, "destino": destino, "evento": r["eventos"][0]["id"]}
    return {
        "comunicacao_id": cid,
        "mensagens_na_graph_api": 1,
        "tipo": "template",
        "modelo": m[0]["template"],
        "variaveis": ["Fulana", "<link do km>"],
        "biz_opaque_callback_data": m[0]["biz_opaque_callback_data"],
        "wamid_registrado_no_pcpr": True,
        "mapeamento_wamid_comunicacao": True,
        "reservas_200": 1,
        "resultados_200": 1,
    }


def tw2() -> dict:
    t = T.get("tw1")
    checar(t, "TW2 depende do TW1")
    antes = len(msgs(gst(), t["destino"]))
    reentregas = [sim(f"/_sim/eventos/{t['evento']}/entregar", {})["status"] for _ in range(2)]
    # mesma comunicação nova, evento entregue 5x em paralelo
    destino = telefone(GRUPOS["OUT"])
    r = com_wa(destino, tipo="link_km", entregar=False)
    cid, eid = r["comunicacao_id"], r["eventos"][0]["id"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        paralelas = list(
            ex.map(lambda _: sim(f"/_sim/eventos/{eid}/entregar", {})["status"], range(5))
        )
    esperar_estado(cid, ("enviada",))
    # evento NOVO (outro id) para a mesma comunicação já enviada: passa a dedup, PCPR barra
    n_res = len(chamadas(est(), r"/comunicacoes/\d+/reservar", cid))
    sim(f"/_sim/comunicacoes/{cid}/reemitir", {})
    esperar(
        lambda: len(chamadas(est(), r"/comunicacoes/\d+/reservar", cid)) > n_res,
        30,
        "evento reemitido não chegou ao reservar",
    )
    assentar(4)
    e, g = est(), gst()
    extra = chamadas(e, r"/comunicacoes/\d+/reservar", cid)[n_res:]
    checar(reentregas == [202, 202], f"reentregas {reentregas}")
    checar(len(msgs(g, t["destino"])) == antes == 1, "reentrega gerou nova mensagem")
    checar(len(msgs(g, destino)) == 1, f"paralelo gerou {len(msgs(g, destino))} mensagens")
    checar([x["status"] for x in extra] == [409], f"reemitido: {extra}")
    return {
        "a_reentregas_do_mesmo_evento": {"respostas": reentregas, "mensagens": 1},
        "b_cinco_entregas_simultaneas": {"respostas": paralelas, "mensagens": 1},
        "c_evento_com_outro_id": {
            "reserva": [409],
            "codigo": extra[0].get("codigo"),
            "mensagens": 1,
        },
    }


def tw3() -> dict:
    resetar()
    ev: dict[str, Any] = {}
    # (a) fora da janela, pedido de texto livre → modelo direto (nenhuma tentativa livre)
    a = telefone(GRUPOS["OUT"])
    ca = com_wa(a, tipo="documentos_disponiveis", forma="texto")["comunicacao_id"]
    esperar_estado(ca, ("enviada", "falhou"))
    # (b) o PCPR "acha" que a janela está aberta, a Meta não (síncrono): 1× 131047 → modelo
    b = telefone(GRUPOS["OUT"])
    sim(
        "/_sim/janela_pcpr",
        {"destino": b, "ultima_em": (datetime.now(UTC) - timedelta(hours=1)).isoformat()},
    )
    cb = com_wa(b, tipo="documentos_disponiveis", forma="texto")["comunicacao_id"]
    esperar_estado(cb, ("enviada", "falhou"))
    # (d) fora da janela e SEM modelo → recusa clara, nenhuma chamada à Graph API
    d = telefone(GRUPOS["OUT"])
    cd = com_wa(d, tipo="documentos_disponiveis", forma="texto", com_modelo=False)["comunicacao_id"]
    esperar_estado(cd, ("enviada", "falhou"))
    # (e) modelo não aprovado (PENDING) → 132001 uma vez, exceção, sem laço
    x = telefone(GRUPOS["OUT"])
    cx = com_wa(x, tipo="lembrete_pendencia", forma="modelo")["comunicacao_id"]
    esperar_estado(cx, ("enviada", "falhou"))
    # (c) variante assíncrona: a Meta aceita o texto e depois manda status failed/131047
    graph("/_sim/config", {"modo_131047": "assincrono"})
    c = telefone(GRUPOS["OUT"])
    sim(
        "/_sim/janela_pcpr",
        {"destino": c, "ultima_em": (datetime.now(UTC) - timedelta(hours=1)).isoformat()},
    )
    cc = com_wa(c, tipo="documentos_disponiveis", forma="texto")["comunicacao_id"]
    esperar_estado(cc, ("enviada", "falhou"))
    substituta = esperar(
        lambda: next(
            (
                x
                for x in est()["comunicacoes"]
                if x.get("substitui") == cc and x["estado"] == "enviada"
            ),
            None,
        ),
        40,
        "PCPR não reagendou por modelo depois do failed/131047",
    )
    assentar(6)
    graph("/_sim/config", {"modo_131047": "sincrono"})
    e, g = est(), gst()

    def resumo(destino: str) -> list[dict]:
        return [
            {k: m.get(k) for k in ("tipo", "aceita", "erro_codigo", "falha_assincrona", "template")}
            for m in msgs(g, destino)
        ]

    ev["a_fora_da_janela_pedido_texto"] = {"estado": com(e, ca)["estado"], "graph": resumo(a)}
    ev["b_131047_sincrono_troca_por_modelo"] = {"estado": com(e, cb)["estado"], "graph": resumo(b)}
    ev["c_131047_assincrono_pcpr_reagenda_modelo"] = {
        "original": {"estado": com(e, cc)["estado"], "entrega": com(e, cc)["entrega"]},
        "substituta": {"id": substituta["id"], "estado": substituta["estado"]},
        "graph": resumo(c),
    }
    ev["d_sem_modelo_recusa"] = {
        "estado": com(e, cd)["estado"],
        "graph": resumo(d),
        "excecao": [
            x["detalhe"] for x in e["excecoes"] if (x.get("recurso") or {}).get("id") == cd
        ],
    }
    ev["e_modelo_nao_aprovado"] = {
        "estado": com(e, cx)["estado"],
        "graph": resumo(x),
        "excecoes": len([z for z in e["excecoes"] if (z.get("recurso") or {}).get("id") == cx]),
    }
    total_131047 = sum(
        1
        for m in g["mensagens"]
        if m.get("erro_codigo") == 131047 or m.get("falha_assincrona") == 131047
    )
    ev["total_131047_na_bateria"] = total_131047
    ra = resumo(a)
    checar(len(ra) == 1 and ra[0]["tipo"] == "template" and ra[0]["aceita"], f"(a) {ra}")
    rb = resumo(b)
    checar(
        [(m["tipo"], m["aceita"], m["erro_codigo"]) for m in rb]
        == [("text", False, 131047), ("template", True, None)],
        f"(b) {rb}",
    )
    checar(com(e, cb)["estado"] == "enviada", "(b) não ficou enviada")
    rc = resumo(c)
    checar(
        [(m["tipo"], m["aceita"]) for m in rc] == [("text", True), ("template", True)]
        and rc[0]["falha_assincrona"] == 131047,
        f"(c) {rc}",
    )
    checar(com(e, cc)["entrega"] == "falhou", f"(c) entrega original {com(e, cc)['entrega']}")
    checar(not resumo(d), f"(d) chamou a Graph API: {resumo(d)}")
    checar(com(e, cd)["estado"] == "falhou" and ev["d_sem_modelo_recusa"]["excecao"], "(d) exceção")
    re_ = resumo(x)
    checar(len(re_) == 1 and re_[0]["erro_codigo"] == 132001, f"(e) {re_}")
    checar(com(e, cx)["estado"] == "falhou" and ev["e_modelo_nao_aprovado"]["excecoes"] == 1, "(e)")
    checar(total_131047 == 2, f"131047 deveria ocorrer 1× em (b) e 1× em (c): {total_131047}")
    return ev


def tw4() -> dict:
    resetar("V2")  # a janela é aberta por mensagem recebida (aqui pelo caminho V2)
    f = telefone(GRUPOS["OUT"])
    rx = graph("/_sim/receber", {"de": f, "tipo": "text", "fase": "OUT", "texto": "Bom dia"})
    checar(rx["entregas"][0]["status"] == 200, f"webhook {rx['entregas']}")
    esperar(lambda: f in est()["janelas"], 15, "PCPR não registrou a janela")
    r = com_wa(f, tipo="documentos_disponiveis", forma="documento")
    cid = r["comunicacao_id"]
    c = esperar_estado(cid, ("enviada", "falhou"))
    assentar(3)
    e, g = est(), gst()
    m = msgs(g, f)
    pdf_sha = com(e, cid)["whatsapp"]["pdf_sha256"]
    checar(c["estado"] == "enviada", f"estado {c['estado']} {c.get('motivo')}")
    checar(
        len(g["uploads"]) == 1 and g["uploads"][0]["sha256"] == pdf_sha, f"upload {g['uploads']}"
    )
    checar(
        len(m) == 1 and m[0]["tipo"] == "document" and m[0]["aceita"] and m[0]["janela_aberta"],
        f"mensagens {m}",
    )
    checar(m[0]["documento_id"] == g["uploads"][0]["media_id"], "documento não usa o id do upload")
    checar(com(e, cid)["provedor_mensagem_id"] == m[0]["wamid"], "wamid não registrado")
    return {
        "janela_aberta_por": "mensagem de texto recebida (V2) → PCPR.janela",
        "upload": {"media_id": "<id sintético>", "sha256_confere_com_o_pcpr": True},
        "mensagem": {"tipo": "document", "por_id_de_midia": True, "filename": m[0]["filename"]},
        "modelos_enviados": 0,
        "estado": "enviada",
    }


def tw11() -> dict:
    # (a) padrão do simulador: WhatsApp BLOQUEADO (nada ligado)
    resetar(ligar=False)
    _st, estado = http(
        "GET", f"{API}/estado", cab={"Authorization": f"Bearer {SEGREDOS['token_api']}"}
    )
    checar(estado["canais"]["whatsapp"] == "bloqueado", f"padrão {estado['canais']}")
    checar(estado["canais_entrada"]["whatsapp"] == "bloqueado", "entrada deveria nascer bloqueada")
    a = telefone(GRUPOS["OUT"])
    ra = com_wa(a, tipo="documentos_disponiveis")
    checar(ra["estado"] == "aguardando_envio_manual" and not ra["eventos"], f"(a) {ra}")
    st_r, rec = reconciliar()
    checar(st_r == 200 and rec.get("devidas") == 0, f"reconciliação {st_r} {rec}")
    manual = sim(f"/_sim/comunicacoes/{ra['comunicacao_id']}/envio_manual", {})
    feita = sim(
        f"/_sim/comunicacoes/{ra['comunicacao_id']}/enviado_por_outro_meio",
        {"por": "operador.sintetico"},
    )
    checar(feita["estado"] == "feita_a_mao" and feita["origem"] == "outro_meio", f"WA-1 {feita}")
    checar(manual["link_wa_me"].startswith("https://wa.me/5500"), "link wa.me")
    # (b) bloqueado DEPOIS de agendar (evento já emitido): reservar 409 canal_bloqueado
    sim("/_sim/canais", {"whatsapp": "ligado", "whatsapp_entrada": "ligado"})
    b = telefone(GRUPOS["OUT"])
    rb = com_wa(b, tipo="documentos_disponiveis", entregar=False)
    sim("/_sim/canais", {"whatsapp": "bloqueado"})
    st_b = sim(f"/_sim/eventos/{rb['eventos'][0]['id']}/entregar", {})["status"]
    esperar(
        lambda: chamadas(est(), r"/comunicacoes/\d+/reservar", rb["comunicacao_id"]),
        30,
        "W2 não tentou reservar",
    )
    assentar(3)
    e = est()
    res_b = chamadas(e, r"/comunicacoes/\d+/reservar", rb["comunicacao_id"])
    checar(
        [(x["status"], x.get("codigo")) for x in res_b] == [(409, "canal_bloqueado")],
        f"(b) {res_b}",
    )
    checar(com(e, rb["comunicacao_id"])["estado"] == "aguardando_envio_manual", "(b) estado")
    checar(not chamadas(e, r"/comunicacoes/\d+/resultado", rb["comunicacao_id"]), "(b) resultado")
    # (c) entrada bloqueada: webhook direto (V2) → 403, nada gravado; API → 409
    sim("/_sim/canais", {"whatsapp_entrada": "bloqueado"})
    usar("V2")
    de = telefone(GRUPOS["V2"])
    rc = graph(
        "/_sim/receber", {"de": de, "tipo": "document", "fase": "V2", "prefixo_midia": "92022"}
    )
    st_c, corpo_c = http(
        "POST",
        f"{API}/recebimentos/sem-arquivo",
        {
            "canal": "whatsapp",
            "mensagem_id_canal": "wamid.SIMTW11",
            "anexo_indice": 0,
            "total_anexos": 1,
            "remetente": de,
            "recebido_em": datetime.now(UTC).isoformat(),
            "motivo": "sem_anexo",
        },
        {
            "Authorization": f"Bearer {SEGREDOS['token_api']}",
            "Idempotency-Key": "receb:whatsapp:wamid.SIMTW11:0",
        },
    )
    assentar(2)
    e = est()
    checar(rc["entregas"][0]["status"] == 403, f"(c) webhook {rc['entregas']}")
    checar(st_c == 409 and corpo_c["codigo"] == "canal_bloqueado", f"(c) API {st_c} {corpo_c}")
    checar(not e["recebimentos"] and de not in e["janelas"], "(c) gravou algo")
    # (d) desligado (≠ bloqueado): 423, segue agendada; religado → reconciliação envia 1×
    sim("/_sim/canais", {"whatsapp": "desligado", "whatsapp_entrada": "ligado"})
    usar("V1")
    d = telefone(GRUPOS["OUT"])
    rd = com_wa(d, tipo="documentos_disponiveis")
    esperar(lambda: chamadas(est(), r"/comunicacoes/\d+/reservar", rd["comunicacao_id"]), 30, "(d)")
    assentar(2)
    res_d = chamadas(est(), r"/comunicacoes/\d+/reservar", rd["comunicacao_id"])
    checar([x["status"] for x in res_d] == [423], f"(d) {res_d}")
    checar(com(est(), rd["comunicacao_id"])["estado"] == "agendada", "(d) deveria seguir agendada")
    sim("/_sim/canais", {"whatsapp": "ligado"})
    st_d, rec_d = reconciliar()
    checar(st_d == 200, f"(d) reconciliação {st_d} {rec_d}")
    esperar_estado(rd["comunicacao_id"], ("enviada",))
    g = gst()
    checar(not msgs(g, a) and not msgs(g, b), "canal bloqueado chamou a Graph API")
    checar(len(msgs(g, d)) == 1, f"(d) depois de religar: {len(msgs(g, d))} mensagens")
    return {
        "a_padrao_bloqueado": {
            "estado_inicial": estado["canais"]["whatsapp"],
            "comunicacao": ra["estado"],
            "eventos_emitidos": 0,
            "reconciliacao": rec,
            "wa1_link_wa_me": "https://wa.me/5500…?text=…",
            "marcado_enviado_por_outro_meio": {
                "estado": feita["estado"],
                "origem": feita["origem"],
            },
            "chamadas_graph_api": 0,
        },
        "b_bloqueado_depois_do_evento": {
            "resposta_n8n": st_b,
            "reserva": [409, "canal_bloqueado"],
            "estado": "aguardando_envio_manual",
            "chamadas_graph_api": 0,
        },
        "c_entrada_bloqueada": {"webhook_v2": 403, "api_sem_arquivo": [409, "canal_bloqueado"]},
        "d_desligado_depois_religado": {"reserva": [423], "reconciliacao": rec_d, "mensagens": 1},
    }


def tw12() -> dict:
    resetar()
    casos = {}
    for situacao in ("sem_opt_in", "revogado", "nao_verificado"):
        destino = telefone(GRUPOS["OUT"])
        cid = com_wa(destino, tipo="documentos_disponiveis", contato=situacao)["comunicacao_id"]
        esperar(lambda c=cid: chamadas(est(), r"/comunicacoes/\d+/reservar", c), 30, situacao)
        casos[situacao] = (cid, destino)
    assentar(3)
    e, g = est(), gst()
    saida = {}
    for situacao, (cid, destino) in casos.items():
        res = chamadas(e, r"/comunicacoes/\d+/reservar", cid)
        ex = [x for x in e["excecoes"] if (x.get("recurso") or {}).get("id") == cid]
        checar(
            [(x["status"], x.get("codigo")) for x in res] == [(409, "regra_violada")],
            f"{situacao}: {res}",
        )
        checar(com(e, cid)["estado"] == "sem_contato", f"{situacao}: {com(e, cid)['estado']}")
        checar([x["motivo"] for x in ex] == ["contato_nao_verificado"], f"{situacao}: {ex}")
        checar(not msgs(g, destino), f"{situacao}: chamou a Graph API")
        saida[situacao] = {
            "reserva": [409, "regra_violada"],
            "estado": "sem_contato",
            "excecao": "contato_nao_verificado",
            "mensagens": 0,
        }
    return saida


def tw15() -> dict:
    """C5/C6 no W6: a Graph API aceita a mensagem mas a resposta chega como 502 sem corpo da
    Graph (proxy no meio) → resultado_desconhecido + exceção. Nunca falha_temporaria: o PCPR
    reagendaria e o W6 reenviaria às cegas."""
    resetar()
    graph("/_sim/config", {"respostas_ambiguas": 1})
    destino = telefone(GRUPOS["OUT"])
    cid = com_wa(destino, tipo="link_km", forma="modelo")["comunicacao_id"]
    esperar(lambda: com(est(), cid).get("rodadas"), 30, "W6 não registrou resultado")
    assentar(2)
    st, corpo = reconciliar()
    checar(st == 200 and corpo.get("devidas") == 0, f"reconciliação: {st} {corpo}")
    assentar(2)
    e, g = est(), gst()
    c = com(e, cid)
    m = msgs(g, destino)
    ex = [x for x in e["excecoes"] if (x.get("recurso") or {}).get("id") == cid]
    checar(len(m) == 1 and m[0]["aceita"] and m[0].get("resposta_ambigua") == 502, f"graph: {m}")
    checar(
        [r["resultado"] for r in c["rodadas"]] == ["resultado_desconhecido"],
        f"rodadas: {c['rodadas']}",
    )
    checar(c["estado"] == "falhou", f"estado {c['estado']} (temporária reagendaria e reenviaria)")
    checar([x["motivo"] for x in ex] == ["resultado_desconhecido"], f"exceções: {ex}")
    return {
        "mensagens_na_graph_api": 1,
        "resposta_vista_pelo_w6": "502 sem corpo da Graph API (a Meta tinha aceitado)",
        "resultado": "resultado_desconhecido",
        "estado": c["estado"],
        "excecao": "resultado_desconhecido",
        "reconciliacao_depois": corpo,
        "reenvios": 0,
    }


def tw16() -> dict:
    """2ª verificação (C5 no W6): 5xx com erro GENÉRICO da Graph API não prova que a Meta recusou
    → resultado_desconhecido + exceção, 0 reenvio. Limite de taxa (429 / 130429) é recusa antes do
    aceite → falha_temporaria → o PCPR reagenda → 1 mensagem aceita, sem exceção."""
    resetar()
    sim("/_sim/config", {"backoff_s": [1], "max_rodadas": 3})
    # (a) a Meta ACEITA e responde 500 com código 131000 ("Something went wrong")
    graph(
        "/_sim/config", {"erros_estruturados": [{"status": 500, "code": 131000, "aceitar": True}]}
    )
    destino = telefone(GRUPOS["OUT"])
    cid = com_wa(destino, tipo="link_km", forma="modelo")["comunicacao_id"]
    esperar(lambda: com(est(), cid).get("rodadas"), 30, "(a) W6 não registrou resultado")
    assentar(2)
    st, corpo = reconciliar()
    checar(st == 200 and corpo.get("devidas") == 0, f"(a) reconciliação: {st} {corpo}")
    assentar(2)
    e, g = est(), gst()
    c = com(e, cid)
    m = msgs(g, destino)
    ex = [x for x in e["excecoes"] if (x.get("recurso") or {}).get("id") == cid]
    checar(
        len(m) == 1 and m[0]["aceita"] and m[0].get("resposta_erro_apos_aceite") == [500, 131000],
        f"(a) graph: {m}",
    )
    checar(
        [r["resultado"] for r in c["rodadas"]] == ["resultado_desconhecido"],
        f"(a) rodadas: {c['rodadas']}",
    )
    checar(c["estado"] == "falhou", f"(a) estado {c['estado']}")
    checar([x["motivo"] for x in ex] == ["resultado_desconhecido"], f"(a) exceções: {ex}")
    # (b) limite de taxa: 429 com código 130429, a Meta NÃO aceitou → temporária → nova rodada
    graph(
        "/_sim/config", {"erros_estruturados": [{"status": 429, "code": 130429, "aceitar": False}]}
    )
    destino_b = telefone(GRUPOS["OUT"])
    cid_b = com_wa(destino_b, tipo="link_km", forma="modelo")["comunicacao_id"]
    esperar(
        lambda: (
            [r["resultado"] for r in (com(est(), cid_b).get("rodadas") or [])]
            == ["falha_temporaria"]
        ),
        30,
        "(b) 1ª rodada não terminou em falha_temporaria",
    )
    time.sleep(1.5)  # backoff de 1 s no PCPR
    st_b, corpo_b = reconciliar()
    checar(st_b == 200 and corpo_b.get("devidas") == 1, f"(b) reconciliação: {st_b} {corpo_b}")
    esperar_estado(cid_b, ("enviada",))
    assentar(2)
    e, g = est(), gst()
    c_b = com(e, cid_b)
    m_b = msgs(g, destino_b)
    ex_b = [x for x in e["excecoes"] if (x.get("recurso") or {}).get("id") == cid_b]
    checar([x["aceita"] for x in m_b] == [False, True], f"(b) graph: {m_b}")
    checar(
        [r["resultado"] for r in c_b["rodadas"]] == ["falha_temporaria", "enviada"],
        f"(b) rodadas: {c_b['rodadas']}",
    )
    checar(not ex_b, f"(b) exceções: {ex_b}")
    return {
        "a_500_131000_apos_aceite": {
            "mensagens_na_graph_api": 1,
            "resultado": "resultado_desconhecido",
            "estado": c["estado"],
            "excecao": "resultado_desconhecido",
            "reconciliacao_depois": corpo,
            "reenvios": 0,
        },
        "b_429_130429_recusa": {
            "tentativas_na_graph_api": [x["aceita"] for x in m_b],
            "rodadas": [r["resultado"] for r in c_b["rodadas"]],
            "reconciliacao": corpo_b,
            "excecoes": 0,
        },
    }


# ===================================================================== cenários: recebimento


def enviada_para_status(variante: str) -> tuple[int, str, str]:
    destino = telefone(GRUPOS["OUT"])
    cid = com_wa(destino, tipo="link_km")["comunicacao_id"]
    esperar_estado(cid, ("enviada",))
    wamid = msgs(gst(), destino)[0]["wamid"]
    usar(variante)
    return cid, wamid, destino


def tw5(variante: str) -> dict:
    resetar(variante)
    cid, wamid, _ = enviada_para_status(variante)
    sequencia = [
        {"status": "read"},
        {"status": "delivered"},
        {"status": "read"},  # repetido (outro POST, mesmo conteúdo lógico)
        {"status": "sent"},  # atrasado
    ]
    respostas, entregas = [], []
    for s in sequencia:
        r = graph("/_sim/status", {"wamid": wamid, **s})
        respostas.append(r["entregas"][0]["status"])
        entregas.append(r["entrega_id"])
    # reentrega idêntica (mesmos bytes e assinatura) do "delivered"
    respostas += [
        x["status"] for x in graph("/_sim/reentregar", {"entrega_id": entregas[1]})["entregas"]
    ]
    sem_cb = {}
    if variante == "V1":  # status sem biz_opaque_callback_data: W8 consulta o PCPR pelo wamid
        cid2, wamid2, _ = enviada_para_status(variante)
        r = graph(
            "/_sim/status", {"wamid": wamid2, "status": "delivered", "sem_callback_data": True}
        )
        respostas.append(r["entregas"][0]["status"])
        sem_cb = {"comunicacao": cid2, "wamid": wamid2}
    assentar(3 if variante == "V1" else 1)
    e = est()
    c = com(e, cid)
    m = e["marcas"][wamid]
    ev: dict[str, Any] = {
        "webhooks": respostas,
        "estado_final_entrega": c["entrega"],
        "entregue_em_registrado": bool(m["entregue_em"]),
        "lida_em_registrado": bool(m["lida_em"]),
    }
    checar(all(s == 200 for s in respostas), f"webhooks {respostas}")
    checar(c["entrega"] == "lida", f"estado final {c['entrega']} (esperado lida, sem regressão)")
    checar(m["entregue_em"] and m["lida_em"] and not m["falhou_em"], f"marcas {m}")
    if variante == "V1":
        posts = chamadas(e, r"/comunicacoes/\d+/entrega", cid)
        novos = [p for p in posts if not p.get("replay")]
        ev["posts_entrega"] = len(posts)
        ev["repeticoes_idempotentes"] = len(posts) - len(novos)
        checar(len(novos) == 2, f"esperados 2 registros novos (lida, entregue): {posts}")
        checar(len(posts) == 4, f"esperados 4 POST /entrega (2 novos + 2 repetidos): {len(posts)}")
        c2 = com(e, sem_cb["comunicacao"])
        busca = chamadas(e, r"/comunicacoes")
        checar(c2["entrega"] == "entregue", f"sem callback data: {c2['entrega']}")
        checar(busca and busca[-1]["status"] == 200, "W8 não consultou o PCPR pelo wamid")
        ev["status_sem_biz_opaque_callback_data"] = {
            "resolvido_pelo_wamid": True,
            "entrega": "entregue",
        }
    else:
        ev["duplicatas_ignoradas_no_pcpr"] = {
            k: v for k, v in e["wa_vistos"].items() if k.startswith(f"status:{wamid}")
        }
        checar(e["wa_vistos"].get(f"status:{wamid}:read") == 2, "read repetido não contado")
        checar(e["wa_vistos"].get(f"status:{wamid}:delivered") == 2, "reentrega não contada")
    return ev


def tw14(variante: str) -> dict:
    """C7 (W8): status que chega ANTES do /resultado (wamid ainda desconhecido no PCPR) não é
    engolido com 200: a 1ª entrega recebe não-2xx; reentregue depois do registro → gravado. O
    teste faz o papel do W6 (reserva e envio direto na Graph API simulada) para controlar a
    ordem. (b) com biz_opaque_callback_data o PCPR guarda a marca pelo wamid já na 1ª entrega."""
    resetar(variante)
    api = {"Authorization": f"Bearer {SEGREDOS['token_api']}"}
    bearer = {"Authorization": f"Bearer {SEGREDOS['wa_token']}"}

    def enviar_como_w6(destino: str, cid: int, com_callback: bool) -> tuple[str, str]:
        st, res = http(
            "POST",
            f"{API}/comunicacoes/{cid}/reservar",
            {},
            {**api, "Idempotency-Key": f"reserva:{cid}:v1:exectw14{cid}"},
        )
        checar(st == 200, f"reservar {cid}: {st} {res}")
        corpo: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": re.sub(r"\D", "", destino),
            "type": "template",
            "template": {
                "name": "pcpr_km_vespera_v1",
                "language": {"code": "pt_BR"},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": "Fulana"},
                            {"type": "text", "text": f"https://pcpr.example.invalid/km/c{cid}"},
                        ],
                    }
                ],
            },
        }
        if com_callback:
            corpo["biz_opaque_callback_data"] = f"com:{cid}"
        st, g = http("POST", f"{GRAPH}/v21.0/{cw.NUMERO_ID_PADRAO}/messages", corpo, bearer)
        checar(st == 200, f"graph: {st} {g}")
        return res["reserva"]["token"], g["messages"][0]["id"]

    def registrar_resultado(cid: int, token: str, wamid: str) -> None:
        st, b = http(
            "POST",
            f"{API}/comunicacoes/{cid}/resultado",
            {
                "reserva_token": token,
                "resultado": "enviada",
                "provedor": "whatsapp_cloud",
                "provedor_mensagem_id": wamid,
            },
            {**api, "Idempotency-Key": f"resultado:{cid}:{token}"},
        )
        checar(st == 200, f"resultado {cid}: {st} {b}")

    # (a) sem biz_opaque_callback_data: o W8 só acha a comunicação pelo wamid
    destino = telefone(GRUPOS["OUT"])
    cid = com_wa(destino, tipo="link_km", entregar=False)["comunicacao_id"]
    token, wamid = enviar_como_w6(destino, cid, com_callback=False)
    s1 = graph("/_sim/status", {"wamid": wamid, "status": "delivered"})
    st1 = s1["entregas"][0]["status"]
    assentar(1)
    e = est()
    buscas = [x for x in chamadas(e, r"/comunicacoes") if x.get("encontrou") is False]
    checar(st1 is not None and not 200 <= st1 < 300, f"1ª entrega deveria ser não-2xx: {st1}")
    checar(buscas, "o W8 não consultou o PCPR pelo wamid")
    checar(not chamadas(e, r"/comunicacoes/\d+/entrega", cid), "gravou entrega sem comunicação")
    checar(wamid not in e["marcas"] and com(e, cid)["entrega"] is None, "status gravado cedo")
    registrar_resultado(cid, token, wamid)
    s2 = graph("/_sim/reentregar", {"entrega_id": s1["entrega_id"]})
    st2 = s2["entregas"][0]["status"]
    checar(st2 == 200, f"reentrega depois do resultado deveria ser 200: {st2}")
    esperar(lambda: com(est(), cid)["entrega"] == "entregue", 15, "status não gravado")
    # (b) com biz_opaque_callback_data: já gravado na 1ª entrega (marca guardada pelo wamid)
    destino_b = telefone(GRUPOS["OUT"])
    cid_b = com_wa(destino_b, tipo="link_km", entregar=False)["comunicacao_id"]
    token_b, wamid_b = enviar_como_w6(destino_b, cid_b, com_callback=True)
    sb = graph("/_sim/status", {"wamid": wamid_b, "status": "delivered"})
    stb = sb["entregas"][0]["status"]
    checar(stb == 200, f"(b) com callback deveria ser 200: {stb}")
    checar(est()["marcas"].get(wamid_b, {}).get("entregue_em"), "(b) marca não guardada")
    registrar_resultado(cid_b, token_b, wamid_b)
    checar(com(est(), cid_b)["entrega"] == "entregue", "(b) marca não aplicada ao registrar")
    # (c) status ÓRFÃO antigo: wamid que o PCPR nunca vai conhecer (ex.: resultado perdido numa
    # queda; a reserva venceu e virou resultado_desconhecido), sem biz_opaque_callback_data e de
    # 2 h atrás → não é adiado (a Meta reentregaria o lote por até 7 dias): exceção + 200
    wamid_c = "wamid.SIMORFAO" + secrets.token_hex(8)
    corpo_c = {
        "wamid": wamid_c,
        "status": "delivered",
        "para": re.sub(r"\D", "", telefone(GRUPOS["OUT"])),
        "timestamp": int(time.time()) - 2 * 3600,
        "sem_callback_data": True,
    }
    sc = graph("/_sim/status", corpo_c)
    stc = sc["entregas"][0]["status"]
    assentar(1)
    rc = graph("/_sim/reentregar", {"entrega_id": sc["entrega_id"]})
    e = est()
    ex_c = [x for x in e["excecoes"] if wamid_c[-12:] in str(x.get("correlacao_id"))]
    checar(stc == 200, f"(c) status órfão antigo deveria ser confirmado (200): {stc}")
    checar(rc["entregas"][0]["status"] == 200, f"(c) reentrega: {rc['entregas']}")
    checar(
        len(ex_c) == 1 and ex_c[0]["origem"] == "n8n" and ex_c[0]["motivo"] == "outro",
        f"(c) exceções: {ex_c}",
    )
    checar(wamid_c not in e["marcas"], "(c) status órfão gravado como marca")
    # controle: o mesmo status RECENTE continua adiado (a regra do (a) não foi afrouxada)
    wamid_d = "wamid.SIMRECENTE" + secrets.token_hex(8)
    sd = graph("/_sim/status", {**corpo_c, "wamid": wamid_d, "timestamp": int(time.time())})
    std = sd["entregas"][0]["status"]
    checar(std is not None and not 200 <= std < 300, f"(c) status recente deveria adiar: {std}")
    return {
        "a_sem_callback_data": {
            "primeira_entrega": st1,
            "consulta_pelo_wamid": "itens: [] (resultado ainda não registrado)",
            "reentrega_depois_do_resultado": st2,
            "entrega_final": "entregue",
        },
        "b_com_callback_data": {
            "primeira_entrega": stb,
            "entrega_apos_registrar_o_resultado": "entregue",
        },
        "c_status_orfao_antigo": {
            "idade_s": 7200,
            "limite_para_adiar_s": cw.ADIAR_STATUS_MAX_S,
            "primeira_entrega": stc,
            "reentrega": rc["entregas"][0]["status"],
            "excecoes": 1,
            "status_recente_de_controle": std,
        },
    }


def _antes(variante: str) -> dict:
    e, g = est(), gst()
    return {
        "rec": len(e["recebimentos"]),
        "log": len(e["log"]),
        "meta": len(g["metadados"]),
        "down": len(g["downloads"]),
        "wa_log": len(e["wa_log"]),
    }


def tw6(variante: str) -> dict:
    resetar(variante)
    de = telefone(GRUPOS[variante])
    sim("/_sim/contatos", {"destino": de})
    antes = _antes(variante)
    respostas = {}
    medias = []
    for modo in ("segredo_errado", "sem_assinatura", "corpo_alterado", "sha1"):
        r = graph(
            "/_sim/receber",
            {
                "de": de,
                "tipo": "document",
                "fase": variante,
                "modo": modo,
                "prefixo_midia": "91011" if variante == "V1" else "92022",
            },
        )
        respostas[modo] = r["entregas"][0]["status"]
        medias.append(r["media_id"])
    assentar(3)
    e, g = est(), gst()
    checar(all(s == 401 for s in respostas.values()), f"esperado 401: {respostas}")
    checar(len(e["recebimentos"]) == antes["rec"], "assinatura inválida gerou recebimento")
    checar(de not in e["janelas"], "assinatura inválida abriu janela")
    novas = [x for x in e["log"][antes["log"] :] if x["rota"].startswith("/recebimentos")]
    checar(not novas, f"assinatura inválida chamou o PCPR: {novas}")
    tocadas = [x for x in g["metadados"] + g["downloads"] if x.get("media_id") in medias]
    checar(not tocadas, f"assinatura inválida baixou mídia: {tocadas}")
    # controle positivo: a mesma mensagem, assinada certo
    ok = graph(
        "/_sim/receber",
        {
            "de": de,
            "tipo": "document",
            "fase": variante,
            "prefixo_midia": "91011" if variante == "V1" else "92022",
        },
    )
    esperar(lambda: recebimentos_de(est(), ok["wamid"]), 30, "controle positivo não registrou")
    return {
        "respostas_invalidas": respostas,
        "recebimentos_gravados": 0,
        "janela_aberta": False,
        "midias_baixadas": 0,
        "controle_positivo": {"status": ok["entregas"][0]["status"], "recebimentos": 1},
    }


def tw7(variante: str) -> dict:
    resetar(variante)
    certo = graph("/_sim/verificar", {"verify_token": SEGREDOS["wa_verify_token"]})
    errado = graph("/_sim/verificar", {"verify_token": "token-errado-" + secrets.token_hex(4)})
    modo = graph(
        "/_sim/verificar", {"verify_token": SEGREDOS["wa_verify_token"], "modo": "unsubscribe"}
    )
    refletido = graph(
        "/_sim/verificar",
        {"verify_token": SEGREDOS["wa_verify_token"], "challenge": "<script>alert(1)</script>"},
    )
    checar(certo["status"] == 200 and certo["confere"], f"verificação correta: {certo}")
    checar("text/plain" in (certo.get("content_type") or ""), f"content-type {certo}")
    for nome, r in (("token errado", errado), ("modo errado", modo), ("desafio hostil", refletido)):
        checar(r["status"] == 403 and not r["confere"], f"{nome}: {r}")
    return {
        "correta": [certo["status"], "desafio ecoado", certo.get("content_type")],
        "token_errado": errado["status"],
        "modo_errado": modo["status"],
        "desafio_nao_alfanumerico": refletido["status"],
    }


def _receber_documento(variante: str, de: str, **mais: Any) -> dict:
    return graph(
        "/_sim/receber",
        {
            "de": de,
            "tipo": "document",
            "fase": variante,
            "prefixo_midia": "91011" if variante == "V1" else "92022",
            **mais,
        },
    )


def tw8(variante: str) -> dict:
    resetar(variante)
    # a resposta do servidor cita (context.id) uma mensagem enviada: o PCPR liga pelo wamid
    cid, wamid_out, _ = enviada_para_status(variante)
    de = telefone(GRUPOS[variante])
    sim("/_sim/contatos", {"destino": de})
    r = _receber_documento(
        variante, de, contexto_wamid=wamid_out, nome_arquivo="termo-assinado.pdf"
    )
    checar(r["entregas"][0]["status"] == 200, f"webhook {r['entregas']}")
    recs = esperar(lambda: recebimentos_de(est(), r["wamid"]), 30, "recebimento não registrado")
    assentar(2)
    e, g = est(), gst()
    recs = recebimentos_de(e, r["wamid"])
    midia = g["midias"][r["media_id"]]
    downs = [x for x in g["downloads"] if x["media_id"] == r["media_id"]]
    metas = [x for x in g["metadados"] if x["media_id"] == r["media_id"]]
    checar(len(recs) == 1 and recs[0]["estado"] == "aceito_para_processamento", f"{recs}")
    checar(recs[0]["sha256"] == midia["sha256"], "SHA-256 do recebimento ≠ da mídia")
    checar(recs[0]["em_resposta_a_comunicacao"] == cid, "resposta não ligada à comunicação")
    checar(downs and all(x["bearer"] for x in downs) and downs[-1]["status"] == 200, f"{downs}")
    checar(len(metas) >= 1, "não pediu a URL da mídia (passo 1)")
    # (b) mídia corrompida no caminho → SHA-256 não confere → nada importado, exceção. A Meta
    # entrega o MESMO webhook 3× (duplicar=2) e a mídia vem corrompida nas 3: no V1 o W7 repete o
    # POST /excecoes com a mesma chave e o MESMO corpo (sem id da execução) → 201, 201 repetição,
    # 201 repetição; 1 exceção só e nenhuma resposta não-2xx (3ª verificação, C7)
    graph("/_sim/config", {"corromper_proximos_downloads": 3})
    rb = _receber_documento(variante, de, duplicar=2)
    esperar(
        lambda: any("SHA-256" in (x.get("detalhe") or "") for x in est()["excecoes"]),
        30,
        "SHA-256 divergente não virou exceção",
    )
    assentar(2)
    graph("/_sim/config", {"corromper_proximos_downloads": 0})
    e = est()
    checar(not recebimentos_de(e, rb["wamid"]), "arquivo corrompido foi importado")
    resp_b = [x["status"] for x in rb["entregas"]]
    checar(resp_b == [200, 200, 200], f"(b) reentregas do webhook: {resp_b}")
    excs_sha = [x for x in e["excecoes"] if "SHA-256" in (x.get("detalhe") or "")]
    checar(len(excs_sha) == 1, f"(b) exceções de SHA-256: {excs_sha}")
    posts_sha: list[tuple[int, bool]] = []
    if variante == "V1":
        chave_sha = f"excecao:whatsapp-sha256:{rb['wamid']}"
        posts_sha = [
            (p["status"], bool(p.get("replay")))
            for p in chamadas(e, r"/excecoes")
            if p["chave"] == chave_sha
        ]
        checar(
            posts_sha == [(201, False), (201, True), (201, True)],
            f"(b) POST /excecoes do W7: {posts_sha}",
        )
    # (c) lote misto: documento + status no MESMO POST da Meta
    cid3, wamid3, _ = enviada_para_status(variante)
    lote = graph(
        "/_sim/lote",
        {
            "eventos": [
                {
                    "de": de,
                    "tipo": "document",
                    "fase": variante,
                    "prefixo_midia": "91011" if variante == "V1" else "92022",
                },
                {"wamid": wamid3, "status": "delivered"},
            ]
        },
    )
    checar(lote["entregas"][0]["status"] == 200, f"lote {lote['entregas']}")
    wamid_doc = lote["itens"][0]["wamid"]
    if variante == "V1":  # W7 só responde depois de processar os dois eventos
        e = est()
        imediato = bool(recebimentos_de(e, wamid_doc)) and com(e, cid3)["entrega"] == "entregue"
        checar(imediato, "W7 respondeu 200 antes de concluir os eventos do lote")
    else:  # V2: 200 após o registro durável; o download segue na fila do PCPR
        esperar(lambda: recebimentos_de(est(), wamid_doc), 30, "lote: documento")
        checar(com(est(), cid3)["entrega"] == "entregue", "lote: status")
    return {
        "webhook": r["entregas"][0]["status"],
        "recebimentos": 1,
        "estado": recs[0]["estado"],
        "sha256_conferido": True,
        "midia_baixada_com_bearer": True,
        "passos": {"metadados": len(metas), "downloads": [x["status"] for x in downs]},
        "resposta_ligada_a_comunicacao": True,
        "b_sha256_divergente": {
            "entregas_do_mesmo_webhook": resp_b,
            "recebimentos": 0,
            "excecoes": 1,
            "post_excecoes_w7": [f"{st}{' (repetição)' if rp else ''}" for st, rp in posts_sha]
            or "aberta pelo PCPR (V2)",
        },
        "c_lote_misto_documento_e_status": {
            "resposta": 200,
            "concluido_antes_do_200": variante == "V1",
            "recebimentos": 1,
            "entrega": "entregue",
        },
    }


def tw9(variante: str) -> dict:
    resetar(variante)
    de = telefone(GRUPOS[variante])
    sim("/_sim/contatos", {"destino": de})
    r = _receber_documento(variante, de, duplicar=2)
    respostas = [x["status"] for x in r["entregas"]]
    esperar(lambda: recebimentos_de(est(), r["wamid"]), 30, "recebimento não registrado")
    assentar(3)
    e, g = est(), gst()
    recs = [x for x in recebimentos_de(e, r["wamid"]) if x["estado"] != "duplicado"]
    downs = [x for x in g["downloads"] if x["media_id"] == r["media_id"]]
    checar(respostas == [200, 200, 200], f"entregas {respostas}")
    checar(len(recs) == 1 and len(recebimentos_de(e, r["wamid"])) == 1, f"recebimentos {recs}")
    ev = {
        "entregas_identicas": 3,
        "respostas": respostas,
        "recebimentos": 1,
        "downloads": len(downs),
    }
    if variante == "V1":
        posts = chamadas(e, r"/recebimentos")
        ev["post_recebimentos"] = len(posts)
        ev["repeticoes_idempotentes"] = sum(1 for p in posts if p.get("replay"))
        checar(len(posts) == 3 and ev["repeticoes_idempotentes"] == 2, f"posts {posts}")
    else:
        chave = f"receb:whatsapp:{r['wamid']}:0"
        ev["vezes_que_chegou_ao_pcpr"] = e["wa_vistos"].get(chave)
        checar(e["wa_vistos"].get(chave) == 3 and len(downs) == 1, f"V2 {e['wa_vistos']} {downs}")
    return ev


def tw10(variante: str) -> dict:
    resetar(variante)
    de = telefone(GRUPOS[variante])
    sim("/_sim/contatos", {"destino": de})
    graph("/_sim/config", {"expirar_proximas_urls": 1})
    r = _receber_documento(variante, de, incluir_url=False)
    esperar(lambda: recebimentos_de(est(), r["wamid"]), 40, "recebimento não registrado")
    assentar(2)
    e, g = est(), gst()
    downs = [x["status"] for x in g["downloads"] if x["media_id"] == r["media_id"]]
    metas = [x for x in g["metadados"] if x["media_id"] == r["media_id"]]
    recs = recebimentos_de(e, r["wamid"])
    checar(downs == [404, 200], f"downloads {downs}")
    checar(len(metas) == 2, f"pedidos de URL {len(metas)}")
    checar(len(recs) == 1 and recs[0]["estado"] == "aceito_para_processamento", f"{recs}")
    return {
        "pedidos_de_url": 2,
        "downloads": downs,
        "recebimentos": 1,
        "webhook": r["entregas"][0]["status"],
    }


# ===================================================================== TW13: retenção


def marcadores(g: dict) -> dict[str, list[str]]:
    """Marcadores de dado pessoal/credencial por grupo. Ids de mídia vêm do simulador."""
    acumular_midias()
    por_fase = {fase: sorted(ids) for fase, ids in T.get("midias", {}).items()}
    base = {
        "V1·telefone": [GRUPOS["V1"]],
        "V1·wamid": ["wamid.SIMINV1"],
        "V1·url_midia": ["urlSIM-V1"],
        "V1·id_midia": por_fase.get("V1", []),
        "V1·nome_perfil": ["SINTETICA-V1"],
        "V1·documento": ["PCPR-DOC-SINTETICO-V1"],
        "V2·telefone": [GRUPOS["V2"]],
        "V2·wamid": ["wamid.SIMINV2"],
        "V2·url_midia": ["urlSIM-V2"],
        "V2·id_midia": por_fase.get("V2", []),
        "V2·nome_perfil": ["SINTETICA-V2"],
        "V2·documento": ["PCPR-DOC-SINTETICO-V2"],
        "status·wamid_saida": ["wamid.SIMOUT"],
        "envio·telefone": [GRUPOS["OUT"]],
        "envio·link_km": ["example.invalid/km/"],
        "envio·token_reserva": ["rsvSIM"],
        "envio·url_assinada_pcpr": ["arqSIM"],
        "envio·documento": ["PCPR-DOC-SINTETICO-OUT"],
        "envio·id_midia": por_fase.get("OUT", []),
    }
    for fase in ("M1", "M2"):
        base[f"{fase}·telefone"] = [GRUPOS[fase]]
        base[f"{fase}·wamid"] = [f"wamid.SIMIN{fase}"]
        base[f"{fase}·url_midia"] = [f"urlSIM-{fase}"]
        base[f"{fase}·documento"] = [f"PCPR-DOC-SINTETICO-{fase}"]
    base["envioM·telefone"] = [GRUPOS["OUTM"]]
    for nome, valor in SEGREDOS.items():
        base[f"segredo·{nome}"] = [valor]
    return base


_RE_B64 = re.compile(rb"[A-Za-z0-9+/]{40,}={0,2}")


def contar(dados: bytes, mk: dict[str, list[str]]) -> dict[str, int]:
    """Ocorrências de cada marcador em texto puro e, com a chave `<marcador>[b64]`, dentro de
    trechos base64 decodificados (ex.: Raw Body do webhook guardado como binário inline)."""
    blobs = []
    for m in _RE_B64.finditer(dados):
        bloco = m.group(0)
        if not bloco.endswith(b"="):
            bloco = bloco[: len(bloco) - len(bloco) % 4]
        try:
            blobs.append(base64.b64decode(bloco, validate=True))
        except ValueError:
            continue
    decodificado = b"\n".join(blobs)
    saida: dict[str, int] = {}
    for k, padroes in mk.items():
        for sufixo, alvo in (("", dados), ("[b64]", decodificado)):
            n = sum(alvo.count(x.encode()) for x in padroes if x)
            if n:
                saida[k + sufixo] = saida.get(k + sufixo, 0) + n
    return saida


def varrer(rotulo: str) -> dict:
    """Copia ~/.n8n do contêiner e conta marcadores: tabelas de execução (sem workflowData),
    demais tabelas (sem definições de workflow) e arquivos (binários, logs)."""
    g = gst()
    mk = marcadores(g)
    d = Path(tempfile.mkdtemp(prefix="pcpr-wa-tw13-"))
    t0 = time.time()
    try:
        n8n_local.copiar_dados(d)
        con = sqlite3.connect(str(d / "database.sqlite"))
        tabelas = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
        definicoes = {"workflowData", "nodes", "connections", "pinData", "data_definicao"}
        tab_def = {
            "workflow_entity",
            "workflow_history",
            "credentials_entity",
            "workflow_published_version",
        }
        exec_cont: dict[str, int] = {}
        outras_onde: dict[str, dict[str, int]] = {}
        for t in tabelas:
            if t in tab_def:
                continue
            cols = [r[1] for r in con.execute(f"pragma table_info('{t}')")]
            for col in cols:
                if col in definicoes:
                    continue
                for (v,) in con.execute(f'select "{col}" from "{t}"'):  # noqa: S608
                    if isinstance(v, str):
                        v = v.encode("utf-8")
                    if not isinstance(v, bytes):
                        continue
                    for k, n in contar(v, mk).items():
                        if t.startswith("execution"):
                            exec_cont[k] = exec_cont.get(k, 0) + n
                        else:
                            outras_onde.setdefault(t, {}).setdefault(k, 0)
                            outras_onde[t][k] += n
        onde: dict[str, dict[str, int]] = {}
        linhas: dict[str, int] = {}
        if "execution_data" in tabelas and "execution_entity" in tabelas:
            consulta = (
                "select e.workflowId, e.status, e.mode, e.deletedAt is not null, d.data "
                "from execution_data d join execution_entity e on e.id = d.executionId"
            )
            for wid, status, modo, apagada, dados in con.execute(consulta):
                chave = f"{wid}|{status}|{modo}|{'soft-deleted' if apagada else 'ativa'}"
                linhas[chave] = linhas.get(chave, 0) + 1
                for k, n in contar(f"{dados or ''}".encode(), mk).items():
                    onde.setdefault(chave, {}).setdefault(k, 0)
                    onde[chave][k] += n
        con.close()
        arq_cont: dict[str, int] = {}
        arq_onde: dict[str, dict[str, int]] = {}
        n_arquivos = 0
        for p in d.rglob("*"):
            if not p.is_file() or p.name.startswith("database.sqlite") or p.name == "config":
                continue
            n_arquivos += 1
            dados = p.read_bytes()
            rel = p.relative_to(d).as_posix()
            partes = rel.split("/")
            grupo = (
                f"storage:{partes[partes.index('workflows') + 1]}"
                if "workflows" in partes
                else partes[0]
            )
            for k, n in contar(dados, mk).items():
                arq_cont[k] = arq_cont.get(k, 0) + n
                arq_onde.setdefault(grupo, {}).setdefault(k, 0)
                arq_onde[grupo][k] += n
        r = {
            "rotulo": rotulo,
            "em": datetime.now(FUSO).isoformat(timespec="seconds"),
            "segundos_desde_subida_do_n8n": round(
                time.time() - T.get("subida_n8n", time.time()), 1
            ),
            "tabelas_de_execucao": {k: v for k, v in exec_cont.items() if v},
            "execucoes_com_marcadores": onde,
            "linhas_execution_data": linhas,
            "demais_tabelas": outras_onde,
            "arquivos": {k: v for k, v in arq_cont.items() if v},
            "arquivos_onde": arq_onde,
            "arquivos_varridos": n_arquivos,
            "tabelas_do_banco": sorted(tabelas),
            "varredura_s": round(time.time() - t0, 1),
        }
        r["por_grupo"] = resumir_grupos(r)
        T["varreduras"][rotulo] = r
        return r
    finally:
        shutil.rmtree(d, ignore_errors=True)


def resumir_grupos(r: dict) -> dict:
    saida: dict[str, dict[str, int]] = {}
    for fonte in ("tabelas_de_execucao", "arquivos"):
        for k, v in r[fonte].items():
            grupo = k.split("·")[0] + (" (base64)" if k.endswith("[b64]") else "")
            saida.setdefault(grupo, {"banco": 0, "arquivos": 0})
            saida[grupo]["banco" if fonte == "tabelas_de_execucao" else "arquivos"] += v
    return saida


def delta(a: dict | None, b: dict) -> dict[str, dict[str, int]]:
    saida: dict[str, dict[str, int]] = {}
    for fonte, nome in (("tabelas_de_execucao", "banco"), ("arquivos", "arquivos")):
        antes = (a or {}).get(fonte, {})
        for k, n in b[fonte].items():
            d = n - antes.get(k, 0)
            if d:
                saida.setdefault(k, {})[nome] = d
    return saida


def rodada_minima(fase: str, tel_out: str) -> dict:
    """Uma rodada V1 completa (documento + texto + status) e um envio por modelo (W6)."""
    resetar("V1")
    de = telefone(GRUPOS[fase])
    sim("/_sim/contatos", {"destino": de})
    r1 = graph(
        "/_sim/receber",
        {
            "de": de,
            "tipo": "document",
            "fase": fase,
            "prefixo_midia": "95055" if fase == "M1" else "96066",
        },
    )
    r2 = graph("/_sim/receber", {"de": de, "tipo": "text", "fase": fase})
    destino = telefone(GRUPOS[tel_out])
    cid = com_wa(destino, tipo="link_km")["comunicacao_id"]
    esperar_estado(cid, ("enviada",))
    wamid = msgs(gst(), destino)[0]["wamid"]
    r3 = graph("/_sim/status", {"wamid": wamid, "status": "read"})
    esperar(lambda: recebimentos_de(est(), r1["wamid"]), 30, f"{fase}: documento")
    checar(
        [x["entregas"][0]["status"] for x in (r1, r2, r3)] == [200, 200, 200], f"{fase}: webhooks"
    )
    checar(com(est(), cid)["entrega"] == "lida", f"{fase}: status")
    return {"documento": 1, "texto": 1, "status": 1, "envio_modelo": 1}


def reiniciar_n8n(env_extra: dict[str, str]) -> float:
    n8n_local.docker("rm", "-f", n8n_local.CONTEINER, check=False)
    n8n_local.subir(SEGREDOS["n8n_cripto"], env_extra=env_extra, hosts_extras=SUMIDOURO)
    T["subida_n8n"] = time.time()
    s = n8n_local.esperar_pronto()
    esperar(lambda: http("GET", f"{N8N}/webhook/whatsapp")[0] == 403, 60, "W7 não registrou")
    return s


def tw13() -> dict:
    v = T["varreduras"]
    checar({"apos_envio", "apos_v1", "apos_v2"} <= set(v), "TW13 precisa dos blocos A, B e C")
    ev: dict[str, Any] = {
        "configuracao_n8n_nos_blocos_A_B_C": "a mesma da suíte principal "
        "(EXECUTIONS_DATA_PRUNE=true, hard-delete a cada 15 min, padrão 2.43.7); W6–W8 com "
        "saveData*='none' e saveExecutionProgress=false",
        "apos_envio": v["apos_envio"]["por_grupo"],
        "apos_v1": v["apos_v1"]["por_grupo"],
        "apos_v2": v["apos_v2"]["por_grupo"],
        # o que CADA bloco acrescentou (ocorrências no banco + nos arquivos do n8n)
        "acrescimo_bloco_A_envio": delta(None, v["apos_envio"]),
        "acrescimo_bloco_B_V1": delta(v["apos_envio"], v["apos_v1"]),
        "acrescimo_bloco_C_V2": delta(v["apos_v1"], v["apos_v2"]),
        "linhas_de_execucao_apos_v2": v["apos_v2"]["linhas_execution_data"],
    }
    # Mitigação 1: hard-delete a cada 1 min (poda continua ligada para o que é salvo)
    ev["m1_subida_s"] = round(reiniciar_n8n({"EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL": "1"}), 1)
    ev["m1_rodada"] = rodada_minima("M1", "OUTM")
    m1_ja = varrer("m1_imediato")
    # O hard-delete roda a cada 1 min contado de quando o serviço de poda inicia, e só remove o
    # que já estava apagado (soft delete) naquele ciclo. Uma janela fixa contada da subida do n8n
    # não basta: se a rodada M1 demora (task runner lento: "Offer expired"), a 2ª varredura caía
    # logo depois da 1ª, antes de qualquer ciclo posterior à rodada (TW13 reprovou 2× assim).
    # Agora: espera pelo menos 1 ciclo inteiro + folga depois do fim da rodada e, se ainda
    # sobrar, varre de novo a cada 20 s até 3 ciclos (180 s) — o limite é o que o TW13 garante.
    fim_rodada = time.time()
    tentativas_m1: list[dict[str, Any]] = []
    time.sleep(75)
    while True:
        m1_depois = varrer("m1_apos_hard_delete")
        tentativas_m1.append(
            {
                "s_apos_fim_da_rodada": round(time.time() - fim_rodada, 1),
                "sobra": m1_depois["por_grupo"],
            }
        )
        if not m1_depois["por_grupo"] or time.time() - fim_rodada > 180:
            break
        time.sleep(20)
    ev["m1_varreduras_apos_a_rodada"] = tentativas_m1
    ev["m1_imediato"] = m1_ja["por_grupo"]
    ev["m1_apos_hard_delete"] = m1_depois["por_grupo"]
    ev["m1_segundos_desde_subida_na_2a_varredura"] = m1_depois["segundos_desde_subida_do_n8n"]
    # Mitigação 2: sem poda → "não salvar" vira exclusão física imediata no fim da execução
    ev["m2_subida_s"] = round(reiniciar_n8n({"EXECUTIONS_DATA_PRUNE": "false"}), 1)
    ev["m2_rodada"] = rodada_minima("M2", "OUTM")
    m2 = varrer("m2_imediato")
    ev["m2_imediato"] = m2["por_grupo"]
    pessoais_v2 = {k: n for k, n in v["apos_v2"]["por_grupo"].items() if k in ("V2", "V2 (base64)")}
    # asserções
    # Credenciais que o n8n usa para FALAR com alguém nunca podem aparecer em execução/disco.
    # (disparo e wa_verify_token chegam DE FORA em cabeçalho/query: são medidos e relatados.)
    proibidos = {
        f"segredo·{k}"
        for k in ("token_api", "hmac", "n8n_cripto", "canal_chave", "wa_token", "wa_app_secret")
    } | {"segredo·wa_chave_verify"}
    proibidos |= {f"{k}[b64]" for k in proibidos}
    for rot, r in v.items():
        achados = [k for k in (*r["tabelas_de_execucao"], *r["arquivos"]) if k in proibidos]
        checar(not achados, f"credencial encontrada no n8n em {rot}: {achados}")
    ev["segredos_vindos_de_fora_retidos"] = {
        rot: {
            k: r["tabelas_de_execucao"].get(k, 0) + r["arquivos"].get(k, 0)
            for k in ("segredo·disparo", "segredo·wa_verify_token")
            if r["tabelas_de_execucao"].get(k) or r["arquivos"].get(k)
        }
        for rot, r in v.items()
    }
    checar(not pessoais_v2, f"V2 deixou dado de entrada no n8n: {pessoais_v2}")
    checar(
        m1_ja["por_grupo"].get("M1"),
        "controle positivo: a rodada M1 não deixou rastro "
        "nem antes do hard-delete (varredura insensível?)",
    )
    sobra_m1 = dict(m1_depois["por_grupo"])
    checar(
        not sobra_m1,
        f"até 180 s depois da rodada M1 (3 ciclos de hard-delete de 1 min) ainda sobrou: "
        f"{sobra_m1}; varreduras: {[x['s_apos_fim_da_rodada'] for x in tentativas_m1]}",
    )
    sobra_m2 = {k: x for k, x in m2["por_grupo"].items() if k.split(" ")[0] in ("M2", "envioM")}
    checar(not sobra_m2, f"PRUNE=false: sobrou {m2['por_grupo']}")
    return ev


# ===================================================================== orquestração

CENARIOS: list[tuple[str, str, str, Callable[..., dict]]] = [
    ("TW0", "-", "simulador aplica as regras oficiais (Bearer, janela, modelos, mídia, HMAC)", tw0),
    ("TW1", "-", "modelo enviado 1× e wamid registrado no PCPR", tw1),
    ("TW2", "-", "evento duplicado (série, paralelo, outro id) → 1 mensagem", tw2),
    ("TW3", "-", "fora da janela: modelo, nunca 131047 em laço", tw3),
    ("TW4", "-", "dentro da janela: documento por id de mídia", tw4),
    ("TW11", "-", "canal bloqueado → 0 chamada à Graph API, aguardando envio manual (WA-1)", tw11),
    ("TW12", "-", "contato sem opt-in → não envia, exceção contato_nao_verificado", tw12),
    ("TW15", "-", "W6: resposta ambígua (502 após aceitar) → resultado_desconhecido", tw15),
    (
        "TW16",
        "-",
        "W6: 5xx genérico da Graph (aceite incerto) → desconhecido; 429/130429 → reagenda → 1",
        tw16,
    ),
    ("VARRER", "apos_envio", "", varrer),
    ("TW5", "V1", "status fora de ordem e duplicado → lida, sem regressão", tw5),
    ("TW6", "V1", "assinatura inválida → 401, nada gravado", tw6),
    ("TW7", "V1", "verificação GET correta/incorreta", tw7),
    ("TW8", "V1", "documento recebido → 1 recebimento, SHA-256, Bearer", tw8),
    ("TW9", "V1", "reentrega do mesmo webhook → 1 recebimento", tw9),
    ("TW10", "V1", "URL de mídia vencida → pede nova e conclui", tw10),
    (
        "TW14",
        "V1",
        "status antes do resultado → não-2xx; reentrega após registro → gravado; "
        "órfão antigo → exceção e 200",
        tw14,
    ),
    ("VARRER", "apos_v1", "", varrer),
    ("TW5", "V2", "status fora de ordem e duplicado → lida, sem regressão", tw5),
    ("TW6", "V2", "assinatura inválida → 401, nada gravado", tw6),
    ("TW7", "V2", "verificação GET correta/incorreta", tw7),
    ("TW8", "V2", "documento recebido → 1 recebimento, SHA-256, Bearer", tw8),
    ("TW9", "V2", "reentrega do mesmo webhook → 1 recebimento", tw9),
    ("TW10", "V2", "URL de mídia vencida → pede nova e conclui", tw10),
    ("VARRER", "apos_v2", "", varrer),
    ("TW13", "-", "retenção de dado pessoal no n8n: V1 × V2 e mitigação", tw13),
]


def subir_simuladores(log_dir: Path) -> list[subprocess.Popen]:
    env = dict(os.environ)
    env.update(
        {
            "PCPR_SIM_TOKEN": SEGREDOS["token_api"],
            "PCPR_SIM_SEGREDO_HMAC": SEGREDOS["hmac"],
            "PCPR_SIM_URL_EVENTOS": f"{N8N}/webhook/pcpr-eventos",
            # PCPR_SIM_CANAL_WHATSAPP NÃO é definido: o simulador nasce com o canal BLOQUEADO
            "PCPR_SIM_WA_APP_SECRET": SEGREDOS["wa_app_secret"],
            "PCPR_SIM_WA_VERIFY_TOKEN": SEGREDOS["wa_verify_token"],
            "PCPR_SIM_WA_TOKEN": SEGREDOS["wa_token"],
            "PCPR_SIM_GRAPH_URL": f"{GRAPH}/v21.0",
            "PCPR_SIM_URL_PUBLICA": "http://host.docker.internal:8765",
            "GRAPH_SIM_TOKEN": SEGREDOS["wa_token"],
            "GRAPH_SIM_APP_SECRET": SEGREDOS["wa_app_secret"],
            "PYTHONUNBUFFERED": "1",
        }
    )
    procs = []
    for script, porta in (("simulador_pcpr.py", 8765), ("simulador_graph.py", 8767)):
        log = (log_dir / f"{script}.log").open("w", encoding="utf-8")
        procs.append(
            subprocess.Popen(
                [sys.executable, str(RAIZ / script), "--porta", str(porta)],
                cwd=RAIZ,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        )
    for url in (SIM, GRAPH):
        esperar(lambda u=url: http("GET", u + "/_sim/saude")[0] == 200, 15, f"{url} não subiu")
    return procs


def credenciais() -> list[dict]:
    return [
        {
            **cw.CRED_API,
            "type": "httpHeaderAuth",
            "data": {"name": "Authorization", "value": f"Bearer {SEGREDOS['token_api']}"},
        },
        {**cw.CRED_HMAC, "type": "crypto", "data": {"hmacSecret": SEGREDOS["hmac"]}},
        {
            **cw.CRED_CANAL_API,
            "type": "httpHeaderAuth",
            "data": {"name": "X-Canal-Chave", "value": SEGREDOS["canal_chave"]},
        },
        {
            **cw.CRED_CANAL_WEBHOOK,
            "type": "httpHeaderAuth",
            "data": {"name": "X-Canal-Token", "value": SEGREDOS["canal_webhook"]},
        },
        {
            **cw.CRED_DISPARO,
            "type": "httpHeaderAuth",
            "data": {"name": "X-Disparo-Token", "value": SEGREDOS["disparo"]},
        },
        {
            **cw.CRED_WA_TOKEN,
            "type": "httpHeaderAuth",
            "data": {"name": "Authorization", "value": f"Bearer {SEGREDOS['wa_token']}"},
        },
        {
            **cw.CRED_WA_APP_SECRET,
            "type": "crypto",
            "data": {"hmacSecret": SEGREDOS["wa_app_secret"]},
        },
        {
            **cw.CRED_WA_VERIFY,
            "type": "crypto",
            "data": {"hmacSecret": SEGREDOS["wa_chave_verify"]},
        },
    ]


def exportar_workflows(tmp: Path) -> dict:
    destino = tmp / "exportado"
    destino.mkdir()
    saida = n8n_local.exportar(destino, SEGREDOS["n8n_cripto"])
    evid: dict[str, Any] = {"cli": saida.strip().splitlines()[-6:], "arquivos": {}}
    cred = (destino / "credenciais-criptografadas.json").read_text(encoding="utf-8")
    vazou = [k for k, v in SEGREDOS.items() if v in cred]
    evid["credenciais_criptografadas_no_banco"] = not vazou
    checar(not vazou, f"credenciais exportadas em claro: {vazou}")
    DOCS_N8N.mkdir(parents=True, exist_ok=True)
    for wid, nome in ARQUIVOS_EXPORTAR.items():
        bruto = (destino / "workflows" / f"{wid}.json").read_text(encoding="utf-8")
        dados = json.loads(bruto)
        segredos_no_arquivo = [k for k, v in SEGREDOS.items() if v in bruto]
        checar(not segredos_no_arquivo, f"{nome} contém segredo: {segredos_no_arquivo}")
        checar(dados.get("active") is False, f"{nome}: active={dados.get('active')!r}")
        checar("facebook.com" not in bruto, f"{nome} aponta para a Meta")
        (DOCS_N8N / nome).write_text(
            json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        evid["arquivos"][nome] = {
            "active": dados["active"],
            "nos": len(dados["nodes"]),
            "credenciais": sorted(
                {c["id"] for n in dados["nodes"] for c in (n.get("credentials") or {}).values()}
            ),
            "settings": {
                k: dados["settings"].get(k)
                for k in (
                    "saveDataSuccessExecution",
                    "saveDataErrorExecution",
                    "saveExecutionProgress",
                )
            },
            "menciona_facebook_com": False,
        }
    return evid


def portas_abertas() -> list[str]:
    r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, check=False)
    return [
        linha.strip()
        for linha in r.stdout.splitlines()
        if re.search(r":(8765|8767|5678)\s", linha)
        and ("LISTEN" in linha.upper() or "ESCUTANDO" in linha.upper())
    ]


def anexar_regressao(caminho: Path) -> int:
    rel = json.loads(caminho.read_text(encoding="utf-8"))
    atual = json.loads(RELATORIO.read_text(encoding="utf-8")) if RELATORIO.exists() else {}
    atual["regressao_suite_principal"] = {
        "comando": "testar_prototipo.py --sem-exportar --relatorio <scratchpad> (não sobrescreve "
        "resultados/resultados.json)",
        "inicio": rel.get("inicio"),
        "fim": rel.get("fim"),
        "cenarios": [
            {
                "id": c["id"],
                "passou": c["passou"],
                **({"erro": c["erro"][:600]} if c.get("erro") else {}),
            }
            for c in rel["cenarios"]
        ],
        "segredos_no_relatorio": rel.get("segredos_no_relatorio"),
        "limpeza": rel.get("limpeza"),
    }
    RELATORIO.write_text(json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")
    for c in atual["regressao_suite_principal"]["cenarios"]:
        print(f"{c['id']:>4}  {'PASSOU' if c['passou'] else 'FALHOU'}  {c.get('erro', '')[:160]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manter", action="store_true")
    ap.add_argument("--sem-exportar", action="store_true")
    ap.add_argument("--apenas", default="")
    ap.add_argument("--anexar-regressao", type=Path)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    if a.anexar_regressao:
        return anexar_regressao(a.anexar_regressao)
    if n8n_local.existe():
        print("contêiner pcpr-prototipo-n8n já existe (outra execução?) — abortado", flush=True)
        return 2
    SAIDA.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="pcpr-whatsapp-"))
    procs: list[subprocess.Popen] = []
    relatorio: dict[str, Any] = {
        "inicio": datetime.now(FUSO).isoformat(timespec="seconds"),
        "imagem": n8n_local.IMAGEM,
        "python": sys.version.split()[0],
        "garantias": {
            "chamadas_reais_a_meta": "nenhuma: Graph API simulada em 127.0.0.1:8767; no contêiner "
            + ", ".join(h.split(":")[0] for h in SUMIDOURO)
            + " → 127.0.0.1; SSRF do n8n libera só host.docker.internal",
            "numeros": "fictícios +5500… (DDD 00 não existe)",
            "segredos": "sintéticos, gerados nesta execução e removidos do relatório",
        },
        "cenarios": [],
    }
    filtro = {x.strip().upper() for x in a.apenas.split(",") if x.strip()}
    try:
        procs = subir_simuladores(tmp)
        imp = tmp / "importar"
        cw.construir(imp / "workflows", whatsapp=True)
        (imp / "credenciais.json").write_text(json.dumps(credenciais()), encoding="utf-8")
        t0 = time.time()
        ids = list(cw.ARQUIVOS) + list(cw.ARQUIVOS_WHATSAPP)
        log_prep = n8n_local.preparar(imp, SEGREDOS["n8n_cripto"], ids)
        relatorio["preparacao"] = {
            "segundos": round(time.time() - t0, 1),
            "saida_cli": log_prep.strip().splitlines()[-18:],
        }
        shutil.rmtree(imp / "workflows", ignore_errors=True)
        (imp / "credenciais.json").unlink()
        n8n_local.subir(SEGREDOS["n8n_cripto"], hosts_extras=SUMIDOURO)
        T["subida_n8n"] = time.time()
        relatorio["primeira_subida_s"] = round(n8n_local.esperar_pronto(), 1)
        esperar(lambda: http("GET", f"{N8N}/webhook/whatsapp")[0] == 403, 60, "W7 não registrou")
        relatorio["config_efetiva"] = n8n_local.config_efetiva()
        resultados: dict[str, dict] = {}
        for cid, variante, nome, fn in CENARIOS:
            if cid == "VARRER":
                if not filtro or "TW13" in filtro:
                    try:
                        varrer(variante)
                    except Exception as exc:
                        relatorio.setdefault("erros_varredura", []).append(repr(exc)[:500])
                continue
            if filtro and cid not in filtro:
                continue
            inicio = time.time()
            item = resultados.setdefault(cid, {"id": cid, "nome": nome, "passou": True})
            sub: dict[str, Any] = {}
            try:
                sub["evidencia"] = fn(variante) if variante != "-" else fn()
                sub["passou"] = True
            except Exception as exc:
                sub["passou"] = False
                sub["erro"] = f"{type(exc).__name__}: {exc}"[:3000]
                sub["traceback"] = traceback.format_exc()[-2500:]
                sub["log_n8n"] = n8n_local.logs(30).splitlines()[-30:]
            sub["segundos"] = round(time.time() - inicio, 1)
            if variante == "-":
                item.update(sub)
            else:
                item.setdefault("variantes", {})[variante] = sub
                item["passou"] = item["passou"] and sub["passou"]
            print(
                f"{cid} {variante}: {'PASSOU' if sub['passou'] else 'FALHOU'} "
                f"({sub['segundos']}s) {sub.get('erro', '')[:300]}",
                flush=True,
            )
        relatorio["cenarios"] = list(resultados.values())
        relatorio["varreduras"] = T["varreduras"]
        relatorio["n8n_log_final"] = n8n_local.logs(40).splitlines()[-40:]
        relatorio["n8n_log_menciona_facebook"] = "facebook" in n8n_local.logs(5000).lower()
        if a.manter:
            print("mantido: contêiner e simuladores no ar", flush=True)
            return 0
        n8n_local.parar()
        if not a.sem_exportar:
            try:
                relatorio["exportacao"] = exportar_workflows(tmp)
            except Exception as exc:
                relatorio["exportacao"] = {"erro": repr(exc)}
        ok = all(c["passou"] for c in relatorio["cenarios"]) and "erro" not in relatorio.get(
            "exportacao", {}
        )
        return 0 if ok else 1
    finally:
        if not a.manter:
            n8n_local.remover()
            for p in procs:
                p.terminate()
                try:
                    p.wait(10)
                except subprocess.TimeoutExpired:
                    p.kill()
            shutil.rmtree(tmp, ignore_errors=True)
            time.sleep(1)
            relatorio["limpeza"] = {
                "conteiner_existe": n8n_local.existe(),
                "volume_existe": bool(
                    n8n_local.docker(
                        "volume", "ls", "-q", "--filter", f"name={n8n_local.VOLUME}", check=False
                    ).stdout.strip()
                ),
                "portas_ainda_abertas": portas_abertas(),
            }
        relatorio["fim"] = datetime.now(FUSO).isoformat(timespec="seconds")
        texto = json.dumps(relatorio, ensure_ascii=False, indent=2, default=str)
        vazados = [k for k, v in SEGREDOS.items() if v in texto]
        for k in vazados:
            texto = texto.replace(SEGREDOS[k], f"<{k}-removido>")
        final = json.loads(texto)
        final["segredos_no_relatorio"] = vazados
        anterior = json.loads(RELATORIO.read_text(encoding="utf-8")) if RELATORIO.exists() else {}
        if "regressao_suite_principal" in anterior and not filtro:
            final["regressao_suite_principal_anterior"] = anterior["regressao_suite_principal"]
        if not filtro:
            RELATORIO.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            (tmp.parent / "resultados-whatsapp-parcial.json").write_text(
                json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        for c in final["cenarios"]:
            print(f"{c['id']:>5}  {'PASSOU' if c['passou'] else 'FALHOU'}  {c['nome']}")


if __name__ == "__main__":
    sys.exit(main())
