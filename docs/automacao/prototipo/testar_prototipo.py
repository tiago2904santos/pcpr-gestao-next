"""Orquestra o protótipo inteiro e faz as asserções T1–T21 + métricas.

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
import contextlib
import hashlib
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
from comum import chave_recebimento, montar_multipart  # noqa: E402
from regra_vespera import FUSO  # noqa: E402
from validar_esquema import validar  # noqa: E402

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
    # /_sim/inbound espera o W4 responder, e o W4 só responde depois do PCPR (C9): até 30 s de
    # download + 60 s de POST por entrega (tempos-limite dos nós), vezes as reentregas pedidas
    entregas = 1 + int((corpo or {}).get("reentregar", 0)) if caminho == "/_sim/inbound" else 0
    limite = 30 if not entregas else 100 * entregas
    st, b = http("POST" if corpo is not None else "GET", CANAL + caminho, corpo, timeout=limite)
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


def canal_no_ar() -> bool:
    try:
        return http("GET", CANAL + "/_sim/saude", timeout=3)[0] == 200
    except (urllib.error.URLError, OSError):
        return False


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


def validar_envelopes(envelopes: list[dict]) -> list[str]:
    """Valida contra `evento-integracao.schema.json` com o validador stdlib completo para as
    palavras-chave do esquema (allOf, if/then/else, $ref local, ...) — C2 do PR #23."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return [m for ev in envelopes for m in validar(ev, schema)]


def negativos_do_validador(base: dict) -> dict[str, list[str]]:
    """Envelopes que o esquema REJEITA têm de ser reprovados (prova de que o validador não
    ignora allOf/if/then/$ref: o T1 antigo aprovava `dados.rotulo`)."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def com(muda: Callable[[dict], None]) -> list[str]:
        ev = json.loads(json.dumps(base))
        muda(ev)
        return validar(ev, schema)

    return {
        "campo_extra_em_dados": com(lambda ev: ev["dados"].update(rotulo="véspera")),
        "tipo_comunicacao_fora_do_enum": com(lambda ev: ev["dados"].update(tipo_comunicacao="sms")),
        "dados_sem_campo_obrigatorio": com(lambda ev: ev["dados"].pop("comunicacao_id")),
        "recurso_incompativel_com_o_tipo": com(lambda ev: ev["recurso"].update(tipo="viagem")),
        "aviso_fora_do_padrao": com(lambda ev: ev["dados"].update(aviso="Viagem Já")),
        "campo_extra_na_raiz": com(lambda ev: ev.update(extra=1)),
        "data_sem_fuso": com(lambda ev: ev.update(ocorrido_em="2026-10-17T12:00:00")),
        "id_nao_uuid": com(lambda ev: ev.update(id="nao-e-uuid")),
    }


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
    envelopes = [ev["envelope"] for ev in e["eventos"]]
    erros = validar_envelopes(envelopes)
    checar(not erros, f"envelope fora do schema: {erros}")
    tipos = sorted(ev["tipo"] for ev in envelopes)
    checar(tipos == ["comunicacao.agendada", "viagem.confirmada"], f"tipos emitidos: {tipos}")
    # negativos: o validador TEM de reprovar o que o esquema rejeita (C2)
    agendada = next(ev for ev in envelopes if ev["tipo"] == "comunicacao.agendada")
    negativos = negativos_do_validador(agendada)
    aprovados_indevidamente = [k for k, erros_k in negativos.items() if not erros_k]
    checar(not aprovados_indevidamente, f"validador aprovou: {aprovados_indevidamente}")
    T_ESTADO["t1"] = {"cid": cid, "evento_id": evento(r)["id"]}
    return {
        "comunicacao_id": cid,
        "respostas_n8n": status,
        "envios_no_canal": len(envios),
        "resultados_registrados": len(resultados),
        "reservas": len(reservas),
        "estado_final": com(e, cid)["estado"],
        "provedor_mensagem_id": com(e, cid)["provedor_mensagem_id"],
        "envelopes_validados_contra_schema": {"quantos": len(envelopes), "tipos": tipos},
        "campos_de_dados_da_agendada": sorted(agendada["dados"]),
        "validador_reprovou_os_negativos": {k: v[:1] for k, v in negativos.items()},
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
    # (f) UTF-8 no corpo bruto, num campo DO CONTRATO (correlacao_id; o antigo `dados.rotulo`
    # saiu do simulador — C2): assinado sobre os bytes UTF-8 exatos → 202; assinado sobre a
    # mesma informação re-serializada com escapes é → 401 (o n8n não re-serializa).
    av = sim(
        "/_sim/eventos",
        {
            "tipo": "viagem.confirmada",
            "recurso": {"tipo": "viagem", "id": 999001, "versao": 1},
            "correlacao_id": "viagem:véspera-ação-T3",
            "dados": {"inicio_previsto": agora_sp().isoformat(timespec="seconds")},
        },
    )
    erros = validar_envelopes([av["envelope"]])
    checar(not erros, f"evento UTF-8 fora do schema: {erros}")
    st_ascii = entregar(av["id"], "assinatura_ascii")["status"]
    st_utf8 = entregar(av["id"])["status"]
    checar(st_ascii == 401, f"assinatura sobre re-serialização deveria dar 401, deu {st_ascii}")
    checar(st_utf8 == 202, f"assinatura sobre os bytes UTF-8 deveria dar 202, deu {st_utf8}")
    return {
        "respostas_invalidas": respostas,
        "envios_com_eventos_invalidos": 0,
        "controle_positivo": {"status": ok, "envios": 1},
        "f_utf8_no_corpo_bruto": {
            "campo": "correlacao_id (do contrato)",
            "envelope_valido_no_schema": True,
            "assinado_sobre_reserializacao_ascii": st_ascii,
            "assinado_sobre_bytes_utf8": st_utf8,
        },
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
    # todos os envelopes do cenário (reagendada, cancelada, agendadas) contra o esquema (C2)
    envelopes = [ev["envelope"] for ev in est()["eventos"]]
    erros = validar_envelopes(envelopes)
    checar(not erros, f"envelope fora do schema: {erros}")
    return {
        "envelopes_validados_contra_schema": sorted(ev["tipo"] for ev in envelopes),
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
    """C5: o canal RECUSA 1x (503 com corpo de recusa = prova de que nada foi aceito) e aceita na
    2ª tentativa controlada pelo W2 (sem retryOnFail nativo)."""
    resetar()
    canal("/_sim/modo", {"modo": "recusa_503_1x"})
    cid = comunicacao()["comunicacao_id"]
    esperar(lambda: com(est(), cid)["estado"] == "enviada", 30, "não ficou enviada")
    assentar()
    e, c = est(), est_canal()
    t = tentativas(c, cid)
    res = [x for x in chamadas(e, r"/comunicacoes/\d+/resultado", cid) if x["status"] == 200]
    checar(
        [x["status"] for x in t] == [503, 200], f"tentativas no canal: {[x['status'] for x in t]}"
    )
    checar(len(aceitas(c, cid)) == 1, "deveria haver 1 envio efetivo")
    checar(len(res) == 1 and res[0].get("resultado") == "enviada", f"resultados: {res}")
    checar(not excecoes_de(e, cid), f"não deveria haver exceção: {excecoes_de(e, cid)}")
    return {
        "tentativas_no_canal": [x["status"] for x in t],
        "envios_efetivos": 1,
        "resultados": [x.get("resultado") for x in res],
        "intervalo_entre_tentativas_s": round(t[1]["em"] - t[0]["em"], 2),
        "excecoes": 0,
    }


def devida(cid: int) -> bool:
    x = com(est(), cid)
    return x["estado"] == "agendada" and datetime.fromisoformat(x["enviar_em"]) <= datetime.now(
        FUSO
    )


def t7() -> dict:
    """C6: canal sempre RECUSA (503 + corpo de recusa). Cada rodada = 3 tentativas curtas no W2 →
    falha_temporaria → o PCPR reagenda com backoff; esgotadas as rodadas, o PCPR marca `falhou`
    e abre UMA exceção. Sem laço infinito: depois disso a reconciliação não acha nada."""
    resetar()
    rodadas_max = 3
    sim("/_sim/config", {"backoff_s": [2, 2], "max_rodadas": rodadas_max})
    canal("/_sim/modo", {"modo": "recusa_503"})
    cid = comunicacao()["comunicacao_id"]  # rodada 1 pelo evento
    por_rodada: list[dict] = []
    reconciliacoes: list[Any] = []
    for rodada in range(1, rodadas_max + 1):
        if rodada > 1:  # rodadas seguintes: o PCPR reagendou; a reconciliação pega quando vence
            esperar(lambda: devida(cid), 20, f"rodada {rodada}: não voltou a ficar devida")
            st, corpo = reconciliar()
            checar(st == 200 and corpo.get("devidas") == 1, f"reconciliação {st} {corpo}")
            reconciliacoes.append(corpo)
        esperar(
            lambda r=rodada: len(com(est(), cid).get("rodadas") or []) == r,
            40,
            f"rodada {rodada} sem resultado",
        )
        x = com(est(), cid)
        por_rodada.append(
            {
                "rodada": rodada,
                "resultado": x["rodadas"][-1]["resultado"],
                "estado_depois": x["estado"],
                "tentativas_no_canal_acumuladas": len(tentativas(est_canal(), cid)),
            }
        )
    assentar(3)  # passa do último backoff: nada pode estar devido
    st, corpo = reconciliar()
    checar(st == 200 and corpo.get("devidas") == 0, f"reconciliação final: {st} {corpo}")
    assentar(3)
    e, c = est(), est_canal()
    t = tentativas(c, cid)
    ex = excecoes_de(e, cid)
    x = com(e, cid)
    checar(
        [r["resultado"] for r in por_rodada] == ["falha_temporaria"] * rodadas_max,
        f"rodadas: {por_rodada}",
    )
    checar(
        [r["estado_depois"] for r in por_rodada] == ["agendada"] * (rodadas_max - 1) + ["falhou"],
        f"estados: {por_rodada}",
    )
    checar(
        len(t) == 3 * rodadas_max and all(z["status"] == 503 for z in t),
        f"esperadas {3 * rodadas_max} tentativas 503, houve {[z['status'] for z in t]}",
    )
    checar(not aceitas(c, cid), "nenhum envio deveria ter sido aceito")
    checar(x["estado"] == "falhou" and x["motivo"] == "limite_tentativas", f"comunicação: {x}")
    checar(
        len(ex) == 1 and ex[0]["motivo"] == "limite_tentativas" and ex[0]["origem"] == "pcpr",
        f"exceções: {ex}",
    )
    return {
        "rodadas": por_rodada,
        "tentativas_no_canal": len(t),
        "reconciliacoes_entre_rodadas": reconciliacoes,
        "reconciliacao_depois_de_esgotar": corpo,
        "estado": x["estado"],
        "excecao": {k: ex[0][k] for k in ("motivo", "origem", "fluxo", "detalhe")},
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
        posts[0]["chave"] == posts[1]["chave"] == f"receb:email:{mid}:0",
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


def t14() -> dict:
    """C5: resultado AMBÍGUO no canal nunca é repetido. Tempo esgotado depois de o canal aceitar,
    conexão derrubada depois de aceitar e HTTP 500 sem corpo de recusa → 1 tentativa só,
    `resultado_desconhecido` + exceção; a reconciliação não reenvia."""
    resetar()
    casos: dict[str, int] = {}
    for modo, atraso in (
        ("timeout_apos_aceitar", 15),  # > 10 s, o tempo-limite do nó Enviar ao canal
        ("desconectar_apos_aceitar", 0),
        ("sempre_500", 0),
    ):
        canal("/_sim/modo", {"modo": modo, "atraso_s": atraso})
        cid = comunicacao()["comunicacao_id"]
        esperar(
            lambda c=cid: com(est(), c)["estado"] == "falhou", 40, f"{modo}: não terminou falhou"
        )
        casos[modo] = cid
    canal("/_sim/modo", {"modo": "ok"})
    assentar(3)
    st, corpo = reconciliar()
    checar(st == 200 and corpo.get("devidas") == 0, f"reconciliação: {st} {corpo}")
    assentar(3)
    e, c = est(), est_canal()
    saida: dict[str, Any] = {"reconciliacao_depois": corpo}
    for modo, cid in casos.items():
        t = tentativas(c, cid)
        x = com(e, cid)
        ex = excecoes_de(e, cid)
        res = [z for z in chamadas(e, r"/comunicacoes/\d+/resultado", cid) if z["status"] == 200]
        checar(len(t) == 1, f"{modo}: o canal recebeu {len(t)} tentativas (reenvio às cegas)")
        aceitos_esperados = 0 if modo == "sempre_500" else 1
        checar(len(aceitas(c, cid)) == aceitos_esperados, f"{modo}: envios {len(aceitas(c, cid))}")
        checar(
            x["estado"] == "falhou" and x["resultado"] == "resultado_desconhecido",
            f"{modo}: {x['estado']}/{x['resultado']}",
        )
        checar([z.get("resultado") for z in res] == ["resultado_desconhecido"], f"{modo}: {res}")
        checar([z["motivo"] for z in ex] == ["resultado_desconhecido"], f"{modo}: {ex}")
        saida[modo] = {
            "tentativas_no_canal": len(t),
            "envios_aceitos_pelo_canal": len(aceitas(c, cid)),
            "resultado": x["resultado"],
            "excecao": ex[0]["motivo"],
            "erro_registrado": (x.get("rodadas") or [{}])[-1].get("erro"),
        }
    return saida


def t15() -> dict:
    """C6: canal FORA DO AR (porta fechada → ECONNREFUSED, prova de que nada saiu) por um tempo
    e depois volta: rodada 1 = 3 recusas → falha_temporaria → o PCPR reagenda; com o canal de
    volta, a reconciliação faz a rodada 2 → exatamente 1 envio, sem exceção."""
    resetar()
    sim("/_sim/config", {"backoff_s": [3], "max_rodadas": 3})
    canal("/_sim/fora_do_ar", {"segundos": 10})
    time.sleep(0.5)
    checar(not canal_no_ar(), "a porta do canal deveria estar fechada")
    cid = comunicacao()["comunicacao_id"]
    esperar(lambda: len(com(est(), cid).get("rodadas") or []) == 1, 30, "rodada 1 sem resultado")
    r1 = com(est(), cid)
    checar(
        r1["estado"] == "agendada" and r1["rodadas"][0]["resultado"] == "falha_temporaria",
        f"rodada 1: {r1['estado']} {r1['rodadas']}",
    )
    recusas = r1["rodadas"][0]["erro"].count("conexão recusada")
    checar(recusas == 3, f"esperadas 3 recusas de conexão na rodada 1: {r1['rodadas'][0]}")
    esperar(canal_no_ar, 30, "canal não voltou")
    esperar(lambda: devida(cid), 20, "não voltou a ficar devida (backoff)")
    st, corpo = reconciliar()
    checar(st == 200 and corpo.get("devidas") == 1, f"reconciliação: {st} {corpo}")
    esperar(lambda: com(est(), cid)["estado"] == "enviada", 30, "não ficou enviada")
    st2, corpo2 = reconciliar()
    checar(st2 == 200 and corpo2.get("devidas") == 0, f"2ª reconciliação: {st2} {corpo2}")
    assentar(3)
    e, c = est(), est_canal()
    x = com(e, cid)
    checar(len(tentativas(c, cid)) == 1 and len(aceitas(c, cid)) == 1, "esperado 1 envio")
    checar(
        [z["resultado"] for z in x["rodadas"]] == ["falha_temporaria", "enviada"],
        f"rodadas: {x['rodadas']}",
    )
    checar(not excecoes_de(e, cid), f"não deveria haver exceção: {excecoes_de(e, cid)}")
    return {
        "canal_fora_do_ar_s": 10,
        "rodada_1": {"resultado": "falha_temporaria", "conexoes_recusadas": recusas},
        "estado_entre_rodadas": "agendada (backoff 3 s no PCPR)",
        "reconciliacao": corpo,
        "rodada_2": "enviada",
        "envios_efetivos": 1,
        "excecoes": 0,
        "reconciliacao_final": corpo2,
    }


def _post_recebimento_direto(campos: dict[str, str], chave: str) -> tuple[int, Any]:
    pdf = b"%PDF-1.4\n% PCPR T16 contrato\n%%EOF\n"
    campos = {**campos, "sha256": hashlib.sha256(pdf).hexdigest()}
    corpo, tipo = montar_multipart(campos, {"arquivo": ("t16.pdf", "application/pdf", pdf)})
    req = urllib.request.Request(
        f"{SIM}/api/automacao/v1/recebimentos",
        data=corpo,
        headers={
            "Content-Type": tipo,
            "Authorization": f"Bearer {SEGREDOS['token_api']}",
            "Idempotency-Key": chave,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


PRAZO_1A_ENTREGA_MS = 20_000  # W4 com 2 anexos (medido: < 1 s); o canal desiste em 90 s


def t16() -> dict:
    """C3: mensagem com 2 anexos → 2 recebimentos distintos com a chave do contrato
    `receb:<canal>:<mensagem_id_canal>:<anexo_indice>` e anexo_indice/total_anexos no multipart;
    a mesma mensagem reenviada → 0 recebimentos novos. O simulador exige os campos (422)."""
    resetar()
    mid = f"msg.sim.T16.{secrets.token_hex(4)}"
    entrada = {
        "mensagem_id": mid,
        "remetente": "+5500000000161",
        "canal": "email",
        "anexos": [
            {"texto": "T16 anexo A sintetico", "nome": "termo-a.pdf"},
            {"texto": "T16 anexo B sintetico", "nome": "termo-b.pdf"},
        ],
    }
    # Como um canal real, o simulador reentrega enquanto o W4 não der 2xx (o W4 só dá 2xx depois
    # do PCPR). Na rodada completa de 18/10 00:28 o 1º webhook deste cenário passou de 30 s sem
    # resposta (causa não confirmada; não se repetiu). A reentrega fica ligada para o relatório
    # mostrar o que aconteceu, mas a 1ª entrega TEM de dar 2xx dentro do prazo: um W4 que trave na
    # 1ª entrega não pode passar despercebido (2ª verificação do C3).
    r1 = canal("/_sim/inbound", {**entrada, "reentregar": 2})
    checar(r1["status"] == 200, f"webhook W4 respondeu {r1['entregas']} {r1.get('resposta')}")
    checar(
        r1["entregas"][0] == 200 and r1["ms_entregas"][0] <= PRAZO_1A_ENTREGA_MS,
        f"1ª entrega (2 anexos) fora do prazo de {PRAZO_1A_ENTREGA_MS} ms: "
        f"{r1['entregas']} {r1['ms_entregas']}",
    )
    e = est()
    posts = chamadas(e, r"/recebimentos")
    recs = [x for x in e["recebimentos"] if x["estado"] != "duplicado"]
    chaves_esperadas = [f"receb:email:{mid}:0", f"receb:email:{mid}:1"]
    chaves = sorted({p["chave"] for p in posts})
    checar(chaves == chaves_esperadas, f"chaves: {chaves}")
    for k in chaves_esperadas:  # por anexo: exatamente 1 efeito; o resto é repetição
        efeitos = [
            p for p in posts if p["chave"] == k and p["status"] == 202 and not p.get("replay")
        ]
        checar(len(efeitos) == 1, f"{k}: {len(efeitos)} POST com efeito ({posts})")
    checar(len(recs) == 2 and recs[0]["id"] != recs[1]["id"], f"recebimentos: {recs}")
    checar(len(e["recebimentos"]) == 2, f"registros: {len(e['recebimentos'])}")
    por_indice = {x["campos"]["anexo_indice"]: x for x in recs}
    checar(sorted(por_indice) == ["0", "1"], f"anexo_indice: {sorted(por_indice)}")
    checar(all(x["campos"]["total_anexos"] == "2" for x in recs), "total_anexos ≠ 2")
    checar(
        [por_indice[str(i)]["sha256"] for i in range(2)] == [a["sha256"] for a in r1["arquivos"]],
        "SHA-256 dos recebimentos ≠ dos anexos",
    )
    # (b) a MESMA mensagem de novo (reentrega do canal): só repetições idempotentes, 0 novos
    r2 = canal("/_sim/inbound", {**entrada, "reentregar": 2})
    checar(r2["status"] == 200, f"reenvio: {r2['entregas']}")
    e2 = est()
    novos_posts = chamadas(e2, r"/recebimentos")[len(posts) :]
    aceitos_b = [p for p in novos_posts if p["status"] == 202]
    checar(
        {p["chave"] for p in aceitos_b} == set(chaves_esperadas)
        and all(p.get("replay") for p in aceitos_b),
        f"reenvio: {novos_posts}",
    )
    checar(len(e2["recebimentos"]) == 2, f"reenvio criou recebimento: {len(e2['recebimentos'])}")
    # (c) o simulador do PCPR exige o contrato (direto na API, sem o n8n)
    base = {
        "canal": "email",
        "mensagem_id_canal": f"{mid}.direto",
        "remetente": "+5500000000162",
        "recebido_em": "2026-10-17T12:00:00Z",
    }
    sem_indice = _post_recebimento_direto(base, f"receb:email:{mid}.direto:0")
    chave_antiga = _post_recebimento_direto(
        {**base, "anexo_indice": "0", "total_anexos": "1"}, f"recebimento:email:{mid}.direto"
    )
    indice_fora = _post_recebimento_direto(
        {**base, "anexo_indice": "1", "total_anexos": "1"}, f"receb:email:{mid}.direto:1"
    )
    for nome, (st, corpo) in (
        ("sem anexo_indice/total_anexos", sem_indice),
        ("chave antiga recebimento:<canal>:<id>", chave_antiga),
        ("anexo_indice >= total_anexos", indice_fora),
    ):
        checar(st == 422 and corpo.get("codigo") == "entrada_invalida", f"{nome}: {st} {corpo}")
    # (d) mensagem sem anexo → /recebimentos/sem-arquivo (motivo sem_anexo, contrato): o PCPR
    # registra e orienta o remetente; o W4 confirma ao canal (antes: 422 sem chamar o PCPR, e o
    # canal reentregava até desistir — 2ª verificação do C9)
    mid_v = f"{mid}.vazia"
    r3 = canal("/_sim/inbound", {**entrada, "mensagem_id": mid_v, "anexos": [], "reentregar": 2})
    e3 = est()
    sem = [
        p
        for p in chamadas(e3, r"/recebimentos/sem-arquivo")
        if p["chave"] == f"receb:email:{mid_v}:0"
    ]
    rec_v = [x for x in e3["recebimentos"] if x["campos"].get("mensagem_id_canal") == mid_v]
    checar(r3["entregas"] == [200], f"sem anexo: entregas {r3['entregas']} {r3.get('resposta')}")
    checar([p["status"] for p in sem] == [202], f"sem anexo: sem-arquivo {sem}")
    checar(
        len(rec_v) == 1 and rec_v[0]["estado"] == "rejeitado" and rec_v[0]["motivo"] == "sem_anexo",
        f"sem anexo: recebimento {rec_v}",
    )
    checar(
        not [p for p in chamadas(e3, r"/recebimentos") if mid_v in str(p["chave"])],
        "sem anexo chamou POST /recebimentos",
    )
    return {
        "a_dois_anexos": {
            "entregas_do_canal": r1["entregas"],
            "ms_da_1a_entrega": r1["ms_entregas"][0],
            "prazo_ms": PRAZO_1A_ENTREGA_MS,
            "chaves": chaves,
            "recebimentos": [
                {"id": x["id"], "anexo_indice": i, "total_anexos": 2}
                for i, x in sorted(por_indice.items())
            ],
        },
        "b_reenvio_da_mesma_mensagem": {
            "entregas_do_canal": r2["entregas"],
            "posts": [p["status"] for p in novos_posts],
            "repeticoes_idempotentes": len(aceitos_b),
            "recebimentos_novos": 0,
        },
        "c_contrato_no_simulador": {
            "sem_anexo_indice": sem_indice[0],
            "chave_antiga": chave_antiga[0],
            "indice_fora_do_total": indice_fora[0],
        },
        "d_mensagem_sem_anexo": {
            "entregas_do_canal": r3["entregas"],
            "sem_arquivo": [p["status"] for p in sem],
            "recebimento": {"estado": rec_v[0]["estado"], "motivo": rec_v[0]["motivo"]},
        },
    }


def t17() -> dict:
    """C9: o W4 só responde 2xx ao canal DEPOIS de o PCPR aceitar. Falha no POST /recebimentos
    ou no download → não-2xx → o canal reentrega a mensagem → 1 recebimento."""
    resetar()
    # (a) POST /recebimentos falha 1x (503 do PCPR, não guardado pela idempotência)
    sim("/_sim/config", {"falhar_recebimentos": 1})
    mid = f"msg.sim.T17a.{secrets.token_hex(4)}"
    ra = canal(
        "/_sim/inbound",
        {"mensagem_id": mid, "remetente": "+5500000000171", "canal": "email", "reentregar": 3},
    )
    e = est()
    posts = chamadas(e, r"/recebimentos")
    recs = [x for x in e["recebimentos"] if x["estado"] != "duplicado"]
    checar(ra["entregas"] == [503, 200], f"(a) entregas do canal: {ra['entregas']}")
    checar([p["status"] for p in posts] == [503, 202], f"(a) POST /recebimentos: {posts}")
    checar(not posts[1].get("replay"), "(a) a 2ª chamada não pode ser repetição de um 503")
    checar(len(recs) == 1 and recs[0]["sha256"] == ra["arquivo"]["sha256"], f"(a) {recs}")
    # (b) o download do anexo no canal falha 1x
    canal("/_sim/modo", {"falhar_downloads": 1})
    mid_b = f"msg.sim.T17b.{secrets.token_hex(4)}"
    rb = canal(
        "/_sim/inbound",
        {"mensagem_id": mid_b, "remetente": "+5500000000172", "canal": "email", "reentregar": 3},
    )
    e, c = est(), est_canal()
    downs = [d["status"] for d in c["downloads"] if d["arquivo"] == rb["arquivo"]["id"]]
    posts_b = [
        p for p in chamadas(e, r"/recebimentos") if p["chave"].startswith(f"receb:email:{mid_b}")
    ]
    recs_b = [
        x
        for x in e["recebimentos"]
        if x["estado"] != "duplicado" and x["campos"]["mensagem_id_canal"] == mid_b
    ]
    checar(rb["entregas"] == [503, 200], f"(b) entregas do canal: {rb['entregas']}")
    checar(downs == [500, 200], f"(b) downloads: {downs}")
    checar([p["status"] for p in posts_b] == [202], f"(b) o PCPR só deveria ver 1 POST: {posts_b}")
    checar(len(recs_b) == 1, f"(b) recebimentos: {recs_b}")
    return {
        "a_post_recebimentos_falha_1x": {
            "respostas_do_w4_ao_canal": ra["entregas"],
            "post_recebimentos": [p["status"] for p in posts],
            "recebimentos": 1,
        },
        "b_download_falha_1x": {
            "respostas_do_w4_ao_canal": rb["entregas"],
            "downloads": downs,
            "post_recebimentos": [p["status"] for p in posts_b],
            "recebimentos": 1,
        },
    }


def t18() -> dict:
    """C11: deduplicação de recebimento por (servidor remetente resolvido, SHA-256). O mesmo
    arquivo de 2 servidores → 2 recebimentos; o mesmo servidor 2x (inclusive por outro contato
    dele) → 1."""
    resetar()
    a, b, a2 = "+5500000000181", "+5500000000182", "+5500000000183"
    for remetente, sid in ((a, 9001), (b, 9002), (a2, 9001)):  # a2 = 2º contato do servidor 9001
        sim("/_sim/remetentes", {"canal": "email", "remetente": remetente, "servidor_id": sid})
    mesmo = [{"texto": "T18 formulario sintetico identico", "nome": "formulario.pdf"}]
    envios = (("a1", a), ("b1", b), ("a2", a), ("a3_outro_contato", a2))
    ids: dict[str, str] = {}
    for rotulo, remetente in envios:
        mid = f"msg.sim.T18.{rotulo}.{secrets.token_hex(3)}"
        r = canal(
            "/_sim/inbound",
            {"mensagem_id": mid, "remetente": remetente, "canal": "email", "anexos": mesmo},
        )
        checar(r["status"] == 200, f"{rotulo}: webhook {r['status']}")
        ids[rotulo] = mid
    e = est()
    por = {
        rotulo: next(x for x in e["recebimentos"] if x["campos"]["mensagem_id_canal"] == mid)
        for rotulo, mid in ids.items()
    }
    shas = {x["sha256"] for x in por.values()}
    checar(len(shas) == 1, f"o arquivo deveria ser o mesmo nos 4 envios: {shas}")
    estados = {k: x["estado"] for k, x in por.items()}
    checar(
        estados["a1"] == "aceito_para_processamento"
        and estados["b1"] == "aceito_para_processamento",
        f"servidores diferentes → 2 recebimentos: {estados}",
    )
    checar(
        estados["a2"] == "duplicado" and por["a2"]["duplicado_de"] == por["a1"]["id"],
        f"mesmo servidor 2x → duplicado: {estados}",
    )
    checar(
        estados["a3_outro_contato"] == "duplicado"
        and por["a3_outro_contato"]["duplicado_de"] == por["a1"]["id"],
        f"outro contato do mesmo servidor → duplicado: {estados}",
    )
    nao_dup = [x for x in e["recebimentos"] if x["estado"] != "duplicado"]
    checar(len(nao_dup) == 2, f"esperados 2 recebimentos, houve {len(nao_dup)}")
    return {
        "mesmo_sha256": True,
        "por_envio": {
            k: {"servidor": x["servidor"], "estado": x["estado"]} for k, x in por.items()
        },
        "recebimentos": 2,
        "duplicados": 2,
    }


def t19() -> dict:
    """2ª verificação do C9 (arquitetura §3.7 e §3.12): recusa PERMANENTE do PCPR e anexo sem bytes
    não viram laço de reentrega nem perda silenciosa. Cada caso: o canal recebe resposta final
    (2xx) já na 1ª entrega, mesmo pedindo até 3 reentregas, e sobra um registro humano no PCPR
    (exceção ou recebimento `rejeitado` com orientação ao remetente)."""
    remetente = "+5500000000191"

    def receber(mid: str, anexos: list[dict] | None = None, **mais: Any) -> dict:
        corpo: dict[str, Any] = {
            "mensagem_id": mid,
            "remetente": remetente,
            "canal": "email",
            "reentregar": 3,
            **mais,
        }
        if anexos is not None:
            corpo["anexos"] = anexos
        return canal("/_sim/inbound", corpo)

    def da_msg(e: dict, mid: str) -> dict[str, Any]:
        chave = chave_recebimento("email", mid, 0)
        return {
            "posts": [p["status"] for p in chamadas(e, r"/recebimentos") if p["chave"] == chave],
            "sem_arquivo": [
                p["status"]
                for p in chamadas(e, r"/recebimentos/sem-arquivo")
                if p["chave"] == chave
            ],
            "excecoes_n8n": [
                p for p in chamadas(e, r"/excecoes") if f"{chave}:" in str(p["chave"])
            ],
            "excecoes": [x for x in e["excecoes"] if mid in str(x.get("correlacao_id"))],
            "recebimentos": [
                x for x in e["recebimentos"] if x["campos"].get("mensagem_id_canal") == mid
            ],
            "w5": [x for x in e["excecoes"] if str(x["fluxo"]).startswith("n8n:")],
        }

    saida: dict[str, Any] = {}
    # (a) 422 permanente no POST /recebimentos → exceção do n8n + 200; reentrega → a MESMA exceção
    resetar()
    sim("/_sim/config", {"recusar_recebimentos": 99})
    mid = f"msg.sim.T19a.{secrets.token_hex(3)}"
    r = receber(mid)
    x = da_msg(est(), mid)
    checar(r["entregas"] == [200], f"(a) entregas {r['entregas']} {r.get('resposta')}")
    checar(x["posts"] == [422], f"(a) POST /recebimentos {x['posts']}")
    checar(
        len(x["excecoes"]) == 1
        and x["excecoes"][0]["origem"] == "n8n"
        and x["excecoes"][0]["fluxo"] == "recebimento-canais"
        and x["excecoes"][0]["motivo"] == "outro",
        f"(a) exceções {x['excecoes']}",
    )
    checar(not x["recebimentos"] and not x["w5"], f"(a) recebimentos/W5: {x}")
    r2 = receber(mid)  # o canal entrega a mesma mensagem outra vez (ex.: caixa relida)
    x2 = da_msg(est(), mid)
    checar(r2["entregas"] == [200], f"(a2) entregas {r2['entregas']}")
    checar(len(x2["excecoes"]) == 1, f"(a2) exceção duplicada: {x2['excecoes']}")
    checar(
        [(p["status"], bool(p.get("replay"))) for p in x2["excecoes_n8n"]]
        == [(201, False), (201, True)],
        f"(a2) POST /excecoes {x2['excecoes_n8n']}",
    )
    saida["a_422_permanente"] = {
        "entregas_do_canal": r["entregas"],
        "post_recebimentos": x["posts"],
        "excecao": {k: x["excecoes"][0][k] for k in ("origem", "fluxo", "motivo", "detalhe")},
        "mesma_mensagem_de_novo": {
            "entregas_do_canal": r2["entregas"],
            "post_excecoes": ["201", "201 (repetição)"],
            "excecoes": 1,
        },
    }
    # (b) canal de entrada bloqueado → 409 canal_bloqueado → exceção canal_indisponivel + 200
    resetar()
    sim("/_sim/canais", {"email_entrada": "bloqueado"})
    mid = f"msg.sim.T19b.{secrets.token_hex(3)}"
    r = receber(mid)
    x = da_msg(est(), mid)
    checar(r["entregas"] == [200], f"(b) entregas {r['entregas']}")
    checar(x["posts"] == [409], f"(b) POST /recebimentos {x['posts']}")
    checar([e["motivo"] for e in x["excecoes"]] == ["canal_indisponivel"], f"(b) {x['excecoes']}")
    saida["b_409_canal_bloqueado"] = {
        "entregas_do_canal": r["entregas"],
        "post_recebimentos": x["posts"],
        "excecao": "canal_indisponivel",
    }
    # (c) 413 do PCPR → /recebimentos/sem-arquivo (acima_do_limite), sem exceção do n8n
    resetar()
    sim("/_sim/config", {"limite_recebimento_bytes": 256})
    mid = f"msg.sim.T19c.{secrets.token_hex(3)}"
    r = receber(mid)
    x = da_msg(est(), mid)
    checar(r["entregas"] == [200], f"(c) entregas {r['entregas']}")
    checar(
        x["posts"] == [413] and x["sem_arquivo"] == [202], f"(c) {x['posts']} {x['sem_arquivo']}"
    )
    checar(
        [(y["estado"], y["motivo"]) for y in x["recebimentos"]]
        == [("rejeitado", "acima_do_limite")],
        f"(c) recebimentos {x['recebimentos']}",
    )
    checar(not x["excecoes"], f"(c) exceções {x['excecoes']}")
    saida["c_413_do_pcpr"] = {
        "entregas_do_canal": r["entregas"],
        "post_recebimentos": x["posts"],
        "sem_arquivo": x["sem_arquivo"],
        "recebimento": "rejeitado (acima_do_limite)",
    }
    # (d) anexo anunciado acima de 25 MiB → nem é baixado; sem-arquivo acima_do_limite
    resetar()
    mid = f"msg.sim.T19d.{secrets.token_hex(3)}"
    r = receber(mid, [{"texto": "T19 d grande", "tamanho_declarado": 30 * 1024 * 1024}])
    e, c = est(), est_canal()
    x = da_msg(e, mid)
    downs = [d["status"] for d in c["downloads"] if d["arquivo"] == r["arquivo"]["id"]]
    checar(r["entregas"] == [200], f"(d) entregas {r['entregas']}")
    checar(not downs and not x["posts"] and x["sem_arquivo"] == [202], f"(d) {downs} {x}")
    checar(
        [(y["estado"], y["motivo"]) for y in x["recebimentos"]]
        == [("rejeitado", "acima_do_limite")],
        f"(d) recebimentos {x['recebimentos']}",
    )
    saida["d_anexo_anunciado_acima_do_limite"] = {
        "entregas_do_canal": r["entregas"],
        "downloads": 0,
        "sem_arquivo": x["sem_arquivo"],
    }
    # (e) anexo que não existe mais no canal (404) → sem-arquivo nao_baixado → exceção do PCPR
    resetar()
    mid = f"msg.sim.T19e.{secrets.token_hex(3)}"
    r = receber(mid, [{"texto": "T19 e removido", "removido": True}])
    e, c = est(), est_canal()
    x = da_msg(e, mid)
    downs = [d["status"] for d in c["downloads"] if d["arquivo"] == r["arquivo"]["id"]]
    checar(r["entregas"] == [200], f"(e) entregas {r['entregas']}")
    checar(downs == [404] and not x["posts"] and x["sem_arquivo"] == [202], f"(e) {downs} {x}")
    checar(
        [(y["origem"], y["motivo"]) for y in x["excecoes"]] == [("pcpr", "arquivo_nao_baixado")],
        f"(e) exceções {x['excecoes']}",
    )
    saida["e_anexo_inexistente_404"] = {
        "entregas_do_canal": r["entregas"],
        "downloads": downs,
        "sem_arquivo": x["sem_arquivo"],
        "excecao": "arquivo_nao_baixado (aberta pelo PCPR)",
    }
    # (e2) download com 4xx estável que não é 404/410 (422: id malformado) → também definitivo:
    # sem-arquivo nao_baixado + exceção do PCPR + 200 já na 1ª entrega; (e3) 429 continua
    # transitório → 503 e o canal reentrega, sem registro sem arquivo
    resetar()
    mid = f"msg.sim.T19e2.{secrets.token_hex(3)}"
    r = receber(mid, [{"texto": "T19 e2 malformado", "status_download": 422}])
    x = da_msg(est(), mid)
    checar(r["entregas"] == [200], f"(e2) entregas {r['entregas']}")
    checar(not x["posts"] and x["sem_arquivo"] == [202], f"(e2) {x}")
    checar(
        [(y["origem"], y["motivo"]) for y in x["excecoes"]] == [("pcpr", "arquivo_nao_baixado")],
        f"(e2) exceções {x['excecoes']}",
    )
    resetar()
    mid = f"msg.sim.T19e3.{secrets.token_hex(3)}"
    r3 = receber(mid, [{"texto": "T19 e3 limite", "status_download": 429}], reentregar=1)
    x3 = da_msg(est(), mid)
    checar(r3["entregas"] == [503, 503], f"(e3) entregas {r3['entregas']}")
    checar(not x3["sem_arquivo"] and not x3["excecoes"], f"(e3) {x3}")
    saida["e2_e3_download_4xx"] = {
        "422_definitivo": {
            "entregas_do_canal": r["entregas"],
            "sem_arquivo": x["sem_arquivo"],
            "excecao": "arquivo_nao_baixado (aberta pelo PCPR)",
        },
        "429_transitorio": {"entregas_do_canal": r3["entregas"], "sem_arquivo": 0},
    }
    # (f) a recusa permanente MUDA entre entregas (422 na 1ª, 409 canal_bloqueado na 2ª): cada
    # classe de recusa tem a sua chave (corpo = função da chave) → 2 exceções, nenhuma 422 de
    # "chave reutilizada", resposta final ao canal nas duas; a 3ª entrega repete a 2ª sem efeito
    resetar()
    sim("/_sim/config", {"recusar_recebimentos": 1})
    mid = f"msg.sim.T19f.{secrets.token_hex(3)}"
    r1 = receber(mid)
    sim("/_sim/canais", {"email_entrada": "bloqueado"})
    r2 = receber(mid)
    r3 = receber(mid)
    x = da_msg(est(), mid)
    entregas_f = [r1["entregas"], r2["entregas"], r3["entregas"]]
    checar(entregas_f == [[200], [200], [200]], f"(f) entregas {entregas_f}")
    checar(x["posts"] == [422, 409, 409], f"(f) POST /recebimentos {x['posts']}")
    excs_f = [(p["status"], bool(p.get("replay"))) for p in x["excecoes_n8n"]]
    checar(excs_f == [(201, False), (201, False), (201, True)], f"(f) POST /excecoes {excs_f}")
    checar(
        sorted(y["motivo"] for y in x["excecoes"]) == ["canal_indisponivel", "outro"],
        f"(f) exceções {x['excecoes']}",
    )
    saida["f_recusa_que_muda_entre_entregas"] = {
        "entregas_do_canal": entregas_f,
        "post_recebimentos": x["posts"],
        "post_excecoes": [f"{st}{' (repetição)' if rep else ''}" for st, rep in excs_f],
        "excecoes": sorted(y["motivo"] for y in x["excecoes"]),
    }
    # (g) falha TEMPORÁRIA persistente (§3.7): entrada de e-mail desligada (423). Mensagem recente
    # → só 503 (o canal reentrega), sem exceção. Mensagem recebida há 2 dias (> 4 h) → continua
    # 503 (nada se perde) e abre UMA exceção fila_parada, repetida sem efeito a cada reentrega;
    # religada a entrada, a reentrega seguinte registra 1 recebimento.
    resetar()
    sim("/_sim/canais", {"email_entrada": "desligado"})
    mid_rec = f"msg.sim.T19g.recente.{secrets.token_hex(3)}"
    rr = receber(mid_rec, reentregar=1)
    xr = da_msg(est(), mid_rec)
    checar(rr["entregas"] == [503, 503], f"(g) recente: entregas {rr['entregas']}")
    checar(not xr["excecoes"] and not xr["excecoes_n8n"], f"(g) recente: exceções {xr}")
    mid = f"msg.sim.T19g.velha.{secrets.token_hex(3)}"
    rv = receber(mid, recebido_ha_s=2 * 86400, reentregar=2)
    e = est()
    xv = da_msg(e, mid)
    chave_fila = f"excecao:recebimento-canais:receb:email:{mid}:fila_parada"  # cabe em 200
    posts_fila = [
        (p["status"], bool(p.get("replay")))
        for p in chamadas(e, r"/excecoes")
        if p["chave"] == chave_fila
    ]
    checar(rv["entregas"] == [503, 503, 503], f"(g) velha: entregas {rv['entregas']}")
    checar(xv["posts"] == [423, 423, 423], f"(g) velha: POST /recebimentos {xv['posts']}")
    checar(
        posts_fila == [(201, False), (201, True), (201, True)], f"(g) POST /excecoes {posts_fila}"
    )
    checar(
        [(y["origem"], y["motivo"]) for y in xv["excecoes"]] == [("n8n", "fila_parada")],
        f"(g) exceções {xv['excecoes']}",
    )
    sim("/_sim/canais", {"email_entrada": "ligado"})
    rl = receber(mid, reentregar=0)
    xl = da_msg(est(), mid)
    checar(rl["entregas"] == [200], f"(g) religada: entregas {rl['entregas']}")
    checar(
        [y["estado"] for y in xl["recebimentos"]] == ["aceito_para_processamento"],
        f"(g) religada: recebimentos {xl['recebimentos']}",
    )
    checar(len(xl["excecoes"]) == 1, f"(g) religada: exceções {xl['excecoes']}")
    saida["g_falha_temporaria_persistente"] = {
        "mensagem_recente": {"entregas_do_canal": rr["entregas"], "excecoes": 0},
        "mensagem_de_2_dias": {
            "entregas_do_canal": rv["entregas"],
            "post_recebimentos": xv["posts"],
            "post_excecoes_fila_parada": [
                f"{st}{' (repetição)' if rep else ''}" for st, rep in posts_fila
            ],
            "excecoes": ["fila_parada"],
        },
        "entrada_religada": {"entregas_do_canal": rl["entregas"], "recebimentos": 1},
    }
    # (h) id de mensagem do canal LONGO (150 caracteres; o contrato aceita até 300): a chave do
    # recebimento ainda cabe em 200, a da exceção não caberia → o cabeçalho usa sha256 do resto.
    # Sem isso o /excecoes dava 400 e o W4 respondia 503 para sempre (Codex 4306152913).
    resetar()
    sim("/_sim/config", {"recusar_recebimentos": 99})
    mid = "msg.sim.T19h." + secrets.token_hex(3) + "x" * 131
    checar(len(mid) == 150, f"(h) tamanho do id {len(mid)}")
    rh = [receber(mid)["entregas"], receber(mid)["entregas"]]  # a 2ª: o canal entrega de novo
    e = est()
    xh = da_msg(e, mid)
    posts_h = [
        (p["status"], bool(p.get("replay")), len(str(p["chave"])))
        for p in chamadas(e, r"/excecoes")
        if str(p["chave"]).startswith("excecao#sha256:recebimento-canais:")
    ]
    checar(rh == [[200], [200]], f"(h) entregas {rh}")
    checar(xh["posts"] == [422, 422], f"(h) POST /recebimentos {xh['posts']}")
    checar(
        [(st, rep) for st, rep, _ in posts_h] == [(201, False), (201, True)]
        and all(n <= 200 for _, _, n in posts_h),
        f"(h) POST /excecoes {posts_h}",
    )
    checar(len(xh["excecoes"]) == 1, f"(h) exceções {xh['excecoes']}")
    saida["h_id_do_canal_longo"] = {
        "tamanho_do_id": len(mid),
        "entregas_do_canal": rh,
        "tamanho_da_chave_da_excecao": posts_h[0][2],
        "post_excecoes": ["201", "201 (repetição)"],
        "excecoes": 1,
    }
    # (i) id do canal com 290 caracteres (o contrato aceita até 300): a chave do recebimento
    # passaria de 200 → receb#sha256:<canal>:<hex>:<anexo>, a mesma regra no PCPR. O 413 ainda
    # vira recebimento rejeitado com orientação (antes: 400 na chave → exceção genérica).
    resetar()
    sim("/_sim/config", {"limite_recebimento_bytes": 256})
    mid = "msg.sim.T19i." + secrets.token_hex(3) + "y" * 271
    checar(len(mid) == 290, f"(i) tamanho do id {len(mid)}")
    ri = receber(mid)
    xi = da_msg(est(), mid)
    chave_i = chave_recebimento("email", mid, 0)
    checar(ri["entregas"] == [200], f"(i) entregas {ri['entregas']}")
    checar(len(chave_i) <= 200 and chave_i.startswith("receb#sha256:email:"), f"(i) {chave_i}")
    # um id curto que imite a forma com hash não colide com ela (o "#" fica no 1º segmento)
    imitacao = "sha256:" + hashlib.sha256(mid.encode()).hexdigest()
    checar(chave_recebimento("email", imitacao, 0) != chave_i, "(i) colisão com id imitado")
    checar(xi["posts"] == [413] and xi["sem_arquivo"] == [202], f"(i) {xi['posts']} {xi}")
    checar(
        [(y["estado"], y["motivo"]) for y in xi["recebimentos"]]
        == [("rejeitado", "acima_do_limite")],
        f"(i) recebimentos {xi['recebimentos']}",
    )
    # (j) falha temporária persistente com id de 160 caracteres: a exceção fila_parada abre
    # (a chave dela passaria de 200 → sha256), e a mensagem segue em 503
    resetar()
    sim("/_sim/canais", {"email_entrada": "desligado"})
    mid = "msg.sim.T19j." + secrets.token_hex(3) + "z" * 141
    rj = receber(mid, recebido_ha_s=2 * 86400, reentregar=1)
    e = est()
    posts_j = [
        (p["status"], bool(p.get("replay")), len(str(p["chave"])))
        for p in chamadas(e, r"/excecoes")
        if str(p["chave"]).startswith("excecao#sha256:recebimento-canais:")
    ]
    checar(rj["entregas"] == [503, 503], f"(j) entregas {rj['entregas']}")
    checar(
        [(st, rep) for st, rep, _ in posts_j] == [(201, False), (201, True)]
        and all(n <= 200 for _, _, n in posts_j),
        f"(j) POST /excecoes {posts_j}",
    )
    checar(
        [y["motivo"] for y in e["excecoes"] if mid[-12:] in str(y.get("correlacao_id"))]
        == ["fila_parada"],
        f"(j) exceções {e['excecoes']}",
    )
    # (k) id com caractere fora do BMP (emoji): JS conta 2, Python conta 1 — por isso a chave
    # bruta só vale em ASCII; aqui sai a com hash nos dois lados e o recebimento entra (202)
    resetar()
    mid = f"msg.sim.T19k.{secrets.token_hex(3)}.😀"
    rk = receber(mid)
    xk = da_msg(est(), mid)
    checar(chave_recebimento("email", mid, 0).startswith("receb#sha256:"), "(k) chave bruta")
    checar(rk["entregas"] == [200] and xk["posts"] == [202], f"(k) {rk['entregas']} {xk}")
    checar(len(xk["recebimentos"]) == 1, f"(k) recebimentos {xk['recebimentos']}")
    # (l) id de 1 caractere: receb:email:x:0 teria 15 (< 16 do contrato) → forma com hash; entra
    resetar()
    mid = "x"
    rl = receber(mid)
    xl = da_msg(est(), mid)
    checar(chave_recebimento("email", mid, 0).startswith("receb#sha256:"), "(l) chave curta crua")
    checar(rl["entregas"] == [200] and xl["posts"] == [202], f"(l) {rl['entregas']} {xl}")
    saida["i_j_ids_muito_longos"] = {
        "i_id_290_sem_arquivo": {
            "chave_do_recebimento": len(chave_i),
            "post_recebimentos": xi["posts"],
            "sem_arquivo": xi["sem_arquivo"],
            "recebimento": "rejeitado (acima_do_limite)",
        },
        "j_id_160_fila_parada": {
            "entregas_do_canal": rj["entregas"],
            "post_excecoes": ["201", "201 (repetição)"],
            "tamanho_da_chave": posts_j[0][2],
        },
    }
    return saida


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


def t21() -> dict:
    """Revisão do Codex (PR #23): mensagem com anexos mistos — o anexo 0 leva 413 e é registrado
    sem arquivo; o anexo 1 falha de forma transitória (503) e o W4 pede reentrega. Na reentrega o
    W4 repete o upload do anexo 0 com a mesma chave: o PCPR devolve o Recebimento `rejeitado` já
    gravado (202, repetição), e não 422 "chave reutilizada" (que virava falsa exceção de recusa
    permanente). Fim: 1 rejeitado + 1 aceito, 0 exceção, 1 só sem-arquivo."""
    resetar()
    # o anexo 0 passa do limite do PCPR (corpo multipart > 4 KiB), o anexo 1 não; o 413 vem antes
    # da falha injetada, então o 503 único cai no anexo 1
    sim("/_sim/config", {"limite_recebimento_bytes": 4096, "falhar_recebimentos": 1})
    mid = f"msg.sim.T21.{secrets.token_hex(4)}"
    r = canal(
        "/_sim/inbound",
        {
            "mensagem_id": mid,
            "remetente": "+5500000000211",
            "canal": "email",
            "reentregar": 3,
            "anexos": [
                {"texto": "T21 anexo grande " + "x" * 6000, "nome": "grande.pdf"},
                {"texto": "T21 anexo pequeno", "nome": "pequeno.pdf"},
            ],
        },
    )
    e = est()
    k0, k1 = chave_recebimento("email", mid, 0), chave_recebimento("email", mid, 1)

    def por_chave(rota: str, k: str) -> list[tuple[int, bool]]:
        return [(p["status"], bool(p.get("replay"))) for p in chamadas(e, rota) if p["chave"] == k]

    posts0, posts1 = por_chave(r"/recebimentos", k0), por_chave(r"/recebimentos", k1)
    sem0 = por_chave(r"/recebimentos/sem-arquivo", k0)
    recs = {
        x["campos"]["anexo_indice"]: x
        for x in e["recebimentos"]
        if x["campos"].get("mensagem_id_canal") == mid
    }
    excecoes = [x for x in e["excecoes"] if mid in str(x.get("correlacao_id"))]
    resposta = json.loads(r.get("resposta") or "{}")
    checar(r["entregas"] == [503, 200], f"entregas do canal {r['entregas']} {r.get('resposta')}")
    checar(posts0 == [(413, False), (202, True)], f"anexo 0, POST /recebimentos: {posts0}")
    checar(sem0 == [(202, False)], f"anexo 0, sem-arquivo: {sem0}")
    checar(posts1 == [(503, False), (202, False)], f"anexo 1, POST /recebimentos: {posts1}")
    checar(
        sorted(recs) == ["0", "1"]
        and (recs["0"]["estado"], recs["0"].get("motivo")) == ("rejeitado", "acima_do_limite")
        and recs["1"]["estado"] == "aceito_para_processamento"
        and len(e["recebimentos"]) == 2,
        f"recebimentos: {e['recebimentos']}",
    )
    checar(not excecoes and not chamadas(e, r"/excecoes"), f"exceções: {excecoes}")
    checar(
        {k: resposta.get(k) for k in ("total", "aceitos", "sem_arquivo", "excecoes")}
        == {"total": 2, "aceitos": 1, "sem_arquivo": 1, "excecoes": 0},
        f"resposta do W4 na entrega final: {resposta}",
    )
    return {
        "entregas_do_canal": r["entregas"],
        "anexo_0": {
            "post_recebimentos": ["413", "202 (repetição do rejeitado)"],
            "sem_arquivo": [s for s, _ in sem0],
            "recebimento": "rejeitado (acima_do_limite)",
        },
        "anexo_1": {"post_recebimentos": [s for s, _ in posts1], "recebimento": "aceito"},
        "resposta_final_do_w4": resposta,
        "excecoes": 0,
    }


CENARIOS: list[tuple[str, str, Callable[[], dict]]] = [
    ("T1", "evento válido → exatamente 1 envio e 1 resultado", t1),
    ("T2", "mesmo evento reenviado (em série e 5x em paralelo) → continua 1 envio", t2),
    ("T3", "assinatura inválida/antiga/adulterada/outro ambiente → 401 e 0 envio", t3),
    ("T4", "evento obsoleto (reagendada / versão antiga) → 409 e 0 envio", t4),
    ("T5", "automação desligada → 423/encerra, 0 envio, segue agendada", t5),
    ("T6", "canal recusa 1x (503 + corpo de recusa) e aceita → 1 envio efetivo", t6),
    ("T7", "canal sempre recusa → rodadas limitadas no PCPR, exceção no fim, sem laço", t7),
    ("T8", "evento perdido → reconciliação envia 1 vez", t8),
    ("T9", "arquivo devolvido 2x (mesmo id) → 1 recebimento", t9),
    ("T10", "reinício do n8n no meio → nada duplicado, reconciliação completa", t10),
    ("T12", "erro inesperado num fluxo → W5 abre exceção", t12),
    (
        "T14",
        "resultado ambíguo no canal (tempo esgotado/desconexão após aceitar, 500) → "
        "resultado_desconhecido, 0 reenvio",
        t14,
    ),
    ("T15", "canal fora do ar e volta → PCPR reagenda (backoff) → 1 envio, sem exceção", t15),
    ("T16", "mensagem com 2 anexos → 2 recebimentos (chave por anexo); reenvio → 0 novos", t16),
    ("T17", "falha no POST /recebimentos ou no download → W4 não-2xx → reentrega → 1", t17),
    ("T18", "dedup de recebimento por (servidor, SHA-256): 2 servidores → 2; mesmo → 1", t18),
    (
        "T19",
        "recusa permanente do PCPR / anexo sem bytes → exceção ou registro sem arquivo, "
        "resposta final ao canal, sem laço de reentrega; recusa que muda entre entregas → "
        "2 exceções; falha temporária persistente → 503 + exceção fila_parada",
        t19,
    ),
    (
        "T21",
        "anexos mistos: 413 → sem-arquivo + falha transitória noutro anexo → reentrega repete o "
        "upload e recebe o rejeitado já gravado (sem 422, sem exceção)",
        t21,
    ),
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


def rodar_t20() -> dict:
    """Unitários sem Docker em processo separado (os dublês do teste de saída não tocam esta
    execução): validador do esquema (C2) e código de saída da suíte (C8)."""
    r = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", "test_validar_esquema", "test_saida_suite"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=120,
    )
    linhas = r.stderr.splitlines()
    rodados = next((int(x.split()[1]) for x in linhas if x.startswith("Ran ")), 0)
    return {
        "id": "T20",
        "nome": "unitários: validador do esquema (C2) e código de saída da suíte (C8)",
        "passou": r.returncode == 0 and rodados > 0,
        "evidencia": {
            "testes": rodados,
            "resultado": [x for x in linhas if x.endswith(("ok", "FAIL", "ERROR"))],
            "saida": r.returncode,
        },
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
        errors="replace",  # saída na página de código do console (com PYTHONUTF8=1 quebrava)
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
        relatorio["cenarios"].append(rodar_t20())
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
                pilha = traceback.extract_tb(exc.__traceback__)
                item["onde"] = [
                    f"{q.name}:{q.lineno} {q.line}" for q in pilha if q.name == fn.__name__
                ]
                item["traceback"] = traceback.format_exc()[-2000:]
                item["log_n8n"] = n8n_local.logs(30).splitlines()[-30:]
                with contextlib.suppress(Exception):  # diagnóstico do canal (entregas, downloads)
                    c = est_canal()
                    item["canal"] = {"inbound": c["inbound"][-6:], "downloads": c["downloads"][-6:]}
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
        # export que falhou também reprova a execução (C8 do PR #23), como no testar_whatsapp
        ok = all(c["passou"] for c in relatorio["cenarios"]) and "erro" not in relatorio.get(
            "exportacao", {}
        )
        return 0 if ok else 1
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
