"""Orquestra o protótipo inteiro e faz as asserções T1–T12 + métricas.

    .venv/Scripts/python.exe docs/automacao/prototipo/testar_prototipo.py
        [--manter]        não remove contêiner/simuladores no fim (depuração)
        [--so-subir]      sobe tudo e para (sem testes), implica --manter
        [--sem-exportar]  não sobrescreve docs/automacao/n8n/*.json
        [--apenas T1,T9,LAT]  roda só esses cenários (LAT = medição de latência)
        [--relatorio CAMINHO] grava o relatório em outro arquivo (regressão sem sobrescrever
                              resultados/resultados.json)

Sobe os dois simuladores (127.0.0.1:8765 e :8766), gera segredos sintéticos novos, importa
credenciais e workflows num n8n 2.43.7 descartável (127.0.0.1:5678), publica-os SÓ localmente,
roda os cenários contra o estado dos simuladores e, no fim, despublica, exporta os workflows
(`"active": false`) e remove contêiner, volume e processos. Resultado em
`resultados/resultados.json`.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import re
import secrets
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import unittest
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import construir_workflows as cw  # noqa: E402
import n8n_local  # noqa: E402
from regra_vespera import FUSO  # noqa: E402

REPO = RAIZ.parents[2]
DOCS_N8N = REPO / "docs" / "automacao" / "n8n"
SCHEMA = REPO / "docs" / "automacao" / "contratos" / "evento-integracao.schema.json"
SAIDA = RAIZ / "resultados"
SIM = "http://127.0.0.1:8765"
CANAL = "http://127.0.0.1:8766"
N8N = n8n_local.URL

SEGREDOS = {
    "token_api": secrets.token_urlsafe(32),
    "hmac": secrets.token_hex(32),
    "canal_chave": secrets.token_urlsafe(24),
    "canal_webhook": secrets.token_urlsafe(24),
    "disparo": secrets.token_urlsafe(24),
    "n8n_cripto": secrets.token_hex(32),
}


# ===================================================================== HTTP mínimo


def http(
    metodo: str, url: str, corpo: Any = None, cab: dict | None = None, timeout: float = 30
) -> tuple[int, Any]:
    dados = None
    cabecalhos = dict(cab or {})
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        cabecalhos.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(
        url,
        data=dados,
        headers=cabecalhos,
        method=metodo,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            bruto = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        bruto, status = exc.read(), exc.code
    try:
        return status, json.loads(bruto) if bruto else None
    except ValueError:
        return status, bruto.decode("utf-8", "replace")


def sim(caminho: str, corpo: Any = None) -> Any:
    st, b = http("POST" if corpo is not None else "GET", SIM + caminho, corpo)
    assert st == 200, f"simulador PCPR {caminho} → {st} {b}"
    return b


def canal(caminho: str, corpo: Any = None) -> Any:
    st, b = http("POST" if corpo is not None else "GET", CANAL + caminho, corpo)
    assert st == 200, f"simulador canal {caminho} → {st} {b}"
    return b


# ===================================================================== utilidades de teste


class Falha(AssertionError):
    pass


def checar(cond: Any, msg: str) -> None:
    if not cond:
        raise Falha(msg)


def esperar(fn: Callable[[], Any], timeout: float, msg: str, intervalo: float = 0.25) -> Any:
    fim = time.time() + timeout
    while True:
        valor = fn()
        if valor:
            return valor
        if time.time() > fim:
            raise Falha(f"tempo esgotado ({timeout}s): {msg}")
        time.sleep(intervalo)


def est() -> dict:
    return sim("/_sim/estado")


def est_canal() -> dict:
    return canal("/_sim/estado")


def com(e: dict, cid: int) -> dict:
    return next(c for c in e["comunicacoes"] if c["id"] == cid)


def aceitas(c: dict, cid: int) -> list[dict]:
    return [t for t in c["tentativas"] if t["comunicacao_id"] == cid and t["aceita"]]


def tentativas(c: dict, cid: int) -> list[dict]:
    return [t for t in c["tentativas"] if t["comunicacao_id"] == cid]


def chamadas(e: dict, padrao: str, cid: int | None = None) -> list[dict]:
    return [
        r
        for r in e["log"]
        if re.fullmatch(padrao, r["rota"]) and (cid is None or r.get("comunicacao_id") == cid)
    ]


def excecoes_de(e: dict, cid: int) -> list[dict]:
    return [x for x in e["excecoes"] if (x.get("recurso") or {}).get("id") == cid]


def resetar(lease: int = 600) -> None:
    sim("/_sim/resetar", {})
    sim("/_sim/config", {"lease_segundos": lease})
    canal("/_sim/resetar", {})


def agora_sp() -> datetime:
    return datetime.now(FUSO)


def viagem(horas: float, entregar: bool = True) -> dict:
    return sim(
        "/_sim/viagens",
        {"inicio": (agora_sp() + timedelta(hours=horas)).isoformat(), "entregar": entregar},
    )


def comunicacao(entregar: bool = True) -> dict:
    return sim("/_sim/comunicacoes", {"entregar": entregar})


def evento(resp: dict, tipo: str = "comunicacao.agendada") -> dict:
    return next(e for e in resp["eventos"] if e["tipo"] == tipo)


def entregar(evento_id: str, modo: str = "normal") -> dict:
    return sim(f"/_sim/eventos/{evento_id}/entregar", {"modo": modo})


def reconciliar() -> tuple[int, Any]:
    return http(
        "POST",
        f"{N8N}/webhook/pcpr-reconciliar",
        {},
        {"X-Disparo-Token": SEGREDOS["disparo"]},
        timeout=120,
    )


def assentar(segundos: float = 3.0) -> None:
    """Dá tempo para efeitos indevidos aparecerem antes de afirmar que NÃO aconteceram."""
    time.sleep(segundos)


# ===================================================================== validação do envelope


def validar(valor: Any, esquema: dict, caminho: str = "$") -> list[str]:
    """Validador mínimo para as palavras-chave usadas no schema do envelope."""
    erros: list[str] = []
    tipos = esquema.get("type")
    if tipos:
        tipos = tipos if isinstance(tipos, list) else [tipos]
        mapa = {
            "object": dict,
            "string": str,
            "integer": int,
            "array": list,
            "null": type(None),
            "boolean": bool,
        }
        if not any(
            isinstance(valor, mapa[t]) and not (t == "integer" and isinstance(valor, bool))
            for t in tipos
        ):
            return [f"{caminho}: tipo {type(valor).__name__} ∉ {tipos}"]
    if "const" in esquema and valor != esquema["const"]:
        erros.append(f"{caminho}: ≠ const {esquema['const']}")
    if "enum" in esquema and valor not in esquema["enum"]:
        erros.append(f"{caminho}: {valor!r} fora do enum")
    if "minimum" in esquema and isinstance(valor, int) and valor < esquema["minimum"]:
        erros.append(f"{caminho}: < {esquema['minimum']}")
    uuid_re = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    if (
        esquema.get("format") == "uuid"
        and isinstance(valor, str)
        and not re.fullmatch(uuid_re, valor)
    ):
        erros.append(f"{caminho}: não é uuid")
    if esquema.get("format") == "date-time" and isinstance(valor, str):
        try:
            datetime.fromisoformat(valor.replace("Z", "+00:00"))
        except ValueError:
            erros.append(f"{caminho}: data-hora inválida")
    if isinstance(valor, dict):
        props = esquema.get("properties", {})
        for req in esquema.get("required", []):
            if req not in valor:
                erros.append(f"{caminho}: falta {req}")
        if esquema.get("additionalProperties") is False:
            erros += [f"{caminho}: campo extra {k}" for k in valor if k not in props]
        for k, sub in props.items():
            if k in valor:
                erros += validar(valor[k], sub, f"{caminho}.{k}")
    return erros


# ===================================================================== cenários


def t1() -> dict:
    resetar()
    r = viagem(3)
    cid = r["comunicacao_id"]
    status = [e["entrega"]["status"] for e in r["eventos"]]
    checar(status == [202, 202], f"n8n deveria responder 202 aos 2 eventos, veio {status}")
    esperar(lambda: com(est(), cid)["estado"] == "enviada", 30, "comunicação não ficou enviada")
    assentar()
    e, c = est(), est_canal()
    envios = aceitas(c, cid)
    resultados = [
        x
        for x in chamadas(e, r"/comunicacoes/\d+/resultado", cid)
        if x["status"] == 200 and not x.get("replay")
    ]
    reservas = [x for x in chamadas(e, r"/comunicacoes/\d+/reservar", cid) if x["status"] == 200]
    checar(len(envios) == 1, f"esperado 1 envio, houve {len(envios)}")
    checar(len(resultados) == 1, f"esperado 1 resultado, houve {len(resultados)}")
    checar(len(reservas) == 1, f"esperada 1 reserva, houve {len(reservas)}")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    erros = [m for ev in e["eventos"] for m in validar(ev["envelope"], schema)]
    checar(not erros, f"envelope fora do schema: {erros}")
    T_ESTADO["t1"] = {"cid": cid, "evento_id": evento(r)["id"]}
    return {
        "comunicacao_id": cid,
        "respostas_n8n": status,
        "envios_no_canal": len(envios),
        "resultados_registrados": len(resultados),
        "reservas": len(reservas),
        "estado_final": com(e, cid)["estado"],
        "provedor_mensagem_id": com(e, cid)["provedor_mensagem_id"],
        "envelopes_validados_contra_schema": len(e["eventos"]),
        "chave_idempotencia_reserva": reservas[0]["chave"],
    }


T_ESTADO: dict[str, Any] = {}


def t2() -> dict:
    cid, eid = T_ESTADO["t1"]["cid"], T_ESTADO["t1"]["evento_id"]
    antes = est()
    n_log = len(chamadas(antes, r"/comunicacoes/\d+/.*", cid))
    respostas = [entregar(eid)["status"] for _ in range(2)]
    checar(respostas == [202, 202], f"reentrega deveria receber 202, veio {respostas}")
    assentar(4)
    e, c = est(), est_canal()
    novas = chamadas(e, r"/comunicacoes/\d+/.*", cid)[n_log:]
    checar(len(aceitas(c, cid)) == 1, f"reentrega gerou envio: {len(aceitas(c, cid))}")
    checar(not novas, f"reentrega chegou ao PCPR (dedup do n8n falhou): {novas}")
    # (b) a MESMA entrega 5x em paralelo. A dedup do n8n é ler-alterar-gravar numa linha JSON
    # sem trava (deduplication-helper.js), então pode deixar passar mais de uma; a garantia
    # final de "1 envio" é a reserva no PCPR (só uma execução ganha; as outras levam 409).
    r = comunicacao(entregar=False)
    cid2, eid2 = r["comunicacao_id"], evento(r)["id"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        paralelas = list(ex.map(lambda _: entregar(eid2)["status"], range(5)))
    esperar(lambda: len(aceitas(est_canal(), cid2)) == 1, 30, "entrega paralela não enviou")
    assentar(4)
    e, c = est(), est_canal()
    reservas = chamadas(e, r"/comunicacoes/\d+/reservar", cid2)
    checar(len(aceitas(c, cid2)) == 1, f"paralelo gerou {len(aceitas(c, cid2))} envios")
    checar(sum(1 for x in reservas if x["status"] == 200) == 1, f"reservas: {reservas}")
    # (c) dedup do n8n contornada de propósito: evento NOVO (outro id) para a mesma comunicação
    # já enviada. Passa pela dedup, chega ao W2 e o PCPR barra no reservar (409).
    n_res = len(reservas)
    re_ev = sim(f"/_sim/comunicacoes/{cid2}/reemitir", {})["eventos"][0]
    esperar(
        lambda: len(chamadas(est(), r"/comunicacoes/\d+/reservar", cid2)) > n_res,
        30,
        "evento reemitido não chegou ao reservar",
    )
    assentar(3)
    e, c = est(), est_canal()
    extra = chamadas(e, r"/comunicacoes/\d+/reservar", cid2)[n_res:]
    checar([x["status"] for x in extra] == [409], f"reemitido deveria levar 409: {extra}")
    checar(len(aceitas(c, cid2)) == 1, "evento reemitido gerou segundo envio")
    return {
        "a_reentregas_sequenciais": {
            "reentregas": 2,
            "respostas_n8n": respostas,
            "envios_no_canal": len(aceitas(c, cid)),
            "chamadas_novas_ao_pcpr": len(novas),
            "observacao": "barrado no n8n (Remove Duplicates entre execuções)",
        },
        "b_cinco_entregas_simultaneas": {
            "respostas_n8n": paralelas,
            "execucoes_que_passaram_pela_dedup_e_tentaram_reservar": len(reservas),
            "reservas_por_status": {
                str(st): sum(1 for x in reservas if x["status"] == st)
                for st in sorted({x["status"] for x in reservas})
            },
            "envios_no_canal": len(aceitas(c, cid2)),
        },
        "c_evento_com_outro_id_mesma_comunicacao": {
            "resposta_n8n": re_ev["entrega"]["status"],
            "reserva": [x["status"] for x in extra],
            "codigo": extra[0].get("codigo"),
            "envios_no_canal": len(aceitas(c, cid2)),
            "observacao": "a dedup do n8n não pega (id novo); o PCPR barra",
        },
    }


def t3() -> dict:
    resetar()
    r = comunicacao(entregar=False)
    cid, eid = r["comunicacao_id"], evento(r)["id"]
    modos = [
        "assinatura_invalida",
        "antigo",
        "corpo_adulterado",
        "sem_assinatura",
        "outro_ambiente",
    ]
    respostas = {m: entregar(eid, m)["status"] for m in modos}
    checar(all(s == 401 for s in respostas.values()), f"esperado 401 em todos: {respostas}")
    assentar(4)
    e, c = est(), est_canal()
    checar(not tentativas(c, cid), "houve tentativa de envio com evento inválido")
    checar(not chamadas(e, r"/comunicacoes/\d+/reservar", cid), "evento inválido chegou ao PCPR")
    checar(com(e, cid)["estado"] == "agendada", "comunicação mudou de estado")
    # controle positivo: o MESMO evento, assinado corretamente, passa (e a dedup não foi
    # "envenenada" pelas tentativas inválidas, que são barradas antes dela)
    ok = entregar(eid)["status"]
    checar(ok == 202, f"controle positivo deveria dar 202, deu {ok}")
    esperar(lambda: len(aceitas(est_canal(), cid)) == 1, 30, "controle positivo não enviou")
    return {
        "respostas_invalidas": respostas,
        "envios_com_eventos_invalidos": 0,
        "controle_positivo": {"status": ok, "envios": 1},
    }


def t4() -> dict:
    resetar()
    # (a) reagendada: evento antigo chega depois do reagendamento (fora de ordem)
    r = viagem(3, entregar=False)
    c1, ev_antigo = r["comunicacao_id"], evento(r)["id"]
    novo_inicio = (agora_sp() + timedelta(days=10)).isoformat()
    rg = sim(
        f"/_sim/viagens/{r['viagem_id']}/reagendar", {"inicio": novo_inicio, "entregar": False}
    )
    c2 = rg["nova_comunicacao_id"]
    st_antigo = entregar(ev_antigo)["status"]
    esperar(
        lambda: chamadas(est(), r"/comunicacoes/\d+/reservar", c1),
        30,
        "W2 não tentou reservar a comunicação obsoleta",
    )
    outros = {e["tipo"]: entregar(e["id"])["status"] for e in rg["eventos"]}
    assentar()
    e, c = est(), est_canal()
    res1 = chamadas(e, r"/comunicacoes/\d+/reservar", c1)
    checar([x["status"] for x in res1] == [409], f"reserva obsoleta deveria ser 409: {res1}")
    checar(res1[0].get("codigo") == "obsoleta", f"código {res1[0].get('codigo')}")
    checar(not aceitas(c, c1) and not aceitas(c, c2), "houve envio de comunicação obsoleta")
    checar(
        not chamadas(e, r"/comunicacoes/\d+/reservar", c2),
        "nova comunicação (futura) foi reservada antes da hora",
    )
    checar(com(e, c2)["estado"] == "agendada", "nova comunicação deveria continuar agendada")
    # (b) versão antiga da MESMA comunicação (If-Match por X-PCPR-Versao-Esperada)
    r2 = comunicacao(entregar=False)
    c3, ev_v1 = r2["comunicacao_id"], evento(r2)["id"]
    nv = sim(f"/_sim/comunicacoes/{c3}/nova_versao", {"entregar": False})
    st_v1 = entregar(ev_v1)["status"]
    esperar(lambda: chamadas(est(), r"/comunicacoes/\d+/reservar", c3), 30, "v1 não reservou")
    assentar(2)
    checar(not aceitas(est_canal(), c3), "versão antiga foi enviada")
    res3 = chamadas(est(), r"/comunicacoes/\d+/reservar", c3)
    checar(
        res3[0]["status"] == 409 and res3[0].get("codigo") == "conflito_de_versao",
        f"esperado 409 conflito_de_versao: {res3}",
    )
    st_v2 = entregar(evento(nv)["id"])["status"]
    esperar(lambda: len(aceitas(est_canal(), c3)) == 1, 30, "versão atual não foi enviada")
    return {
        "a_reagendada": {
            "comunicacao_antiga": c1,
            "resposta_n8n": st_antigo,
            "reserva": [x["status"] for x in res1],
            "codigo": res1[0].get("codigo"),
            "envios": 0,
            "nova_comunicacao": c2,
            "nova_enviar_em": com(e, c2)["enviar_em"],
            "eventos_do_reagendamento": outros,
        },
        "b_versao_antiga": {
            "comunicacao": c3,
            "evento_v1": st_v1,
            "reserva_v1": [res3[0]["status"], res3[0].get("codigo")],
            "evento_v2": st_v2,
            "envios_v2": 1,
        },
    }


def t5() -> dict:
    resetar()
    # (a) chave geral desligada antes: W2 lê /estado e encerra sem reservar
    sim("/_sim/automacao", {"ligada": False, "motivo": "teste T5a"})
    ra = comunicacao()
    ca = ra["comunicacao_id"]
    esperar(lambda: any(x["rota"] == "/estado" for x in est()["log"]), 20, "W2 não leu /estado")
    assentar()
    e = est()
    checar(not chamadas(e, r"/comunicacoes/\d+/reservar", ca), "reservou com automação desligada")
    checar(com(e, ca)["estado"] == "agendada", "deveria continuar agendada")
    # (b) desligada ENTRE a consulta e a reserva → 423 no reservar
    sim("/_sim/automacao", {"ligada": True, "desligar_apos_estado": True})
    rb = comunicacao()
    cb = rb["comunicacao_id"]
    esperar(lambda: chamadas(est(), r"/comunicacoes/\d+/reservar", cb), 20, "W2 não reservou")
    assentar()
    e, c = est(), est_canal()
    resb = chamadas(e, r"/comunicacoes/\d+/reservar", cb)
    checar([x["status"] for x in resb] == [423], f"esperado 423: {[x['status'] for x in resb]}")
    checar(not tentativas(c, ca) and not tentativas(c, cb), "houve envio com automação desligada")
    checar(com(e, cb)["estado"] == "agendada", "deveria continuar agendada após 423")
    # (c) religada: a reconciliação entrega o que ficou para trás, uma vez cada
    sim("/_sim/automacao", {"ligada": True})
    st, corpo = reconciliar()
    checar(st == 200, f"reconciliação → {st} {corpo}")
    e, c = est(), est_canal()
    checar(
        len(aceitas(c, ca)) == 1 and len(aceitas(c, cb)) == 1,
        "após religar, cada uma deveria sair exatamente 1 vez",
    )
    return {
        "a_desligada_antes": {"comunicacao": ca, "reservas": 0, "estado": "agendada"},
        "b_desligada_no_meio": {
            "comunicacao": cb,
            "reserva": [x["status"] for x in resb],
            "estado": "agendada",
            "envios": 0,
        },
        "c_religada_reconciliacao": {"resposta": corpo, "envios": {ca: 1, cb: 1}},
    }


def t6() -> dict:
    resetar()
    canal("/_sim/modo", {"modo": "falha_1x"})
    cid = comunicacao()["comunicacao_id"]
    esperar(lambda: com(est(), cid)["estado"] == "enviada", 30, "não ficou enviada")
    assentar()
    e, c = est(), est_canal()
    t = tentativas(c, cid)
    res = [x for x in chamadas(e, r"/comunicacoes/\d+/resultado", cid) if x["status"] == 200]
    checar(
        [x["status"] for x in t] == [500, 200], f"tentativas no canal: {[x['status'] for x in t]}"
    )
    checar(len(aceitas(c, cid)) == 1, "deveria haver 1 envio efetivo")
    checar(len(res) == 1 and res[0].get("resultado") == "enviada", f"resultados: {res}")
    return {
        "tentativas_no_canal": [x["status"] for x in t],
        "envios_efetivos": 1,
        "resultados": [x.get("resultado") for x in res],
        "intervalo_entre_tentativas_s": round(t[1]["em"] - t[0]["em"], 2),
    }


def t7() -> dict:
    resetar()
    canal("/_sim/modo", {"modo": "sempre_500"})
    cid = comunicacao()["comunicacao_id"]
    esperar(lambda: excecoes_de(est(), cid), 40, "exceção não foi aberta")
    assentar(5)
    n1 = len(tentativas(est_canal(), cid))
    st, corpo = reconciliar()
    checar(st == 200, f"reconciliação → {st} {corpo}")
    assentar(5)
    e, c = est(), est_canal()
    n2 = len(tentativas(c, cid))
    ex = excecoes_de(e, cid)
    checar(n1 == 3, f"esperadas 3 tentativas (maxTries), houve {n1}")
    checar(n2 == n1, f"continuou tentando depois de desistir: {n1} → {n2}")
    checar(not aceitas(c, cid), "nenhum envio deveria ter sido aceito")
    checar(len(ex) == 1 and ex[0]["motivo"] == "limite_tentativas", f"exceções: {ex}")
    checar(com(e, cid)["estado"] == "falhou", f"estado {com(e, cid)['estado']}")
    return {
        "tentativas": n1,
        "tentativas_apos_reconciliacao": n2,
        "reconciliacao": corpo,
        "estado": "falhou",
        "excecao": {
            k: ex[0][k] for k in ("motivo", "origem", "fluxo", "detalhe", "execucao_orquestrador")
        },
    }


def t8() -> dict:
    resetar()
    r = comunicacao(entregar=False)
    cid = r["comunicacao_id"]
    checar(not any(ev["entregas"] for ev in est()["eventos"]), "evento não deveria ter saído")
    st1, c1 = reconciliar()
    checar(st1 == 200 and c1 and c1.get("devidas") == 1, f"1ª reconciliação: {st1} {c1}")
    esperar(lambda: com(est(), cid)["estado"] == "enviada", 20, "não enviou")
    st2, c2 = reconciliar()
    checar(st2 == 200 and c2.get("devidas") == 0, f"2ª reconciliação: {st2} {c2}")
    assentar()
    n = len(aceitas(est_canal(), cid))
    checar(n == 1, f"esperado 1 envio, houve {n}")
    return {
        "evento_entregue_ao_n8n": False,
        "reconciliacao_1": c1,
        "reconciliacao_2": c2,
        "envios": n,
    }


def t9() -> dict:
    resetar()
    # Canal simulado com rótulo "email" (o previsto). Até o WA-3 o rótulo era o fictício
    # "whatsapp"; agora o WhatsApp do simulador do PCPR nasce BLOQUEADO e tem suíte própria
    # (testar_whatsapp.py). O remetente continua com cara de telefone sintético de propósito:
    # é o marcador "destino" que o T13 procura no banco do n8n.
    mid = f"msg.sim.T9.{secrets.token_hex(4)}"
    entrada = {"mensagem_id": mid, "remetente": "+5500000000042", "canal": "email"}
    r1 = canal("/_sim/inbound", entrada)
    checar(r1["status"] == 200, f"webhook W4 respondeu {r1['status']}")
    esperar(lambda: len(chamadas(est(), r"/recebimentos")) == 1, 30, "1º recebimento não chegou")
    r2 = canal("/_sim/inbound", entrada)
    esperar(lambda: len(chamadas(est(), r"/recebimentos")) == 2, 30, "2º recebimento não chegou")
    assentar()
    e = est()
    posts = chamadas(e, r"/recebimentos")
    novos = [x for x in e["recebimentos"] if x["estado"] != "duplicado"]
    checar(len(novos) == 1, f"esperado 1 recebimento, houve {len(novos)}")
    checar(len(e["recebimentos"]) == 1, f"registros: {len(e['recebimentos'])}")
    checar(posts[1].get("replay") is True, "2ª chamada deveria ser repetição idempotente")
    checar(novos[0]["sha256"] == r1["arquivo"]["sha256"], "SHA-256 não confere com o arquivo")
    checar(
        posts[0]["chave"] == posts[1]["chave"] == f"recebimento:email:{mid}",
        f"chaves: {[p['chave'] for p in posts]}",
    )
    # (extra) consulta do recebimento pela API
    st, rec = http(
        "GET",
        f"{SIM}/api/automacao/v1/recebimentos/{novos[0]['id']}",
        cab={"Authorization": f"Bearer {SEGREDOS['token_api']}"},
    )
    checar(st == 200 and rec["estado"] == "aceito_para_processamento", f"GET recebimento {rec}")
    return {
        "webhooks_do_canal": [r1["status"], r2["status"]],
        "posts_recebimentos": len(posts),
        "recebimentos": 1,
        "segunda_chamada_replay": True,
        "chave": posts[0]["chave"],
        "sha256_conferido": True,
        "tamanho_bytes": novos[0]["tamanho"],
        "estado": rec["estado"],
    }


def t10() -> dict:
    resetar(lease=15)
    canal("/_sim/modo", {"modo": "lento", "atraso_s": 8})
    grupo_a = [comunicacao() for _ in range(4)]
    ids_a = [r["comunicacao_id"] for r in grupo_a]
    checar(all(evento(r)["entrega"]["status"] == 202 for r in grupo_a), "eventos A não aceitos")
    esperar(lambda: len(est_canal()["tentativas"]) >= 1, 20, "nada chegou ao canal antes da queda")
    time.sleep(1)
    antes_queda = {cid: com(est(), cid)["estado"] for cid in ids_a}
    n8n_local.parar_abrupto()  # queda no meio (SIGKILL), execuções em andamento
    t_queda = time.time()
    grupo_b = [comunicacao() for _ in range(2)]  # eventos se perdem: n8n fora do ar
    ids_b = [r["comunicacao_id"] for r in grupo_b]
    perdidos = [evento(r)["entrega"] for r in grupo_b]
    checar(
        all(p["status"] is None and p["erro"] for p in perdidos), f"B deveria falhar: {perdidos}"
    )
    canal("/_sim/modo", {"modo": "ok"})
    n8n_local.iniciar()
    pronto_s = n8n_local.esperar_pronto()
    reentrega = entregar(evento(grupo_a[0])["id"])["status"]  # mesmo id após o reinício
    st, corpo = reconciliar()
    checar(st == 200, f"reconciliação pós-reinício: {st} {corpo}")
    # reservas órfãs vencem (lease 15 s) e viram exceção "resultado_desconhecido"
    esperar(
        lambda: all(com(est(), cid)["estado"] in ("enviada", "falhou") for cid in ids_a),
        60,
        "reservas órfãs não foram resolvidas",
    )
    st2, corpo2 = reconciliar()
    checar(st2 == 200, f"reconciliação final → {st2} {corpo2}")
    assentar(4)
    e, c = est(), est_canal()
    resumo = {}
    for cid in ids_a + ids_b:
        x = com(e, cid)
        resumo[cid] = {
            "grupo": "A" if cid in ids_a else "B",
            "antes_da_queda": antes_queda.get(cid),
            "estado": x["estado"],
            "resultado": x["resultado"],
            "envios": len(aceitas(c, cid)),
            "excecoes": [z["motivo"] for z in excecoes_de(e, cid)],
        }
        checar(len(aceitas(c, cid)) <= 1, f"comunicação {cid} DUPLICADA no canal")
    for cid in ids_b:
        checar(
            resumo[cid]["estado"] == "enviada" and resumo[cid]["envios"] == 1,
            f"B {cid} não foi completada pela reconciliação: {resumo[cid]}",
        )
    for cid in ids_a:
        r = resumo[cid]
        ok = (r["estado"] == "enviada" and r["envios"] == 1) or (
            r["estado"] == "falhou"
            and r["resultado"] == "resultado_desconhecido"
            and r["excecoes"] == ["resultado_desconhecido"]
        )
        checar(ok, f"A {cid} terminou em estado inconsistente: {r}")
    checar(
        not [x for x in e["comunicacoes"] if x["estado"] == "agendada"],
        "sobrou comunicação agendada vencida",
    )
    return {
        "lease_s": 15,
        "tempo_para_voltar_s": round(pronto_s, 1),
        "reentrega_evento_A_pos_reinicio": reentrega,
        "reconciliacao": corpo,
        "reconciliacao_final": corpo2,
        "por_comunicacao": resumo,
        "duplicados_no_canal": 0,
        "segundos_entre_queda_e_volta": round(time.time() - t_queda, 1),
    }


def t12() -> dict:
    resetar()
    sim("/_sim/automacao", {"falhar_estado": 10})
    cid = comunicacao()["comunicacao_id"]
    ex = esperar(
        lambda: [x for x in est()["excecoes"] if str(x["fluxo"]).startswith("n8n:")],
        40,
        "W5 não abriu exceção",
    )
    assentar()
    e, c = est(), est_canal()
    checar(not tentativas(c, cid), "não deveria ter enviado")
    checar(com(e, cid)["estado"] == "agendada", "deveria continuar agendada")
    sim("/_sim/automacao", {"falhar_estado": 0})
    st, corpo = reconciliar()
    checar(st == 200, f"reconciliação → {st} {corpo}")
    esperar(lambda: len(aceitas(est_canal(), cid)) == 1, 20, "reconciliação não enviou")
    T_ESTADO["t12_reconciliacao"] = corpo
    return {
        "excecoes_w5": [
            {k: x[k] for k in ("fluxo", "motivo", "detalhe", "execucao_orquestrador")} for x in ex
        ],
        "envio_apos_normalizar": 1,
        "reconciliacao": T_ESTADO.get("t12_reconciliacao"),
    }


def metricas_latencia() -> dict:
    resetar()
    canal("/_sim/modo", {"modo": "ok"})

    nao_sairam: list[dict] = []

    def um() -> tuple[int, float, float] | None:
        r = comunicacao()
        ent = evento(r)["entrega"]
        cid = r["comunicacao_id"]
        try:
            esperar(lambda: aceitas(est_canal(), cid), 60, f"latência: {cid} não saiu", 0.1)
        except Falha:
            e = est()
            nao_sairam.append(
                {
                    "comunicacao_id": cid,
                    "entrega_do_evento": ent,
                    "estado": com(e, cid)["estado"],
                    "chamadas_pcpr": [x for x in e["log"] if x.get("comunicacao_id") == cid],
                    "excecoes": e["excecoes"][-3:],
                }
            )
            return None
        return cid, ent["em"], ent["ms"]

    sequencial = [x for x in (um() for _ in range(20)) if x]
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        rajada = [x for x in ex.map(lambda _: um(), range(20)) if x]
    if nao_sairam:
        T_ESTADO["latencia_nao_sairam"] = nao_sairam
        T_ESTADO["latencia_log_n8n"] = n8n_local.logs(80).splitlines()
        raise Falha(f"{len(nao_sairam)} evento(s) sem envio em 60 s: {nao_sairam}")
    assentar()
    c, e = est_canal(), est()
    dup = [
        cid for cid in {t["comunicacao_id"] for t in c["tentativas"]} if len(aceitas(c, cid)) != 1
    ]
    checar(not dup, f"duplicados/ausentes na medição: {dup}")

    def pct(v: list[float], p: float) -> float:
        s = sorted(v)
        return round(s[max(0, math.ceil(p / 100 * len(s)) - 1)], 1)  # nearest-rank

    def resumo(amostras: list[tuple[int, float, float]]) -> dict:
        total, ate_202, ate_reserva = [], [], []
        for cid, t0, ms202 in amostras:
            total.append((aceitas(c, cid)[0]["em"] - t0) * 1000)
            ate_202.append(ms202)
            res = [x for x in chamadas(e, r"/comunicacoes/\d+/reservar", cid) if x["status"] == 200]
            ate_reserva.append((res[0]["ts"] - t0) * 1000)
        return {
            "evento_ate_envio_ms": {
                "p50": pct(total, 50),
                "p95": pct(total, 95),
                "min": round(min(total), 1),
                "max": round(max(total), 1),
                "media": round(statistics.mean(total), 1),
            },
            "evento_ate_resposta_202_ms": {"p50": pct(ate_202, 50), "p95": pct(ate_202, 95)},
            "evento_ate_reserva_no_pcpr_ms": {
                "p50": pct(ate_reserva, 50),
                "p95": pct(ate_reserva, 95),
            },
        }

    return {
        "sequencial_20": resumo(sequencial),
        "rajada_20_simultaneos": resumo(rajada),
        "definicao": "t0 = POST do evento ao n8n (emissor do PCPR); fim = canal simulado "
        "registra o envio. Mesmo relógio (mesma máquina).",
    }


T13_MARCADORES = {
    "link_km": "example.invalid/km/",
    "destino": "+550000000",
    "token_reserva": "rsvSIM",
}


def _varrer_execucoes() -> tuple[dict[str, int], dict[str, int], dict[str, dict[str, int]]]:
    """Copia o banco do n8n e conta os marcadores nas tabelas de execução.

    Valores, não nomes de campo: a cópia da definição do workflow (coluna workflowData) cita os
    nomes dos campos e fica fora da varredura."""
    import sqlite3
    import tempfile

    d = Path(tempfile.mkdtemp(prefix="pcpr-t13-"))
    try:
        checar(n8n_local.copiar_banco(d), "não consegui copiar o banco do n8n")
        con = sqlite3.connect(str(d / "database.sqlite"))
        tabelas = [
            r[0]
            for r in con.execute("select name from sqlite_master where type='table'")
            if str(r[0]).startswith("execution")
        ]
        ocorrencias = dict.fromkeys(T13_MARCADORES, 0)
        linhas: dict[str, int] = {}
        for t in tabelas:
            # nomes de tabela/coluna vêm do próprio sqlite_master/pragma do banco do protótipo
            linhas[t] = con.execute(f'select count(*) from "{t}"').fetchone()[0]  # noqa: S608
            colunas = [r[1] for r in con.execute(f"pragma table_info('{t}')")]
            for col in colunas:
                if col == "workflowData":
                    continue
                for (v,) in con.execute(f'select "{col}" from "{t}"'):  # noqa: S608
                    if isinstance(v, bytes):
                        v = v.decode("utf-8", "ignore")
                    if isinstance(v, str):
                        for k, m in T13_MARCADORES.items():
                            ocorrencias[k] += v.count(m)
        onde: dict[str, dict[str, int]] = {}
        if "execution_data" in tabelas and "execution_entity" in tabelas:
            consulta = (
                "select e.workflowId, e.status, e.mode, d.data "
                "from execution_data d join execution_entity e on e.id = d.executionId"
            )
            for wid, status, modo, dados in con.execute(consulta):
                texto = f"{dados or ''}"
                for k, m in T13_MARCADORES.items():
                    n = texto.count(m)
                    if n:
                        chave = f"{wid}|{status}|{modo}"
                        onde.setdefault(chave, dict.fromkeys(T13_MARCADORES, 0))[k] += n
        con.close()
        return ocorrencias, linhas, onde
    finally:
        shutil.rmtree(d, ignore_errors=True)


def t13() -> dict:
    """Nada sensível retido no n8n: destino, link-credencial e token de reserva.

    W2 e W4 rodam com saveData*Execution = "none" (revisão de segurança: o link de KM ou de
    assinatura é uma credencial). O n8n grava a execução com a entrada ao iniciar e, com "não
    salvar", só a marca como apagada; a remoção física roda a cada
    EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL minutos (1 no protótipo; padrão 15). O teste mede
    o que existe logo depois dos cenários e exige zero dentro de 3 minutos."""
    t0 = time.monotonic()
    inicial, linhas_inicio, onde_inicio = _varrer_execucoes()
    ocorrencias, linhas, onde = inicial, linhas_inicio, onde_inicio
    while any(ocorrencias.values()) and time.monotonic() - t0 < 180:
        time.sleep(20)
        ocorrencias, linhas, onde = _varrer_execucoes()
    T_ESTADO["t13_onde"] = onde
    checar(
        not any(ocorrencias.values()),
        f"dados sensíveis ainda retidos no n8n após 3 min: {ocorrencias}; onde: {onde}",
    )
    return {
        "logo_apos_os_cenarios": {"ocorrencias": inicial, "onde": onde_inicio},
        "segundos_ate_zerar": round(time.monotonic() - t0, 1),
        "tabelas_de_execucao_no_fim": linhas,
        "ocorrencias_no_fim": ocorrencias,
    }


CENARIOS: list[tuple[str, str, Callable[[], dict]]] = [
    ("T1", "evento válido → exatamente 1 envio e 1 resultado", t1),
    ("T2", "mesmo evento reenviado (em série e 5x em paralelo) → continua 1 envio", t2),
    ("T3", "assinatura inválida/antiga/adulterada/outro ambiente → 401 e 0 envio", t3),
    ("T4", "evento obsoleto (reagendada / versão antiga) → 409 e 0 envio", t4),
    ("T5", "automação desligada → 423/encerra, 0 envio, segue agendada", t5),
    ("T6", "canal falha 1x e aceita → 1 envio efetivo e 1 resultado", t6),
    ("T7", "canal sempre falha → exceção, sem loop", t7),
    ("T8", "evento perdido → reconciliação envia 1 vez", t8),
    ("T9", "arquivo devolvido 2x (mesmo id) → 1 recebimento", t9),
    ("T10", "reinício do n8n no meio → nada duplicado, reconciliação completa", t10),
    ("T12", "erro inesperado num fluxo → W5 abre exceção", t12),
    ("T13", "nenhum destino, link-credencial ou token de reserva retido nas execuções do n8n", t13),
]


# ===================================================================== infraestrutura


class Amostrador(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.amostras: list[int] = []
        self.fase = "repouso"
        self.por_fase: dict[str, list[int]] = {}
        self.parar = threading.Event()

    def run(self) -> None:
        while not self.parar.is_set():
            m = n8n_local.memoria_bytes()
            if m:
                self.amostras.append(m)
                self.por_fase.setdefault(self.fase, []).append(m)
            self.parar.wait(1.0)


def mib(b: float | None) -> float | None:
    return None if b is None else round(b / 1024**2, 1)


def memoria_em_repouso(espera_s: int = 45) -> dict:
    """Espera o n8n assentar (índices, poda, runner) e tira 5 amostras com 2 s de intervalo."""
    time.sleep(espera_s)
    amostras = []
    for _ in range(5):
        m = n8n_local.memoria_bytes()
        if m:
            amostras.append(m)
        time.sleep(2)
    if not amostras:
        return {"erro": "docker stats sem leitura"}
    return {
        "min": mib(min(amostras)),
        "mediana": mib(statistics.median(amostras)),
        "max": mib(max(amostras)),
        "espera_s": espera_s,
    }


def subir_simuladores(log_dir: Path) -> list[subprocess.Popen]:
    env = dict(os.environ)
    env.update(
        {
            "PCPR_SIM_TOKEN": SEGREDOS["token_api"],
            "PCPR_SIM_SEGREDO_HMAC": SEGREDOS["hmac"],
            "PCPR_SIM_URL_EVENTOS": f"{N8N}/webhook/pcpr-eventos",
            "PCPR_CANAL_CHAVE": SEGREDOS["canal_chave"],
            "PCPR_CANAL_TOKEN_WEBHOOK": SEGREDOS["canal_webhook"],
            "PCPR_CANAL_URL_INBOUND": f"{N8N}/webhook/canal-recebimento",
            "PYTHONUNBUFFERED": "1",
        }
    )
    procs = []
    for script, porta in (("simulador_pcpr.py", 8765), ("simulador_canal.py", 8766)):
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
    for url in (SIM, CANAL):
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
    ]


def rodar_t11() -> dict:
    suite = unittest.defaultTestLoader.loadTestsFromName("test_regra_vespera")
    resultado = unittest.TestResult()
    suite.run(resultado)
    falhas = [str(t) for t, _ in resultado.failures + resultado.errors]
    return {
        "id": "T11",
        "nome": "regra da véspera (unitário)",
        "passou": resultado.wasSuccessful() and resultado.testsRun > 0,
        "evidencia": {"testes": resultado.testsRun, "falhas": falhas},
    }


def exportar_workflows(tmp: Path) -> dict:
    destino = tmp / "exportado"
    destino.mkdir()
    saida = n8n_local.exportar(destino, SEGREDOS["n8n_cripto"])
    evid: dict[str, Any] = {"cli": saida.strip().splitlines()[-6:], "arquivos": {}}
    cred = (destino / "credenciais-criptografadas.json").read_text(encoding="utf-8")
    vazou = [k for k, v in SEGREDOS.items() if v in cred]
    evid["credenciais_criptografadas_no_banco"] = not vazou
    DOCS_N8N.mkdir(parents=True, exist_ok=True)
    for wid, nome in cw.ARQUIVOS.items():
        bruto = (destino / "workflows" / f"{wid}.json").read_text(encoding="utf-8")
        dados = json.loads(bruto)
        segredos_no_arquivo = [k for k, v in SEGREDOS.items() if v in bruto]
        if segredos_no_arquivo:
            raise Falha(f"{nome} contém segredo: {segredos_no_arquivo}")
        if dados.get("active") is not False:
            raise Falha(f"{nome}: active={dados.get('active')!r}")
        (DOCS_N8N / nome).write_text(
            json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        evid["arquivos"][nome] = {
            "active": dados["active"],
            "nos": len(dados["nodes"]),
            "credenciais": sorted(
                {c["id"] for n in dados["nodes"] for c in (n.get("credentials") or {}).values()}
            ),
        }
    return evid


def portas_abertas() -> list[str]:
    r = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [
        linha.strip()
        for linha in r.stdout.splitlines()
        if (re.search(r":(8765|8766|5678)\s", linha) and "LISTEN" in linha.upper())
        or re.search(r":(8765|8766|5678)\s.*ESCUTANDO", linha)
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manter", action="store_true")
    ap.add_argument("--so-subir", action="store_true")
    ap.add_argument("--sem-exportar", action="store_true")
    ap.add_argument("--apenas", default="", help="ex.: T1,T2 (depuração)")
    ap.add_argument(
        "--relatorio",
        type=Path,
        default=SAIDA / "resultados.json",
        help="onde gravar o relatório (padrão: resultados/resultados.json)",
    )
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    manter = a.manter or a.so_subir
    SAIDA.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="pcpr-prototipo-"))
    procs: list[subprocess.Popen] = []
    relatorio: dict[str, Any] = {
        "inicio": datetime.now(FUSO).isoformat(timespec="seconds"),
        "imagem": n8n_local.IMAGEM,
        "python": sys.version.split()[0],
        "cenarios": [],
        "metricas": {},
    }
    amostrador = Amostrador()
    try:
        relatorio["cenarios"].append(rodar_t11())
        procs = subir_simuladores(tmp)
        imp = tmp / "importar"
        cw.construir(imp / "workflows")
        (imp / "credenciais.json").write_text(json.dumps(credenciais()), encoding="utf-8")
        t0 = time.time()
        log_prep = n8n_local.preparar(imp, SEGREDOS["n8n_cripto"], list(cw.ARQUIVOS))
        relatorio["preparacao"] = {
            "segundos": round(time.time() - t0, 1),
            "saida_cli": log_prep.strip().splitlines()[-12:],
        }
        shutil.rmtree(imp / "workflows", ignore_errors=True)
        (imp / "credenciais.json").unlink()
        t0 = time.time()
        n8n_local.subir(SEGREDOS["n8n_cripto"])
        relatorio["primeira_subida_s"] = round(n8n_local.esperar_pronto(), 1)
        relatorio["config_efetiva"] = n8n_local.config_efetiva()
        if a.so_subir:
            print(json.dumps({"segredos_desta_execucao": SEGREDOS}, indent=2))
            return 0
        relatorio["metricas"]["memoria_repouso_antes_mib"] = memoria_em_repouso()
        amostrador.start()
        filtro = {x.strip().upper() for x in a.apenas.split(",") if x.strip()}
        for cid, nome, fn in CENARIOS:
            if filtro and cid not in filtro:
                continue
            inicio = time.time()
            amostrador.fase = cid
            item: dict[str, Any] = {"id": cid, "nome": nome}
            try:
                item["evidencia"] = fn()
                item["passou"] = True
            except Exception as exc:
                item["passou"] = False
                item["erro"] = f"{type(exc).__name__}: {exc}"
                item["traceback"] = traceback.format_exc()[-2000:]
            item["segundos"] = round(time.time() - inicio, 1)
            relatorio["cenarios"].append(item)
            print(
                f"{cid}: {'PASSOU' if item['passou'] else 'FALHOU'} "
                f"({item['segundos']}s) {item.get('erro', '')}",
                flush=True,
            )
        if not filtro or "LAT" in filtro:
            amostrador.fase = "latencia (20 sequenciais + rajada de 20)"
            try:
                relatorio["metricas"]["latencia_evento_envio"] = metricas_latencia()
            except Exception as exc:
                relatorio["metricas"]["latencia_evento_envio"] = {
                    "erro": repr(exc)[:3000],
                    "log_n8n": T_ESTADO.get("latencia_log_n8n"),
                }
        amostrador.parar.set()
        amostrador.join(5)
        relatorio["metricas"]["memoria_durante_testes_mib"] = {
            "max": mib(max(amostrador.amostras, default=0)),
            "mediana": mib(statistics.median(amostrador.amostras) if amostrador.amostras else None),
            "amostras": len(amostrador.amostras),
            "max_por_fase": {f: mib(max(v)) for f, v in amostrador.por_fase.items()},
        }
        relatorio["metricas"]["memoria_repouso_depois_mib"] = memoria_em_repouso()
        relatorio["metricas"]["banco_n8n_bytes"] = n8n_local.tamanho_banco()
        relatorio["n8n_log_final"] = n8n_local.logs(40).splitlines()[-40:]
        if a.manter:
            n8n_local.copiar_banco(tmp / "banco")
            print(f"cópia do banco em {tmp / 'banco'}")
            return 0 if all(c["passou"] for c in relatorio["cenarios"]) else 1
        n8n_local.parar()
        if not a.sem_exportar:
            try:
                relatorio["exportacao"] = exportar_workflows(tmp)
            except Exception as exc:
                relatorio["exportacao"] = {"erro": repr(exc)}
        return 0 if all(c["passou"] for c in relatorio["cenarios"]) else 1
    finally:
        amostrador.parar.set()
        if not manter:
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
                "portas_ainda_abertas": portas_abertas(),
            }
        relatorio["fim"] = datetime.now(FUSO).isoformat(timespec="seconds")
        if not a.so_subir:
            texto = json.dumps(relatorio, ensure_ascii=False, indent=2)
            vazados = [k for k, v in SEGREDOS.items() if v in texto]
            for k in vazados:  # o relatório vai para o repositório: nenhum segredo, nem sintético
                texto = texto.replace(SEGREDOS[k], f"<{k}-removido>")
            relatorio_ok = json.loads(texto)
            relatorio_ok["segredos_no_relatorio"] = vazados
            a.relatorio.parent.mkdir(parents=True, exist_ok=True)
            a.relatorio.write_text(
                json.dumps(relatorio_ok, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            for c in relatorio["cenarios"]:
                print(f"{c['id']:>4}  {'PASSOU' if c['passou'] else 'FALHOU'}  {c['nome']}")


if __name__ == "__main__":
    sys.exit(main())
