"""Gera os JSON dos workflows W1–W8 (n8n 2.x) a partir de código revisável.

Fonte única dos fluxos do protótipo: o teste importa o que este script gera; depois exporta
do próprio n8n (com `"active": false`) para `docs/automacao/n8n/`.

    python construir_workflows.py <pasta-destino> [--pcpr URL] [--canal URL] [--whatsapp]

W1–W5: suíte principal (`testar_prototipo.py`). W6–W8: WhatsApp oficial (frente WA-3), só
contra o simulador da Graph API (`testar_whatsapp.py`); exportados DESLIGADOS.

URLs-base não são segredo e ficam num nó "Configuração" no começo de cada fluxo (o acesso a
variáveis de ambiente em nós vem bloqueado no n8n 2.x — `N8N_BLOCK_ENV_ACCESS_IN_NODE=true` —
e `$vars` é recurso pago). Segredos ficam SÓ em credenciais do n8n (referenciadas por id).
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

PCPR_PADRAO = "http://host.docker.internal:8765/api/automacao/v1"
CANAL_PADRAO = "http://host.docker.internal:8766"
# Simulador da Graph API. Na ativação real (só depois do portão da WA-3): a URL da Graph API na
# versão vigente e o phone_number_id da conta institucional — não são segredos.
GRAPH_PADRAO = "http://host.docker.internal:8767/v21.0"
NUMERO_ID_PADRAO = "100000000000001"
# O verify token da Meta é DERIVADO de uma credencial: HMAC-SHA256(chave, esta mensagem), em hex.
# Code node não lê credenciais e o Webhook não autentica por query; assim o valor esperado nunca
# fica em texto no workflow (achado do WA-3).
VERIFY_TOKEN_MENSAGEM = "pcpr-whatsapp-verify-token-v1"  # noqa: S105 (rótulo público, não segredo)

# Execuções que carregam destino, link-credencial, token de reserva ou arquivo não ficam guardadas
# no n8n (revisão de segurança; conferido pelo T13).
SEM_RETENCAO = {
    "saveDataSuccessExecution": "none",
    "saveDataErrorExecution": "none",
    "saveManualExecutions": False,
    "saveExecutionProgress": False,
}

# ids fixos (16 caracteres, como os do n8n) — o W1/W3 chamam o W2 por id; W5 é o errorWorkflow
W1, W2, W3, W4, W5 = (
    "pcprEntradaEvt01",
    "pcprEntregaCom01",
    "pcprReconcilia01",
    "pcprRecebimento1",
    "pcprErros0000001",
)
W6, W7, W8 = "pcprWhatsEnvio01", "pcprWhatsWebhk01", "pcprWhatsStatus1"
ADIAR_STATUS_MAX_S = 3600  # W8: até quando um status de wamid desconhecido é adiado (C7)
NOMES = {
    W1: "PCPR · Entrada de eventos",
    W2: "PCPR · Entregar comunicação",
    W3: "PCPR · Reconciliação",
    W4: "PCPR · Recebimento de arquivo",
    W5: "PCPR · Erros",
    W6: "PCPR · Enviar por WhatsApp (oficial)",
    W7: "PCPR · Webhook WhatsApp",
    W8: "PCPR · Status WhatsApp",
}
ARQUIVOS = {
    W1: "w1-entrada-de-eventos.json",
    W2: "w2-entregar-comunicacao.json",
    W3: "w3-reconciliacao.json",
    W4: "w4-recebimento-de-arquivo.json",
    W5: "w5-erros.json",
}
ARQUIVOS_WHATSAPP = {
    W6: "w6-enviar-por-whatsapp.json",
    W7: "w7-webhook-whatsapp.json",
    W8: "w8-status-whatsapp.json",
}

CRED_API = {"id": "pcprApiToken0001", "name": "PCPR · token da API de automação"}
CRED_HMAC = {"id": "pcprHmacEventos1", "name": "PCPR · segredo HMAC dos eventos"}
CRED_CANAL_API = {"id": "pcprCanalApi0001", "name": "Canal · chave de envio"}
CRED_CANAL_WEBHOOK = {"id": "pcprCanalWebhk01", "name": "Canal · token do webhook de entrada"}
CRED_DISPARO = {"id": "pcprWebhookInt01", "name": "PCPR · token do disparo da reconciliação"}
CRED_WA_TOKEN = {
    "id": "pcprWaToken00001",
    "name": "WhatsApp · token de acesso (usuário de sistema)",
}
CRED_WA_APP_SECRET = {
    "id": "pcprWaAppSecret1",
    "name": "WhatsApp · App Secret (assinatura dos webhooks)",
}
CRED_WA_VERIFY = {"id": "pcprWaVerifyTok1", "name": "WhatsApp · chave do verify token"}

_NS = uuid.UUID("6f1c3c3e-3a0b-4c55-9d7e-5c1a2b3c4d5e")


def _uid(*partes: str) -> str:
    return str(uuid.uuid5(_NS, "/".join(partes)))


class Fluxo:
    def __init__(self, wid: str) -> None:
        self.wid = wid
        self.nos: list[dict] = []
        self.conexoes: dict[str, dict] = {}

    def no(
        self, nome: str, tipo: str, versao: float, params: dict, pos: tuple[int, int], **extra: Any
    ) -> str:
        n = {
            "parameters": params,
            "id": _uid(self.wid, nome),
            "name": nome,
            "type": tipo,
            "typeVersion": versao,
            "position": list(pos),
        }
        n.update(extra)
        self.nos.append(n)
        return nome

    def liga(self, origem: str, destino: str, saida: int = 0, entrada: int = 0) -> None:
        saidas = self.conexoes.setdefault(origem, {"main": []})["main"]
        while len(saidas) <= saida:
            saidas.append([])
        saidas[saida].append({"node": destino, "type": "main", "index": entrada})

    def json(self, settings: dict) -> dict:
        return {
            "id": self.wid,
            "name": NOMES[self.wid],
            "nodes": self.nos,
            "connections": self.conexoes,
            "settings": {"executionOrder": "v1", **settings},
            "active": False,
            "pinData": {},
            "tags": [],
            "meta": {"templateCredsSetupCompleted": True},
        }


# ------------------------------------------------------------------ fábricas de nós


def _cond(expr: str, cid: str) -> dict:
    """Condição booleana (IF/Switch v2 de condições)."""
    return {
        "options": {
            "caseSensitive": True,
            "leftValue": "",
            "typeValidation": "loose",
            "version": 2,
        },
        "conditions": [
            {
                "id": cid,
                "leftValue": expr,
                "rightValue": "",
                "operator": {"type": "boolean", "operation": "true", "singleValue": True},
            }
        ],
        "combinator": "and",
    }


def chave_recebimento_js(canal_js: str, mensagem_js: str, indice_js: str) -> str:
    """Expressão n8n da chave do recebimento — a mesma regra de `comum.chave_recebimento`:
    `receb:<canal>:<id>:<anexo>` se tiver de 16 a 200 e for só ASCII imprimível (`[ -~]`, que mede
    igual em JS e em Python); senão, `receb#sha256:<canal>:<hex>:<anexo>`."""
    c, m, i = f"String({canal_js})", f"String({mensagem_js})", f"String({indice_js})"
    bruta = f"('receb:' + {c} + ':' + {m} + ':' + {i})"
    return (
        f"={{{{ {bruta}.length >= 16 && {bruta}.length <= 200 && /^[ -~]*$/.test({bruta}) "
        f"? {bruta} : "
        f"'receb#sha256:' + {c} + ':' + {m}.hash('sha256') + ':' + {i} }}}}"
    )


def chave_limitada(prefixo: str, logica_js: str) -> str:
    """Expressão n8n de uma Idempotency-Key que cabe no limite do contrato (16 a 200 caracteres).

    `logica_js` é a expressão JS da parte variável (ids do canal podem ter até 300 caracteres).
    Chave curta sai como sempre foi (legível, igual às já gravadas); se passar de 200, vira
    `<1º segmento>#sha256:<resto do prefixo><hex>` (ex.: `excecao#sha256:whatsapp-status:<hex>`),
    estável entre reentregas. O `#` no 1º segmento impede que um valor curto que pareça
    `sha256:<hex>` reproduza a forma com hash (a bruta sempre começa pelo prefixo intacto).
    """
    v = f"(String({logica_js}))"
    cabeca, _, resto = prefixo.partition(":")
    com_hash = f"{cabeca}#sha256:{resto}"
    return (
        f"={{{{ ('{prefixo}' + {v}).length >= 16 && ('{prefixo}' + {v}).length <= 200 "
        f"&& /^[ -~]*$/.test('{prefixo}' + {v}) "
        f"? '{prefixo}' + {v} : "
        f"'{com_hash}' + {v}.hash('sha256') }}}}"
    )


def se(f: Fluxo, nome: str, expr: str, pos: tuple[int, int]) -> str:
    return f.no(
        nome,
        "n8n-nodes-base.if",
        2.2,
        {"conditions": _cond(expr, _uid(f.wid, nome, "c")), "options": {}},
        pos,
    )


def definir(
    f: Fluxo,
    nome: str,
    campos: list[tuple[str, Any, str]],
    pos: tuple[int, int],
    manter: bool = False,
) -> str:
    return f.no(
        nome,
        "n8n-nodes-base.set",
        3.4,
        {
            "mode": "manual",
            "assignments": {
                "assignments": [
                    {"id": _uid(f.wid, nome, k), "name": k, "value": v, "type": t}
                    for k, v, t in campos
                ]
            },
            "includeOtherFields": manter,
            "options": {},
        },
        pos,
    )


def codigo(f: Fluxo, nome: str, js: str, pos: tuple[int, int], por_item: bool = False) -> str:
    params: dict[str, Any] = {"jsCode": js.strip()}
    if por_item:
        params = {"mode": "runOnceForEachItem", **params}
    return f.no(nome, "n8n-nodes-base.code", 2, params, pos)


def nada(f: Fluxo, nome: str, pos: tuple[int, int]) -> str:
    return f.no(nome, "n8n-nodes-base.noOp", 1, {}, pos)


def http(
    f: Fluxo,
    nome: str,
    metodo: str,
    url: str,
    pos: tuple[int, int],
    *,
    cred: dict | None = CRED_API,
    cabecalhos: list[tuple[str, str]] | None = None,
    corpo_json: str | None = None,
    completo: bool = False,
    timeout: int = 10000,
    tentativas: int = 0,
    espera_ms: int = 1000,
    saida_erro: bool = False,
    extra_params: dict | None = None,
) -> str:
    params: dict[str, Any] = {"method": metodo, "url": url}
    extra: dict[str, Any] = {}
    if cred:
        params["authentication"] = "genericCredentialType"
        params["genericAuthType"] = "httpHeaderAuth"
        extra["credentials"] = {"httpHeaderAuth": cred}
    if cabecalhos:
        params["sendHeaders"] = True
        params["headerParameters"] = {
            "parameters": [{"name": k, "value": v} for k, v in cabecalhos]
        }
    if corpo_json is not None:
        params.update(sendBody=True, specifyBody="json", jsonBody=corpo_json)
    opcoes: dict[str, Any] = {"timeout": timeout}
    if completo:
        opcoes["response"] = {"response": {"fullResponse": True, "neverError": True}}
    params["options"] = opcoes
    if extra_params:
        params.update(extra_params)
    if tentativas:
        extra.update(retryOnFail=True, maxTries=tentativas, waitBetweenTries=espera_ms)
    if saida_erro:
        extra["onError"] = "continueErrorOutput"
    return f.no(nome, "n8n-nodes-base.httpRequest", 4.2, params, pos, **extra)


def chamar_w2(f: Fluxo, nome: str, pos: tuple[int, int]) -> str:
    return chamar(f, nome, W2, pos)


def chamar(
    f: Fluxo, nome: str, wid: str, pos: tuple[int, int], continuar: bool = True, **extra: Any
) -> str:
    """Execute Workflow (sub-workflow, espera o fim). `continuar`: erro do sub-workflow não
    derruba o chamador (vai ao W5 pela execução do próprio sub-workflow)."""
    if continuar:
        extra["onError"] = "continueRegularOutput"
    return f.no(
        nome,
        "n8n-nodes-base.executeWorkflow",
        1.2,
        {
            "workflowId": {
                "__rl": True,
                "value": wid,
                "mode": "id",
                "cachedResultName": NOMES[wid],
            },
            "workflowInputs": {
                "mappingMode": "defineBelow",
                "value": {},
                "matchingColumns": [],
                "schema": [],
                "attemptToConvertTypes": False,
                "convertFieldsToString": True,
            },
            "options": {"waitForSubWorkflow": True},
        },
        pos,
        **extra,
    )


# ------------------------------------------------------------------ W1


JS_PREPARAR = r"""
// Corpo BRUTO (opção "Raw Body" do Webhook): a assinatura cobre os bytes exatos enviados pelo
// PCPR — re-serializar o JSON mudaria espaços/escapes e quebraria (ou falsificaria) a checagem.
const AMBIENTE_ESPERADO = 'teste'; // trocar por 'producao' na instância de produção
const JANELA_S = 300;               // frescor: ±5 min
const item = $input.first();
const h = item.json.headers || {};
let bruto = '';
const bin = item.binary && item.binary.data;
if (bin) {
  if (bin.id) {
    const buf = await this.helpers.getBinaryDataBuffer(0, 'data');
    bruto = buf.toString('utf8');
  } else {
    bruto = Buffer.from(bin.data, 'base64').toString('utf8');
  }
}
const cab = String(h['x-pcpr-assinatura'] || '');
const m = /^t=(\d+),v1=([a-f0-9]{64})$/.exec(cab);
let evento = null;
try { evento = JSON.parse(bruto); } catch (e) { evento = null; }
const agora = Math.floor(Date.now() / 1000);
const t = m ? Number(m[1]) : 0;
return [{ json: {
  formato_ok: Boolean(m && evento && typeof evento === 'object'),
  frescor_ok: Boolean(m) && Math.abs(agora - t) <= JANELA_S,
  v1: m ? m[2] : '',
  mensagem_assinada: (m ? m[1] : '0') + '.' + bruto,
  evento_id_cabecalho: String(h['x-pcpr-evento-id'] || ''),
  ambiente_ok: Boolean(evento) && evento.ambiente === AMBIENTE_ESPERADO,
  evento,
} }];
"""

JS_VALIDAR = r"""
// Comparação em tempo constante do HMAC calculado (nó Crypto, segredo na credencial) com v1.
const j = $input.first().json;
const a = String(j.hmac_calculado || '');
const b = String(j.v1 || '');
let dif = (a.length === 64 && b.length === 64) ? 0 : 1;
for (let i = 0; i < Math.min(a.length, b.length); i++) dif |= a.charCodeAt(i) ^ b.charCodeAt(i);
const ev = j.evento || {};
let motivo = 'ok';
if (!j.formato_ok) motivo = 'formato';
else if (!j.frescor_ok) motivo = 'fora_da_janela';
else if (dif !== 0) motivo = 'assinatura';
else if (!j.ambiente_ok) motivo = 'ambiente';
else if (ev.id !== j.evento_id_cabecalho) motivo = 'id_divergente';
const valido = motivo === 'ok';
return [{ json: { valido, motivo, evento: valido ? ev : null } }];
"""


def w1() -> dict:
    f = Fluxo(W1)
    f.no(
        "Webhook de eventos",
        "n8n-nodes-base.webhook",
        2.1,
        {
            "httpMethod": "POST",
            "path": "pcpr-eventos",
            "responseMode": "responseNode",
            "options": {"rawBody": True},
        },
        (0, 300),
        webhookId=_uid(W1, "webhook"),
    )
    codigo(f, "Preparar verificação", JS_PREPARAR, (220, 300))
    f.no(
        "Calcular HMAC",
        "n8n-nodes-base.crypto",
        2,
        {
            "action": "hmac",
            "type": "SHA256",
            "value": "={{ $json.mensagem_assinada }}",
            "dataPropertyName": "hmac_calculado",
            "encoding": "hex",
        },
        (440, 300),
        credentials={"crypto": CRED_HMAC},
    )
    codigo(f, "Validar assinatura e frescor", JS_VALIDAR, (660, 300))
    se(f, "Assinatura válida?", "={{ $json.valido }}", (880, 300))
    f.no(
        "Responder 202",
        "n8n-nodes-base.respondToWebhook",
        1.1,
        {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify({ aceito: true, evento_id: $json.evento.id }) }}",
            "options": {"responseCode": 202},
        },
        (1100, 200),
    )
    f.no(
        "Responder 401",
        "n8n-nodes-base.respondToWebhook",
        1.1,
        {
            "respondWith": "json",
            "responseBody": '{"erro":"assinatura_invalida"}',
            "options": {"responseCode": 401},
        },
        (1100, 420),
    )
    f.no(
        "Deduplicar por id do evento",
        "n8n-nodes-base.removeDuplicates",
        2,
        {
            "operation": "removeItemsSeenInPreviousExecutions",
            "dedupeValue": "={{ $json.evento.id }}",
            "options": {"scope": "workflow", "historySize": 10000},
        },
        (1320, 200),
    )
    f.no(
        "Rotear por tipo",
        "n8n-nodes-base.switch",
        3.2,
        {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "options": {
                                "caseSensitive": True,
                                "leftValue": "",
                                "typeValidation": "strict",
                                "version": 2,
                            },
                            "conditions": [
                                {
                                    "id": _uid(W1, "switch", "agendada"),
                                    "leftValue": "={{ $json.evento.tipo }}",
                                    "rightValue": "comunicacao.agendada",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                            "combinator": "and",
                        },
                        "renameOutput": True,
                        "outputKey": "comunicacao.agendada",
                    }
                ]
            },
            "options": {"fallbackOutput": "extra", "renameFallbackOutput": "outros tipos"},
        },
        (1540, 200),
    )
    # Tolerância de relógio: comparar `enviar_em == agora` entre duas máquinas falha por
    # milissegundos (visto no protótipo: o relógio do contêiner ~0,2 s atrás do host fazia o
    # evento "imediato" cair em "ainda não é hora"). O n8n só ANTECIPA; quem decide é o
    # reservar do PCPR (409 regra_violada se for cedo; a reconciliação pega depois).
    se(
        f,
        "Já é hora de enviar? (tolerância 2 min)",
        "={{ $json.evento.dados.imediato === true || "
        "new Date($json.evento.dados.enviar_em).getTime() <= Date.now() + 120000 }}",
        (1760, 100),
    )
    definir(
        f,
        "Pedido de entrega",
        [
            ("comunicacao_id", "={{ $json.evento.dados.comunicacao_id }}", "number"),
            ("versao", "={{ $json.evento.recurso.versao }}", "number"),
            ("correlacao_id", "={{ $json.evento.correlacao_id }}", "string"),
            ("evento_id", "={{ $json.evento.id }}", "string"),
            ("origem", "evento", "string"),
        ],
        (1980, 0),
    )
    chamar_w2(f, "Entregar comunicação (W2)", (2200, 0))
    nada(f, "Ainda não é hora (reconciliação envia)", (1980, 200))
    nada(f, "Outros tipos: só registro", (1760, 340))
    for a, b in [
        ("Webhook de eventos", "Preparar verificação"),
        ("Preparar verificação", "Calcular HMAC"),
        ("Calcular HMAC", "Validar assinatura e frescor"),
        ("Validar assinatura e frescor", "Assinatura válida?"),
        ("Responder 202", "Deduplicar por id do evento"),
        ("Deduplicar por id do evento", "Rotear por tipo"),
        ("Pedido de entrega", "Entregar comunicação (W2)"),
    ]:
        f.liga(a, b)
    f.liga("Assinatura válida?", "Responder 202", 0)
    f.liga("Assinatura válida?", "Responder 401", 1)
    f.liga("Rotear por tipo", "Já é hora de enviar? (tolerância 2 min)", 0)
    f.liga("Rotear por tipo", "Outros tipos: só registro", 1)
    f.liga("Já é hora de enviar? (tolerância 2 min)", "Pedido de entrega", 0)
    f.liga("Já é hora de enviar? (tolerância 2 min)", "Ainda não é hora (reconciliação envia)", 1)
    return f.json({"errorWorkflow": W5, "saveDataSuccessExecution": "none"})


# ------------------------------------------------------------------ W2

TENTATIVAS_CANAL = 3  # tentativas curtas por rodada; o PCPR controla as rodadas (backoff)

JS_CLASSIFICAR_ENVIO = r"""
// Tentativa __K__ de __MAX__ no canal (o retryOnFail nativo do n8n NÃO é usado aqui: ele repete
// qualquer erro, inclusive tempo esgotado depois de o canal aceitar — duplicaria; C5/PR #23).
// Só se repete o que PROVA que o canal NÃO aceitou: conexão recusada/DNS antes de enviar, ou
// HTTP 429/503 com corpo de recusa ("aceita": false). Tempo esgotado, conexão derrubada no meio
// (ECONNRESET/"socket hang up") e respostas ambíguas (500/502/504, 503 sem corpo de recusa) →
// resultado_desconhecido + exceção, sem reenvio. Recusas esgotadas → falha_temporaria: o PCPR
// reagenda com backoff e só abre exceção quando acabarem as rodadas (C6).
const TENTATIVA = __K__;
const MAX = __MAX__;
const anteriores = __ANTERIORES__;
const it = $input.first().json;
let sinal = 'ambiguo';
let descr = '';
let pid = '';
let sc = 0;
if (it.error !== undefined) {  // saída de erro do nó HTTP: só falha de rede chega aqui
  const e = it.error || {};
  const texto = JSON.stringify(e) + ' ' + String(e.message || '');
  if (/ECONNREFUSED|ENOTFOUND|EAI_AGAIN|refused the connection|DNS server returned/i.test(texto)) {
    sinal = 'recusado';
    descr = 'conexão recusada antes do envio';
  } else {
    descr = 'rede: ' + String(e.message || e.code || 'erro de rede').slice(0, 200);
  }
} else {  // resposta HTTP completa (neverError): o status é dado, não exceção
  sc = Number(it.statusCode || 0);
  const corpo = (it.body && typeof it.body === 'object') ? it.body : {};
  if (sc >= 200 && sc < 300) {
    sinal = 'aceito';
    pid = String(corpo.provedor_mensagem_id || '');
  } else if ((sc === 429 || sc === 503) && corpo.aceita === false) {
    sinal = 'recusado';
  } else if (sc >= 400 && sc < 500 && sc !== 408 && sc !== 429) {
    sinal = 'rejeitado';
  }
  descr = 'HTTP ' + sc + (corpo.erro ? ' ' + String(corpo.erro).slice(0, 100) : '');
}
const historico = [...anteriores, sinal + ' (' + descr + ')'];
if (sinal === 'recusado' && TENTATIVA < MAX) {
  await new Promise((r) => setTimeout(r, 1000));  // espera curta antes da próxima tentativa
  return [{ json: { acao: 'retentar', historico } }];
}
const saida = {
  aceito: { resultado: 'enviada', motivo_excecao: '' },
  recusado: { resultado: 'falha_temporaria', motivo_excecao: '' },
  rejeitado: {
    resultado: 'falha_definitiva',
    motivo_excecao: (sc === 401 || sc === 403) ? 'canal_indisponivel' : 'outro',
  },
  ambiguo: { resultado: 'resultado_desconhecido', motivo_excecao: 'resultado_desconhecido' },
}[sinal];
const resumo = historico.map((h, i) => (i + 1) + 'ª tentativa: ' + h).join('; ').slice(0, 500);
return [{ json: { acao: 'registrar', ...saida, provedor_mensagem_id: pid,
  erro: sinal === 'aceito' ? '' : resumo, historico } }];
"""


def _nome_tentativa(base: str, k: int) -> str:
    return f"{base} ({k}ª tentativa)"


def w2() -> dict:
    f = Fluxo(W2)
    cfg = "$('Configuração').first().json"
    ctx = "$('Contexto do envio').first().json"
    f.no(
        "Quando chamado por outro workflow",
        "n8n-nodes-base.executeWorkflowTrigger",
        1.1,
        {"inputSource": "passthrough"},
        (0, 300),
    )
    definir(
        f,
        "Configuração",
        [
            ("cfg_pcpr", PCPR_PADRAO, "string"),
            ("cfg_canal", CANAL_PADRAO, "string"),
            ("fluxo", "km-vespera", "string"),
        ],
        (220, 300),
        manter=True,
    )
    http(
        f,
        "Consultar estado",
        "GET",
        "={{ $json.cfg_pcpr }}/estado",
        (440, 300),
        cabecalhos=[("X-PCPR-Correlacao", "={{ $json.correlacao_id }}")],
        tentativas=2,
        espera_ms=1000,
    )
    se(
        f,
        "Automação ligada?",
        f"={{{{ $json.ligada === true && ($json.fluxos || {{}})[{cfg}.fluxo] !== false }}}}",
        (660, 300),
    )
    nada(f, "Fim: automação desligada", (880, 480))
    http(
        f,
        "Reservar comunicação",
        "POST",
        f"={{{{ {cfg}.cfg_pcpr }}}}/comunicacoes/{{{{ {cfg}.comunicacao_id }}}}/reservar",
        (880, 200),
        completo=True,
        tentativas=2,
        espera_ms=1000,
        cabecalhos=[
            # chave estável DENTRO da execução (retentativa HTTP devolve a mesma reserva) e
            # distinta ENTRE execuções (outra execução recebe 409 em vez da mesma reserva).
            (
                "Idempotency-Key",
                f"=reserva:{{{{ {cfg}.comunicacao_id }}}}:v{{{{ {cfg}.versao }}}}"
                ":exec{{ $execution.id }}",
            ),
            ("X-PCPR-Versao-Esperada", f"={{{{ {cfg}.versao }}}}"),
            ("X-PCPR-Correlacao", f"={{{{ {cfg}.correlacao_id }}}}"),
        ],
    )

    def regra(valor: int, chave: str) -> dict:
        return {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "loose",
                    "version": 2,
                },
                "conditions": [
                    {
                        "id": _uid(W2, "sw", chave),
                        "leftValue": "={{ $json.statusCode }}",
                        "rightValue": valor,
                        "operator": {"type": "number", "operation": "equals"},
                    }
                ],
                "combinator": "and",
            },
            "renameOutput": True,
            "outputKey": chave,
        }

    f.no(
        "Resultado da reserva",
        "n8n-nodes-base.switch",
        3.2,
        {
            "rules": {
                "values": [
                    regra(200, "reservada"),
                    regra(409, "409 não enviar"),
                    regra(423, "423 desligada"),
                ]
            },
            "options": {"fallbackOutput": "extra", "renameFallbackOutput": "inesperado"},
        },
        (1100, 200),
    )
    nada(f, "Fim: obsoleta, cancelada ou já enviada (409)", (1320, 320))
    nada(f, "Fim: desligada no meio do caminho (423)", (1320, 440))
    f.no(
        "Erro: reserva inesperada",
        "n8n-nodes-base.stopAndError",
        1,
        {
            "errorMessage": "=Reserva devolveu HTTP {{ $json.statusCode }}: "
            "{{ JSON.stringify($json.body).slice(0, 300) }}",
        },
        (1320, 560),
    )
    definir(
        f,
        "Contexto do envio",
        [
            ("comunicacao_id", "={{ $json.body.id }}", "number"),
            ("reserva_token", "={{ $json.body.reserva.token }}", "string"),
            ("canal", "={{ $json.body.canal }}", "string"),
            ("destino", "={{ $json.body.destino }}", "string"),
            ("mensagem", "={{ $json.body.mensagem }}", "object"),
            ("anexos", "={{ $json.body.anexos || [] }}", "array"),
            ("idempotencia_canal", "={{ $json.body.idempotencia_canal }}", "string"),
            ("correlacao_id", f"={{{{ {cfg}.correlacao_id }}}}", "string"),
            ("cfg_pcpr", f"={{{{ {cfg}.cfg_pcpr }}}}", "string"),
            ("cfg_canal", f"={{{{ {cfg}.cfg_canal }}}}", "string"),
        ],
        (1320, 100),
    )
    # Desvio por canal (o canal vem da RESERVA, não do evento): WhatsApp oficial → W6, que envia,
    # registra o resultado e abre exceção; os demais seguem para o canal simulado.
    se(f, "Canal é WhatsApp?", "={{ $json.canal === 'whatsapp' }}", (1430, -80))
    chamar(f, "Enviar por WhatsApp (W6)", W6, (1650, -180))
    nada(f, "Fim: tratado pelo W6", (1870, -180))
    # Tentativas no canal desenroladas (sem retryOnFail): cada uma tem a resposta HTTP completa
    # como dado (neverError) e a falha de rede na saída de erro; o classificador decide se repete.
    x0 = 1540
    for k in range(1, TENTATIVAS_CANAL + 1):
        enviar = _nome_tentativa("Enviar ao canal", k)
        classificar = _nome_tentativa("Classificar envio", k)
        http(
            f,
            enviar,
            "POST",
            f"={{{{ {ctx}.cfg_canal }}}}/canal/enviar",
            (x0, 100),
            cred=CRED_CANAL_API,
            completo=True,
            saida_erro=True,
            corpo_json=f"={{{{ JSON.stringify({{ canal: {ctx}.canal, destino: {ctx}.destino, "
            f"mensagem: {ctx}.mensagem, idempotencia_canal: {ctx}.idempotencia_canal, "
            f"comunicacao_id: {ctx}.comunicacao_id, correlacao_id: {ctx}.correlacao_id }}) }}}}",
        )
        anteriores = (
            "[]"
            if k == 1
            else f"($('{_nome_tentativa('Classificar envio', k - 1)}').first().json.historico"
            " || [])"
        )
        js = (
            JS_CLASSIFICAR_ENVIO.replace("__K__", str(k))
            .replace("__MAX__", str(TENTATIVAS_CANAL))
            .replace("__ANTERIORES__", anteriores)
        )
        codigo(f, classificar, js, (x0 + 220, 100))
        f.liga(enviar, classificar, 0)
        f.liga(enviar, classificar, 1)  # falha de rede também é classificada (não derruba)
        if k < TENTATIVAS_CANAL:
            retentar = _nome_tentativa("Retentar?", k)
            se(f, retentar, "={{ $json.acao === 'retentar' }}", (x0 + 440, 100))
            f.liga(classificar, retentar)
            f.liga(retentar, _nome_tentativa("Enviar ao canal", k + 1), 0)
            f.liga(retentar, "Resultado do envio", 1)
        else:
            f.liga(classificar, "Resultado do envio")
        x0 += 660
    definir(
        f,
        "Resultado do envio",
        [
            ("resultado", "={{ $json.resultado }}", "string"),
            ("provedor_mensagem_id", "={{ $json.provedor_mensagem_id || '' }}", "string"),
            ("erro", "={{ $json.erro || '' }}", "string"),
            ("motivo_excecao", "={{ $json.motivo_excecao || '' }}", "string"),
        ],
        (x0, 300),
    )
    res = "$('Resultado do envio').first().json"
    http(
        f,
        "Registrar resultado",
        "POST",
        f"={{{{ {ctx}.cfg_pcpr }}}}/comunicacoes/{{{{ {ctx}.comunicacao_id }}}}/resultado",
        (x0 + 220, 300),
        tentativas=3,  # seguro: Idempotency-Key estável por reserva
        espera_ms=1000,
        cabecalhos=[
            (
                "Idempotency-Key",
                f"=resultado:{{{{ {ctx}.comunicacao_id }}}}:{{{{ {ctx}.reserva_token }}}}",
            ),
            ("X-PCPR-Correlacao", f"={{{{ {ctx}.correlacao_id }}}}"),
        ],
        corpo_json=f"={{{{ JSON.stringify({{ reserva_token: {ctx}.reserva_token, "
        "resultado: $json.resultado, provedor: 'canal-simulado', "
        "provedor_mensagem_id: $json.provedor_mensagem_id || undefined, "
        "erro: $json.erro || undefined }) }}",
    )
    # exceção só para falha definitiva e resultado desconhecido; falha_temporaria é do PCPR
    se(f, "Abrir exceção?", f"={{{{ Boolean({res}.motivo_excecao) }}}}", (x0 + 440, 300))
    nada(f, "Fim: registrado", (x0 + 660, 200))
    http(
        f,
        "Abrir exceção",
        "POST",
        f"={{{{ {ctx}.cfg_pcpr }}}}/excecoes",
        (x0 + 660, 400),
        tentativas=3,
        espera_ms=1000,
        cabecalhos=[
            (
                "Idempotency-Key",
                f"=excecao:com{{{{ {ctx}.comunicacao_id }}}}:{{{{ {ctx}.reserva_token }}}}",
            ),
        ],
        corpo_json=f"={{{{ JSON.stringify({{ fluxo: {cfg}.fluxo, "
        f"correlacao_id: {ctx}.correlacao_id, "
        f"motivo: {res}.motivo_excecao, "
        "detalhe: 'comunicacao ' + " + ctx + ".comunicacao_id + ': ' + "
        f"{res}.erro, "
        "execucao_orquestrador: String($execution.id), "
        f"recurso: {{ tipo: 'comunicacao', id: {ctx}.comunicacao_id }} }}) }}}}",
    )
    for a, b in [
        ("Quando chamado por outro workflow", "Configuração"),
        ("Configuração", "Consultar estado"),
        ("Consultar estado", "Automação ligada?"),
        ("Contexto do envio", "Canal é WhatsApp?"),
        ("Enviar por WhatsApp (W6)", "Fim: tratado pelo W6"),
        ("Resultado do envio", "Registrar resultado"),
        ("Registrar resultado", "Abrir exceção?"),
    ]:
        f.liga(a, b)
    f.liga("Automação ligada?", "Reservar comunicação", 0)
    f.liga("Automação ligada?", "Fim: automação desligada", 1)
    f.liga("Reservar comunicação", "Resultado da reserva")
    f.liga("Resultado da reserva", "Contexto do envio", 0)
    f.liga("Resultado da reserva", "Fim: obsoleta, cancelada ou já enviada (409)", 1)
    f.liga("Resultado da reserva", "Fim: desligada no meio do caminho (423)", 2)
    f.liga("Resultado da reserva", "Erro: reserva inesperada", 3)
    f.liga("Canal é WhatsApp?", "Enviar por WhatsApp (W6)", 0)
    f.liga("Canal é WhatsApp?", _nome_tentativa("Enviar ao canal", 1), 1)
    f.liga("Abrir exceção?", "Abrir exceção", 0)
    f.liga("Abrir exceção?", "Fim: registrado", 1)
    # mensagem com destino e link-credencial: nada fica guardado no n8n (diagnóstico só pelo W5)
    return f.json({"errorWorkflow": W5, "callerPolicy": "workflowsFromSameOwner", **SEM_RETENCAO})


# ------------------------------------------------------------------ W3


def w3() -> dict:
    f = Fluxo(W3)
    f.no(
        "A cada 15 minutos",
        "n8n-nodes-base.scheduleTrigger",
        1.2,
        {"rule": {"interval": [{"field": "minutes", "minutesInterval": 15}]}},
        (0, 200),
    )
    f.no(
        "Disparo manual (teste)",
        "n8n-nodes-base.webhook",
        2.1,
        {
            "httpMethod": "POST",
            "path": "pcpr-reconciliar",
            "authentication": "headerAuth",
            "responseMode": "lastNode",
            "options": {},
        },
        (0, 400),
        webhookId=_uid(W3, "webhook"),
        credentials={"httpHeaderAuth": CRED_DISPARO},
    )
    definir(f, "Configuração", [("cfg_pcpr", PCPR_PADRAO, "string")], (220, 300))
    http(
        f,
        "Listar devidas",
        "GET",
        "={{ $json.cfg_pcpr }}/comunicacoes/devidas?limite=50",
        (440, 300),
        tentativas=2,
        espera_ms=1000,
    )
    se(f, "Há devidas?", "={{ ($json.itens || []).length > 0 }}", (660, 300))
    definir(f, "Resumo: nada devido", [("devidas", 0, "number")], (880, 460))
    f.no(
        "Separar comunicações",
        "n8n-nodes-base.splitOut",
        1,
        {"fieldToSplitOut": "itens", "options": {}},
        (880, 200),
    )
    f.no(
        "Uma por vez",
        "n8n-nodes-base.splitInBatches",
        3,
        {"batchSize": 1, "options": {}},
        (1100, 200),
    )
    definir(
        f,
        "Pedido de entrega",
        [
            ("comunicacao_id", "={{ $json.id }}", "number"),
            ("versao", "={{ $json.versao }}", "number"),
            ("correlacao_id", "={{ $json.correlacao_id }}", "string"),
            ("origem", "reconciliacao", "string"),
        ],
        (1320, 300),
    )
    chamar_w2(f, "Entregar comunicação (W2)", (1540, 300))
    codigo(
        f,
        "Resumo",
        "return [{ json: { devidas: $('Separar comunicações').all().length } }];",
        (1320, 60),
    )
    for a, b in [
        ("A cada 15 minutos", "Configuração"),
        ("Disparo manual (teste)", "Configuração"),
        ("Configuração", "Listar devidas"),
        ("Listar devidas", "Há devidas?"),
        ("Separar comunicações", "Uma por vez"),
        ("Pedido de entrega", "Entregar comunicação (W2)"),
        ("Entregar comunicação (W2)", "Uma por vez"),
    ]:
        f.liga(a, b)
    f.liga("Há devidas?", "Separar comunicações", 0)
    f.liga("Há devidas?", "Resumo: nada devido", 1)
    f.liga("Uma por vez", "Resumo", 0)
    f.liga("Uma por vez", "Pedido de entrega", 1)
    return f.json({"errorWorkflow": W5, "saveDataSuccessExecution": "none"})


# ------------------------------------------------------------------ W4

LIMITE_ARQUIVO_BYTES = 25 * 1024 * 1024  # limite da importação documental (contrato)
# W4: falha temporária persistente numa mensagem mais velha que isto → exceção fila_parada
# (arquitetura §3.7; o canal continua reentregando). Valor proposto, a calibrar.
FILA_PARADA_APOS_S = 4 * 3600

JS_SEPARAR_ANEXOS = r"""
// Um item por anexo: a chave do recebimento é receb:<canal>:<mensagem_id_canal>:<anexo_indice>
// (contrato 10-6 E1; C3 do PR #23) e o PCPR consolida a mensagem por total_anexos.
// O que não terá bytes vai para /recebimentos/sem-arquivo (contrato 10-6 E2): mensagem sem
// anexo (anexo_indice 0, total_anexos 1) e anexo declarado acima do limite (nem é baixado).
const cfg = $('Configuração').first().json;
const b = cfg.body || {};
const anexos = Array.isArray(b.anexos) ? b.anexos : [];
const LIMITE = Number(cfg.cfg_limite_bytes);
const base = {
  canal: String(b.canal || ''),
  mensagem_id: String(b.mensagem_id || ''),
  remetente: String(b.remetente || ''),
  recebido_em: String(b.recebido_em || ''),
  em_resposta_a_comunicacao: b.em_resposta_a_comunicacao ?? '',
};
if (!anexos.length) {
  return [{ json: { ...base, arquivo_id: '', nome_arquivo: '', tamanho: 0, anexo_indice: 0,
    total_anexos: 1, acao: 'sem_arquivo', motivo: 'sem_anexo' } }];
}
return anexos.map((a, i) => {
  const tamanho = Number(a.tamanho || 0);
  const grande = tamanho > LIMITE;
  return { json: { ...base,
    arquivo_id: String(a.id || ''),
    nome_arquivo: String(a.nome || ('anexo-' + i)),
    tamanho,
    anexo_indice: i,
    total_anexos: anexos.length,
    acao: grande ? 'sem_arquivo' : 'baixar',
    motivo: grande ? 'acima_do_limite' : '',
  } };
});
"""

JS_CLASSIFICAR_PCPR_W4 = r"""
// Resposta do PCPR a __OPERACAO__ → próximo passo do anexo (arquitetura §3.7/§3.12):
// - aceito (2xx) → fim;
// - transitório (rede, 5xx, 408, 423 desligada, 425, 429; 401/403 = credencial a corrigir) →
//   reentregar: o W4 responde 503 e a mensagem continua no canal (nada se perde);
// - 413 em /recebimentos → /recebimentos/sem-arquivo (motivo acima_do_limite, contrato);
// - recusa permanente (409 canal_bloqueado ou conflito_de_versao, 422, outro 4xx): repetir não
//   resolve → exceção humana com chave estável e resposta FINAL ao canal (sem laço de reentrega).
const OP = '__OPERACAO__';
const ctx = $('Anexo atual').first().json;
const it = $input.first().json;
let sc = 0;
let corpo = {};
let rede = '';
if (it.error !== undefined) {  // saída de erro do nó HTTP: falha de rede/tempo esgotado
  const e = it.error || {};
  rede = String(e.message || e.code || e || 'erro de rede').slice(0, 200);
} else {
  sc = Number(it.statusCode || 0);
  corpo = (it.body && typeof it.body === 'object') ? it.body : {};
}
const codigo = String(corpo.codigo || '');
const descr = rede ? ('rede: ' + rede) : ('HTTP ' + sc + (codigo ? ' ' + codigo : ''));
const base = { ...ctx, ultima_resposta: (OP + ': ' + descr).slice(0, 300) };
if (rede || sc === 0 || sc >= 500 || [401, 403, 408, 423, 425, 429].includes(sc)) {
  return [{ json: { ...base, passo: 'fim', desfecho: 'reentregar' } }];
}
if (sc >= 200 && sc < 300) {
  return [{ json: { ...base, passo: 'fim',
    desfecho: OP === 'recebimento' ? 'aceito' : 'registrado_sem_arquivo',
    recebimento_id: corpo.id ?? null, estado: String(corpo.estado || '') } }];
}
if (sc === 413 && OP === 'recebimento') {
  return [{ json: { ...base, passo: 'sem_arquivo', motivo: 'acima_do_limite' } }];
}
// Chave e corpo da exceção são função SÓ da classe da recusa (operação, HTTP, código, motivo do
// sem-arquivo): a mesma recusa reentregue repete a chave com o MESMO corpo (201 repetição); uma
// recusa diferente na entrega seguinte (ex.: 422 e depois 409 canal_bloqueado) abre OUTRA exceção
// em vez de reusar a chave com outro corpo (422 "chave reutilizada" → 503 em laço; 3ª verificação).
// Por isso a `mensagem` livre do PCPR não entra no corpo (pode variar entre entregas).
const motivoSem = OP === 'sem_arquivo' ? $('Pedido sem arquivo').first().json.motivo : '';
const classe = [OP, 'http' + sc, codigo, motivoSem].filter(Boolean).join('-');
const motivo_excecao = codigo === 'canal_bloqueado' ? 'canal_indisponivel' : 'outro';
return [{ json: { ...base, passo: 'excecao', motivo_excecao,
  // contrato: excecao:<fluxo>:<recebimento>:<motivo>; o prefixo excecao:recebimento-canais: vem no
  // cabeçalho, que troca o resto por sha256 quando passaria de 200 caracteres (id longo do canal)
  chave_excecao: 'receb:' + ctx.canal + ':' + ctx.mensagem_id + ':' +
    ctx.anexo_indice + ':' + classe + ':' + motivo_excecao,
  detalhe: ('PCPR recusou ' + OP + ' de forma permanente (' + descr + '); canal ' + ctx.canal +
    ', anexo ' + (Number(ctx.anexo_indice) + 1) + ' de ' + ctx.total_anexos +
    (motivoSem ? ', motivo ' + motivoSem : '') +
    '. O canal recebeu resposta final e não reentrega: conferir a mensagem na caixa.')
    .slice(0, 2000) } }];
"""

JS_CLASSIFICAR_DOWNLOAD_W4 = r"""
// Falha no download do anexo no canal. 4xx estável (404/410 o anexo não existe mais; 400, 405,
// 415, 422… id malformado ou anexo não suportado) = permanente → /recebimentos/sem-arquivo com
// motivo nao_baixado (o PCPR abre a exceção arquivo_nao_baixado, contrato) e resposta final ao
// canal. Só o que pode passar sozinho volta para reentrega (503): rede, 5xx, 408, 425, 429 e
// 401/403 (credencial do canal: problema de configuração; se persistir, vira fila_parada).
const ctx = $('Anexo atual').first().json;
const e = $input.first().json.error || {};
const texto = JSON.stringify(e) + ' ' + String(e.message || '');
let sc = Number(e.statusCode || e.status || e.httpCode || 0);
if (!sc) {
  const m = /"(?:httpCode|statusCode|status)":"?(\d{3})/.exec(texto) ||
    /^(\d{3})\b/.exec(String(e.message || ''));
  if (m) sc = Number(m[1]);
}
const descr = 'download: ' + (sc ? 'HTTP ' + sc : String(e.message || e.code || 'erro de rede'))
  .slice(0, 200);
const transitorio = [401, 403, 408, 425, 429].includes(sc);
if (sc >= 400 && sc < 500 && !transitorio) {
  return [{ json: { ...ctx, passo: 'sem_arquivo', motivo: 'nao_baixado',
    ultima_resposta: descr } }];
}
return [{ json: { ...ctx, passo: 'fim', desfecho: 'reentregar', ultima_resposta: descr } }];
"""

JS_DECIDIR_RESPOSTA_W4 = r"""
// 2xx ao canal SÓ quando todo anexo teve desfecho final no PCPR (C9): aceito, registrado sem
// arquivo ou exceção aberta (recusa permanente). Qualquer 'reentregar' → 503: o canal reentrega
// a mensagem inteira; o que já foi registrado repete a mesma Idempotency-Key, sem efeito novo.
const itens = $input.all().map((i) => i.json);
const esperados = $('Separar anexos').all().length;
const conta = (d) => itens.filter((i) => i.desfecho === d).length;
const resumo = {
  total: esperados,
  aceitos: conta('aceito'),
  sem_arquivo: conta('registrado_sem_arquivo'),
  excecoes: conta('excecao_aberta'),
  reentregar: conta('reentregar'),
};
const finais = resumo.aceitos + resumo.sem_arquivo + resumo.excecoes;
const confirmar = itens.length === esperados && finais === esperados;
// §3.7 "depois, exceção; nunca laço infinito": falha temporária que persiste (PCPR fora do ar,
// 5xx, 423, credencial inválida) numa mensagem recebida pelo canal há mais de cfg_fila_parada_s
// → exceção fila_parada (chave e corpo estáveis por mensagem) E continua 503: o canal segue
// reentregando até o próprio limite e o arquivo não se perde; a pessoa já foi avisada.
const msg = $('Separar anexos').first().json;
const idade_s = (Date.now() - Date.parse(String(msg.recebido_em || ''))) / 1000;
const limite_s = Number($('Configuração').first().json.cfg_fila_parada_s);
return [{ json: { ...resumo, confirmar, canal: msg.canal, mensagem_id: msg.mensagem_id,
  fila_parada: !confirmar && Number.isFinite(idade_s) && idade_s > limite_s } }];
"""


def _regra_campo(wid: str, campo: str, valor: str) -> dict:
    return {
        "conditions": {
            "options": {
                "caseSensitive": True,
                "leftValue": "",
                "typeValidation": "strict",
                "version": 2,
            },
            "conditions": [
                {
                    "id": _uid(wid, campo, valor),
                    "leftValue": f"={{{{ $json.{campo} }}}}",
                    "rightValue": valor,
                    "operator": {"type": "string", "operation": "equals"},
                }
            ],
            "combinator": "and",
        },
        "renameOutput": True,
        "outputKey": valor,
    }


def w4() -> dict:
    """Recebimento de arquivo: um anexo por vez (Loop Over Items); cada anexo termina num
    desfecho FINAL (aceito, registrado sem arquivo, exceção) ou em 'reentregar'. Só responde
    ao canal no fim — 200 se todos são finais, 503 se algum deve ser reentregue."""
    f = Fluxo(W4)
    cfg = "$('Configuração').first().json"
    ctx = "$('Anexo atual').first().json"
    f.no(
        "Webhook do canal",
        "n8n-nodes-base.webhook",
        2.1,
        {
            "httpMethod": "POST",
            "path": "canal-recebimento",
            "authentication": "headerAuth",
            # responde só no fim (nó Responder), depois do PCPR — nunca ao receber (C9)
            "responseMode": "responseNode",
            "options": {},
        },
        (0, 300),
        webhookId=_uid(W4, "webhook"),
        credentials={"httpHeaderAuth": CRED_CANAL_WEBHOOK},
    )
    definir(
        f,
        "Configuração",
        [
            ("cfg_pcpr", PCPR_PADRAO, "string"),
            ("cfg_canal", CANAL_PADRAO, "string"),
            ("cfg_limite_bytes", LIMITE_ARQUIVO_BYTES, "number"),
            ("cfg_fila_parada_s", FILA_PARADA_APOS_S, "number"),
        ],
        (220, 300),
        manter=True,
    )
    codigo(f, "Separar anexos", JS_SEPARAR_ANEXOS, (440, 300))
    f.no(
        "Cada anexo",
        "n8n-nodes-base.splitInBatches",
        3,
        {"batchSize": 1, "options": {}},
        (660, 300),
    )
    nada(f, "Anexo atual", (880, 400))
    se(f, "Baixar?", "={{ $json.acao === 'baixar' }}", (1100, 400))
    # Sem retentativa interna: a reentrega do canal é a retentativa (o arquivo continua no canal
    # até um 2xx). Falha vai para a saída de erro e é classificada.
    http(
        f,
        "Baixar arquivo",
        "GET",
        f"={{{{ {cfg}.cfg_canal }}}}/arquivos/{{{{ $json.arquivo_id }}}}",
        (1320, 200),
        cred=CRED_CANAL_API,
        saida_erro=True,
        extra_params={
            "options": {
                "timeout": 30000,
                "response": {
                    "response": {"responseFormat": "file", "outputPropertyName": "arquivo"}
                },
            }
        },
    )
    codigo(f, "Classificar download", JS_CLASSIFICAR_DOWNLOAD_W4, (1540, 360))
    f.no(
        "Calcular SHA-256",
        "n8n-nodes-base.crypto",
        2,
        {
            "action": "hash",
            "type": "SHA256",
            "binaryData": True,
            "binaryPropertyName": "arquivo",
            "dataPropertyName": "sha256",
            "encoding": "hex",
        },
        (1540, 100),
    )
    # O nó Crypto v2 DESCARTA o binário que acabou de resumir (CryptoV2.node.js: só repassa
    # `item.binary` quando não processou binário). Reanexa o arquivo baixado.
    codigo(
        f,
        "Reanexar arquivo",
        f"return [{{ json: {{ ...{ctx}, sha256: $json.sha256 }}, "
        "binary: $('Baixar arquivo').first().binary }];",
        (1760, 100),
    )
    # resposta completa como dado (neverError): o status decide o passo; rede → saída de erro
    http(
        f,
        "Entregar ao PCPR",
        "POST",
        f"={{{{ {cfg}.cfg_pcpr }}}}/recebimentos",
        (1980, 100),
        timeout=60000,
        completo=True,
        saida_erro=True,
        cabecalhos=[
            (
                "Idempotency-Key",
                chave_recebimento_js("$json.canal", "$json.mensagem_id", "$json.anexo_indice"),
            ),
        ],
        extra_params={
            "sendBody": True,
            "contentType": "multipart-form-data",
            "bodyParameters": {
                "parameters": [
                    {
                        "parameterType": "formBinaryData",
                        "name": "arquivo",
                        "inputDataFieldName": "arquivo",
                    },
                    {"parameterType": "formData", "name": "canal", "value": "={{ $json.canal }}"},
                    {
                        "parameterType": "formData",
                        "name": "mensagem_id_canal",
                        "value": "={{ $json.mensagem_id }}",
                    },
                    {
                        "parameterType": "formData",
                        "name": "anexo_indice",
                        "value": "={{ $json.anexo_indice }}",
                    },
                    {
                        "parameterType": "formData",
                        "name": "total_anexos",
                        "value": "={{ $json.total_anexos }}",
                    },
                    {
                        "parameterType": "formData",
                        "name": "nome_arquivo",
                        "value": "={{ $json.nome_arquivo }}",
                    },
                    {
                        "parameterType": "formData",
                        "name": "remetente",
                        "value": "={{ $json.remetente }}",
                    },
                    {
                        "parameterType": "formData",
                        "name": "recebido_em",
                        "value": "={{ $json.recebido_em }}",
                    },
                    {"parameterType": "formData", "name": "sha256", "value": "={{ $json.sha256 }}"},
                    {
                        "parameterType": "formData",
                        "name": "em_resposta_a_comunicacao",
                        "value": "={{ $json.em_resposta_a_comunicacao }}",
                    },
                ]
            },
        },
    )
    codigo(
        f,
        "Classificar entrega",
        JS_CLASSIFICAR_PCPR_W4.replace("__OPERACAO__", "recebimento"),
        (2200, 100),
    )
    # Sem bytes (sem anexo, acima do limite, anexo que não existe mais): registro no PCPR, que
    # orienta o remetente (contrato /recebimentos/sem-arquivo; mesma chave de idempotência).
    nada(f, "Pedido sem arquivo", (1100, 600))
    http(
        f,
        "Registrar sem arquivo",
        "POST",
        f"={{{{ {cfg}.cfg_pcpr }}}}/recebimentos/sem-arquivo",
        (1320, 640),
        completo=True,
        saida_erro=True,
        cabecalhos=[
            (
                "Idempotency-Key",
                chave_recebimento_js(f"{ctx}.canal", f"{ctx}.mensagem_id", f"{ctx}.anexo_indice"),
            ),
        ],
        corpo_json=f"={{{{ JSON.stringify({{ canal: {ctx}.canal, "
        f"mensagem_id_canal: {ctx}.mensagem_id, anexo_indice: {ctx}.anexo_indice, "
        f"total_anexos: {ctx}.total_anexos, remetente: {ctx}.remetente, "
        f"recebido_em: {ctx}.recebido_em, nome_arquivo: {ctx}.nome_arquivo || undefined, "
        f"tamanho: {ctx}.tamanho || undefined, motivo: $json.motivo }}) }}}}",
    )
    codigo(
        f,
        "Classificar registro sem arquivo",
        JS_CLASSIFICAR_PCPR_W4.replace("__OPERACAO__", "sem_arquivo"),
        (1540, 600),
    )
    f.no(
        "Próximo passo",
        "n8n-nodes-base.switch",
        3.2,
        {
            "rules": {
                "values": [
                    _regra_campo(W4, "passo", "fim"),
                    _regra_campo(W4, "passo", "sem_arquivo"),
                    _regra_campo(W4, "passo", "excecao"),
                ]
            },
            "options": {"fallbackOutput": "extra", "renameFallbackOutput": "inesperado"},
        },
        (2420, 400),
    )
    # Recusa permanente: exceção humana com chave estável (reentrega do canal → mesma exceção) e
    # resposta final ao canal. Repetir este POST é seguro (Idempotency-Key estável).
    http(
        f,
        "Abrir exceção (recusa permanente)",
        "POST",
        f"={{{{ {cfg}.cfg_pcpr }}}}/excecoes",
        (2640, 600),
        tentativas=3,
        espera_ms=1000,
        saida_erro=True,
        cabecalhos=[
            (
                "Idempotency-Key",
                chave_limitada("excecao:recebimento-canais:", "$json.chave_excecao"),
            )
        ],
        # corpo idêntico em toda reentrega da MESMA recusa: sem id da execução nem texto livre do
        # PCPR (mesma chave com outro corpo = 422 "chave reutilizada" → 503 em laço; T19a e T19f)
        corpo_json="={{ JSON.stringify({ fluxo: 'recebimento-canais', "
        "correlacao_id: 'recebimento:' + $json.canal + ':' + $json.mensagem_id, "
        "motivo: $json.motivo_excecao, detalhe: $json.detalhe }) }}",
    )
    codigo(
        f,
        "Exceção aberta",
        f"return [{{ json: {{ ...{ctx}, desfecho: 'excecao_aberta', "
        "excecao_id: $json.id ?? null } }];",
        (2860, 520),
    )
    codigo(
        f,
        "Exceção não aberta",
        f"return [{{ json: {{ ...{ctx}, desfecho: 'reentregar', "
        "ultima_resposta: 'exceção não registrada no PCPR' } }];",
        (2860, 700),
    )
    codigo(
        f,
        "Passo inesperado",
        f"return [{{ json: {{ ...{ctx}, desfecho: 'reentregar', "
        "ultima_resposta: 'passo inesperado: ' + String($json.passo) } }];",
        (2640, 800),
    )
    codigo(f, "Decidir resposta", JS_DECIDIR_RESPOSTA_W4, (880, 100))
    se(f, "Confirmar ao canal?", "={{ $json.confirmar === true }}", (1100, 0))
    f.no(
        "Responder 200",
        "n8n-nodes-base.respondToWebhook",
        1.1,
        {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify({ total: $json.total, aceitos: $json.aceitos, "
            "sem_arquivo: $json.sem_arquivo, excecoes: $json.excecoes }) }}",
            "options": {"responseCode": 200},
        },
        (1320, -100),
    )
    f.no(
        "Responder 503 (reentregar)",
        "n8n-nodes-base.respondToWebhook",
        1.1,
        {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify({ erro: 'recebimento_nao_confirmado', "
            "total: $('Decidir resposta').first().json.total, "
            "aceitos: $('Decidir resposta').first().json.aceitos, "
            "sem_arquivo: $('Decidir resposta').first().json.sem_arquivo, "
            "excecoes: $('Decidir resposta').first().json.excecoes, "
            "reentregar: $('Decidir resposta').first().json.reentregar, "
            "fila_parada: $('Decidir resposta').first().json.fila_parada }) }}",
            "options": {"responseCode": 503},
        },
        (1760, 60),
    )
    se(f, "Fila parada?", "={{ $json.fila_parada === true }}", (1320, 160))
    # Exceção humana (§3.7) sem largar a mensagem: chave e corpo estáveis por mensagem (cada
    # reentrega repete sem efeito); se nem o /excecoes responder, a resposta continua 503.
    http(
        f,
        "Exceção: fila parada",
        "POST",
        f"={{{{ {cfg}.cfg_pcpr }}}}/excecoes",
        (1540, 260),
        saida_erro=True,
        cabecalhos=[
            (
                "Idempotency-Key",
                chave_limitada(
                    "excecao:recebimento-canais:",
                    "'receb:' + $json.canal + ':' + $json.mensagem_id + ':fila_parada'",
                ),
            ),
        ],
        corpo_json="={{ JSON.stringify({ fluxo: 'recebimento-canais', "
        "correlacao_id: 'recebimento:' + $json.canal + ':' + $json.mensagem_id, "
        # corpo = função só da chave: sem o limite configurável (cfg_fila_parada_s), que mudaria o
        # corpo numa reentrega depois de reconfigurar (422 "chave reutilizada" → 503 em laço)
        "motivo: 'fila_parada', detalhe: 'O PCPR não confirma o recebimento desta mensagem há mais "
        "que o prazo configurado (falha temporária persistente: PCPR fora do ar, automação "
        "desligada ou credencial). O canal continua reentregando até o próprio limite; conferir "
        "a mensagem na caixa.' }) }}",
    )
    for a, c in [
        ("Webhook do canal", "Configuração"),
        ("Configuração", "Separar anexos"),
        ("Separar anexos", "Cada anexo"),
        ("Anexo atual", "Baixar?"),
        ("Calcular SHA-256", "Reanexar arquivo"),
        ("Reanexar arquivo", "Entregar ao PCPR"),
        ("Classificar entrega", "Próximo passo"),
        ("Classificar download", "Próximo passo"),
        ("Pedido sem arquivo", "Registrar sem arquivo"),
        ("Registrar sem arquivo", "Classificar registro sem arquivo"),
        ("Classificar registro sem arquivo", "Próximo passo"),
        ("Decidir resposta", "Confirmar ao canal?"),
    ]:
        f.liga(a, c)
    f.liga("Cada anexo", "Decidir resposta", 0)  # done: todos os desfechos
    f.liga("Cada anexo", "Anexo atual", 1)  # loop: um anexo
    f.liga("Baixar?", "Baixar arquivo", 0)
    f.liga("Baixar?", "Pedido sem arquivo", 1)
    f.liga("Baixar arquivo", "Calcular SHA-256", 0)
    f.liga("Baixar arquivo", "Classificar download", 1)
    f.liga("Entregar ao PCPR", "Classificar entrega", 0)
    f.liga("Entregar ao PCPR", "Classificar entrega", 1)  # rede também é classificada
    f.liga("Registrar sem arquivo", "Classificar registro sem arquivo", 1)
    f.liga("Próximo passo", "Cada anexo", 0)  # fim: desfecho já decidido
    f.liga("Próximo passo", "Pedido sem arquivo", 1)
    f.liga("Próximo passo", "Abrir exceção (recusa permanente)", 2)
    f.liga("Próximo passo", "Passo inesperado", 3)
    f.liga("Abrir exceção (recusa permanente)", "Exceção aberta", 0)
    f.liga("Abrir exceção (recusa permanente)", "Exceção não aberta", 1)
    for fim in ("Exceção aberta", "Exceção não aberta", "Passo inesperado"):
        f.liga(fim, "Cada anexo")
    f.liga("Confirmar ao canal?", "Responder 200", 0)
    f.liga("Confirmar ao canal?", "Fila parada?", 1)
    f.liga("Fila parada?", "Exceção: fila parada", 0)
    f.liga("Fila parada?", "Responder 503 (reentregar)", 1)
    f.liga("Exceção: fila parada", "Responder 503 (reentregar)", 0)
    f.liga("Exceção: fila parada", "Responder 503 (reentregar)", 1)
    # arquivo e remetente: nada fica guardado no n8n
    return f.json({"errorWorkflow": W5, **SEM_RETENCAO})


# ------------------------------------------------------------------ W5


def w5() -> dict:
    f = Fluxo(W5)
    f.no("Quando um fluxo falhar", "n8n-nodes-base.errorTrigger", 1, {}, (0, 300))
    definir(f, "Configuração", [("cfg_pcpr", PCPR_PADRAO, "string")], (220, 300), manter=True)
    http(
        f,
        "Abrir exceção",
        "POST",
        "={{ $json.cfg_pcpr }}/excecoes",
        (440, 300),
        tentativas=3,
        espera_ms=2000,
        cabecalhos=[
            (
                "Idempotency-Key",
                "=erro-n8n:{{ $json.workflow.id }}:{{ $json.execution.id ?? $now.toMillis() }}",
            ),
        ],
        corpo_json="={{ JSON.stringify({ fluxo: 'n8n:' + $json.workflow.name, "
        "correlacao_id: 'n8n:execucao:' + ($json.execution.id ?? 'sem-id'), motivo: 'outro', "
        # mensagem de erro pode citar corpo de resposta (ex.: token de reserva): sequências longas
        # de caracteres de token são mascaradas antes de sair do n8n (o PCPR mascara de novo)
        "detalhe: (String(($json.execution.error || {}).message || 'erro sem mensagem')"
        ".replace(/[A-Za-z0-9_-]{24,}/g, '***') + "
        "' (nó: ' + ($json.execution.lastNodeExecuted || '?') + ')').slice(0, 2000), "
        "execucao_orquestrador: String($json.execution.id ?? '') }) }}",
    )
    f.liga("Quando um fluxo falhar", "Configuração")
    f.liga("Configuração", "Abrir exceção")
    # O Error Trigger recebe a mensagem de erro e dados da execução que falhou (W2/W4: destino,
    # token de reserva): a execução do W5 também não fica guardada (T13 achou o token aqui).
    return f.json(SEM_RETENCAO)


# ------------------------------------------------------------------ W6 · WhatsApp oficial: envio

CTX6 = "$('Quando chamado pelo W2').first().json"
CFG6 = "$('Configuração').first().json"

JS_DECIDIR_FORMA = r"""
// O PCPR diz a forma PEDIDA e a janela de 24 h que ELE conhece (última mensagem do servidor).
// Fora da janela só sai modelo APROVADO (utility); texto livre/documento ali daria o erro 131047.
// Margem: janela que fecha em menos de cfg_margem_janela_s conta como fechada.
const ctx = $('Quando chamado pelo W2').first().json;
const cfg = $('Configuração').first().json;
const wa = (ctx.mensagem || {}).whatsapp || {};
const margemMs = Number(cfg.cfg_margem_janela_s || 600) * 1000;
const ate = wa.janela_aberta_ate ? Date.parse(wa.janela_aberta_ate) : 0;
const janelaAberta = ate - Date.now() > margemMs;
const pedida = wa.forma || 'modelo';
const temModelo = Boolean(wa.modelo && wa.modelo.nome);
const temAnexo = Boolean(((ctx.anexos || [])[0] || {}).url_assinada);
let forma = 'impossivel';
if (pedida === 'texto' && janelaAberta) forma = 'texto';
else if (pedida === 'documento' && janelaAberta && temAnexo) forma = 'documento';
else if (temModelo) forma = 'modelo';
return [{ json: { forma, pedida, janela_aberta: janelaAberta, tem_modelo: temModelo } }];
"""

JS_MONTAR_MODELO = r"""
// Modelo (template) utility aprovado; variáveis já vêm do PCPR, sem CPF/RG/telefone/valores.
// biz_opaque_callback_data volta nos webhooks de status → o W8 acha a comunicação sem consulta.
const ctx = $('Quando chamado pelo W2').first().json;
const m = ctx.mensagem.whatsapp.modelo;
return [{ json: { forma_enviada: 'modelo', payload: {
  messaging_product: 'whatsapp', recipient_type: 'individual',
  to: String(ctx.destino || '').replace(/[^0-9]/g, ''), type: 'template',
  template: { name: m.nome, language: { code: m.idioma || 'pt_BR' }, components: [{
    type: 'body', parameters: (m.parametros || []).map((t) => ({ type: 'text', text: String(t) })),
  }] },
  biz_opaque_callback_data: 'com:' + ctx.comunicacao_id,
} } }];
"""

JS_MONTAR_TEXTO = r"""
const ctx = $('Quando chamado pelo W2').first().json;
const wa = ctx.mensagem.whatsapp;
return [{ json: { forma_enviada: 'texto', payload: {
  messaging_product: 'whatsapp', recipient_type: 'individual',
  to: String(ctx.destino || '').replace(/[^0-9]/g, ''), type: 'text',
  text: { body: String(wa.texto || ''), preview_url: false },
  biz_opaque_callback_data: 'com:' + ctx.comunicacao_id,
} } }];
"""

JS_MONTAR_DOCUMENTO = r"""
// Documento por ID de mídia (upload prévio), não por link público.
const ctx = $('Quando chamado pelo W2').first().json;
const anexo = ctx.anexos[0];
return [{ json: { forma_enviada: 'documento', media_id: $input.first().json.id, payload: {
  messaging_product: 'whatsapp', recipient_type: 'individual',
  to: String(ctx.destino || '').replace(/[^0-9]/g, ''), type: 'document',
  document: { id: String($input.first().json.id), filename: anexo.nome,
    caption: String(ctx.mensagem.whatsapp.legenda || '').slice(0, 1024) },
  biz_opaque_callback_data: 'com:' + ctx.comunicacao_id,
} } }];
"""

JS_CONFERIR_DOCUMENTO = r"""
// O Crypto v2 descarta o binário que resume: confere o SHA-256 do PCPR e reanexa o arquivo.
const ctx = $('Quando chamado pelo W2').first().json;
const esperado = String(((ctx.anexos || [])[0] || {}).sha256 || '').toLowerCase();
const calc = String($input.first().json.sha256_calc || '').toLowerCase();
return [{ json: { ok: calc.length === 64 && calc === esperado },
  binary: $('Baixar documento do PCPR').first().binary }];
"""

JS_CLASSIFICAR_WA = r"""
// Resposta da Graph API → resultado para o PCPR. Sem retentativa automática do POST /messages:
// a Cloud API não tem chave de idempotência, então repetir após tempo esgotado duplicaria.
const PERMITE_FALLBACK = %s;
const r = $input.first().json;
const ctx = $('Quando chamado pelo W2').first().json;
const forma = PERMITE_FALLBACK ? $('Decidir forma').first().json.forma : 'modelo';
const temModelo = Boolean((((ctx.mensagem || {}).whatsapp || {}).modelo || {}).nome);
const sc = Number(r.statusCode || 0);
const corpo = (r.body && typeof r.body === 'object') ? r.body : {};
const e = corpo.error || {};
const codigo = Number(e.code || 0);
const wamid = ((corpo.messages || [])[0] || {}).id || '';
const descr = ('HTTP ' + sc + (codigo ? ' código ' + codigo : '') +
  (e.message ? ': ' + String(e.message) : '')).slice(0, 300);
if (sc === 200 && wamid) {
  return [{ json: { fallback: false, resultado: 'enviada', provedor_mensagem_id: wamid,
    erro: '', motivo_excecao: '' } }];
}
// 131047 (fora da janela) numa mensagem livre: troca UMA vez por modelo; nunca repete o livre.
if (codigo === 131047 && PERMITE_FALLBACK && forma !== 'modelo' && temModelo) {
  return [{ json: { fallback: true, erro_primeira_tentativa: descr } }];
}
// Sem erro estruturado da Graph API (ex.: 502/504 de um proxy, 2xx sem wamid) não se sabe se a
// Meta aceitou → resultado desconhecido + exceção. Nunca falha_temporaria aqui: o PCPR reagenda
// a temporária e reenviaria às cegas (mesma regra do W2; C5/C6 do PR #23).
const erroGraph = Boolean(e.code);
if (!erroGraph && sc !== 429) {
  return [{ json: { fallback: false, resultado: 'resultado_desconhecido', provedor_mensagem_id: '',
    erro: ('resposta ambígua da Graph API: ' + descr).slice(0, 300),
    motivo_excecao: 'resultado_desconhecido' } }];
}
// Temporária (o PCPR reagenda e o W6 REENVIA) só com prova de que a Meta NÃO aceitou: limite de
// taxa (HTTP 429 ou códigos de throttling 4, 80007, 130429, 131048, 131056), que a Graph API
// aplica antes de aceitar a mensagem. 5xx com erro genérico (1, 2, 131000, 131016...) não prova
// nada: pode ter falhado depois do aceite → resultado desconhecido + exceção, sem reenvio
// (2ª verificação do PR #23; a mesma regra do W2/C5).
const LIMITE_DE_TAXA = [4, 80007, 130429, 131048, 131056];
if (sc >= 500 && !LIMITE_DE_TAXA.includes(codigo)) {
  return [{ json: { fallback: false, resultado: 'resultado_desconhecido', provedor_mensagem_id: '',
    erro: ('erro do servidor da Graph API, aceite incerto: ' + descr).slice(0, 300),
    motivo_excecao: 'resultado_desconhecido' } }];
}
const temporario = sc === 429 || LIMITE_DE_TAXA.includes(codigo);
const motivo = (codigo === 190 || sc === 401) ? 'canal_indisponivel' : 'outro';
return [{ json: { fallback: false,
  resultado: temporario ? 'falha_temporaria' : 'falha_definitiva', provedor_mensagem_id: '',
  erro: descr, motivo_excecao: temporario ? '' : motivo } }];
"""

JS_REDE_WA = r"""
// Tempo esgotado/conexão caída: não se sabe se a Meta aceitou → resultado desconhecido + exceção
// (nunca reenviar às cegas).
const e = $input.first().json.error || $input.first().json || {};
return [{ json: { fallback: false, resultado: 'resultado_desconhecido', provedor_mensagem_id: '',
  erro: String(e.message || 'erro de rede').slice(0, 300),
  motivo_excecao: 'resultado_desconhecido' } }];
"""

JS_IMPOSSIVEL = r"""
const d = $('Decidir forma').first().json;
return [{ json: { fallback: false, resultado: 'falha_definitiva', provedor_mensagem_id: '',
  erro: "não enviado: forma pedida '" + d.pedida + "' fora da janela de 24 h e sem modelo " +
    'aprovado (evita o erro 131047)', motivo_excecao: 'outro' } }];
"""

JS_DOC_DIVERGENTE = r"""
return [{ json: { fallback: false, resultado: 'falha_definitiva', provedor_mensagem_id: '',
  erro: 'SHA-256 do anexo baixado do PCPR não confere: documento não enviado',
  motivo_excecao: 'outro' } }];
"""


def _http_whatsapp(f: Fluxo, nome: str, pos: tuple[int, int]) -> str:
    """POST /messages: resposta completa sem lançar erro (4xx/5xx viram dado para classificar);
    só falha de rede/tempo esgotado sai pela saída de erro."""
    return http(
        f,
        nome,
        "POST",
        f"={{{{ {CFG6}.cfg_graph }}}}/{{{{ {CFG6}.cfg_numero_id }}}}/messages",
        pos,
        cred=CRED_WA_TOKEN,
        corpo_json="={{ JSON.stringify($json.payload) }}",
        completo=True,
        timeout=30000,
        saida_erro=True,
    )


def w6() -> dict:
    f = Fluxo(W6)
    f.no(
        "Quando chamado pelo W2",
        "n8n-nodes-base.executeWorkflowTrigger",
        1.1,
        {"inputSource": "passthrough"},
        (0, 300),
    )
    definir(
        f,
        "Configuração",
        [
            ("cfg_graph", GRAPH_PADRAO, "string"),
            ("cfg_numero_id", NUMERO_ID_PADRAO, "string"),
            ("cfg_margem_janela_s", 600, "number"),
        ],
        (220, 300),
    )
    codigo(f, "Decidir forma", JS_DECIDIR_FORMA, (440, 300))

    def regra(valor: str) -> dict:
        return {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 2,
                },
                "conditions": [
                    {
                        "id": _uid(W6, "forma", valor),
                        "leftValue": "={{ $json.forma }}",
                        "rightValue": valor,
                        "operator": {"type": "string", "operation": "equals"},
                    }
                ],
                "combinator": "and",
            },
            "renameOutput": True,
            "outputKey": valor,
        }

    f.no(
        "Forma de envio",
        "n8n-nodes-base.switch",
        3.2,
        {
            "rules": {"values": [regra("modelo"), regra("documento"), regra("texto")]},
            "options": {"fallbackOutput": "extra", "renameFallbackOutput": "impossível"},
        },
        (660, 300),
    )
    codigo(f, "Montar modelo", JS_MONTAR_MODELO, (880, 60))
    http(
        f,
        "Baixar documento do PCPR",
        "GET",
        f"={{{{ {CTX6}.anexos[0].url_assinada }}}}",
        (880, 260),
        cred=None,
        tentativas=3,
        espera_ms=1000,
        extra_params={
            "options": {
                "timeout": 60000,
                "response": {
                    "response": {"responseFormat": "file", "outputPropertyName": "documento"}
                },
            }
        },
    )
    f.no(
        "SHA-256 do documento",
        "n8n-nodes-base.crypto",
        2,
        {
            "action": "hash",
            "type": "SHA256",
            "binaryData": True,
            "binaryPropertyName": "documento",
            "dataPropertyName": "sha256_calc",
            "encoding": "hex",
        },
        (1100, 260),
    )
    codigo(f, "Conferir documento", JS_CONFERIR_DOCUMENTO, (1320, 260))
    se(f, "Documento íntegro?", "={{ $json.ok === true }}", (1540, 260))
    http(
        f,
        "Enviar mídia ao WhatsApp",
        "POST",
        f"={{{{ {CFG6}.cfg_graph }}}}/{{{{ {CFG6}.cfg_numero_id }}}}/media",
        (1760, 200),
        cred=CRED_WA_TOKEN,
        tentativas=3,  # upload é seguro de repetir (no pior caso, uma mídia órfã que expira)
        espera_ms=1000,
        extra_params={
            "options": {"timeout": 120000},
            "sendBody": True,
            "contentType": "multipart-form-data",
            "bodyParameters": {
                "parameters": [
                    {"parameterType": "formData", "name": "messaging_product", "value": "whatsapp"},
                    {
                        "parameterType": "formData",
                        "name": "type",
                        "value": "={{ $binary.documento.mimeType || 'application/pdf' }}",
                    },
                    {
                        "parameterType": "formBinaryData",
                        "name": "file",
                        "inputDataFieldName": "documento",
                    },
                ]
            },
        },
    )
    codigo(f, "Montar documento", JS_MONTAR_DOCUMENTO, (1980, 200))
    codigo(f, "Documento divergente", JS_DOC_DIVERGENTE, (1760, 380))
    codigo(f, "Montar texto", JS_MONTAR_TEXTO, (880, 460))
    codigo(f, "Sem forma possível", JS_IMPOSSIVEL, (880, 620))
    _http_whatsapp(f, "Enviar ao WhatsApp", (2200, 300))
    codigo(f, "Classificar resposta", JS_CLASSIFICAR_WA % "true", (2420, 240))
    codigo(f, "Falha de rede", JS_REDE_WA, (2420, 460))
    se(f, "Trocar por modelo (131047)?", "={{ $json.fallback === true }}", (2640, 240))
    codigo(f, "Montar modelo (após 131047)", JS_MONTAR_MODELO, (2860, 100))
    _http_whatsapp(f, "Enviar modelo (após 131047)", (3080, 100))
    codigo(f, "Classificar resposta (após 131047)", JS_CLASSIFICAR_WA % "false", (3300, 100))
    definir(
        f,
        "Normalizar resultado",
        [
            ("resultado", "={{ $json.resultado }}", "string"),
            ("provedor_mensagem_id", "={{ $json.provedor_mensagem_id || '' }}", "string"),
            ("erro", "={{ $json.erro || '' }}", "string"),
            ("motivo_excecao", "={{ $json.motivo_excecao || '' }}", "string"),
        ],
        (3520, 300),
    )
    http(
        f,
        "Registrar resultado",
        "POST",
        f"={{{{ {CTX6}.cfg_pcpr }}}}/comunicacoes/{{{{ {CTX6}.comunicacao_id }}}}/resultado",
        (3740, 300),
        tentativas=3,
        espera_ms=1000,
        cabecalhos=[
            (
                "Idempotency-Key",
                f"=resultado:{{{{ {CTX6}.comunicacao_id }}}}:{{{{ {CTX6}.reserva_token }}}}",
            ),
            ("X-PCPR-Correlacao", f"={{{{ {CTX6}.correlacao_id }}}}"),
        ],
        corpo_json=f"={{{{ JSON.stringify({{ reserva_token: {CTX6}.reserva_token, "
        "resultado: $json.resultado, provedor: 'whatsapp_cloud', "
        "provedor_mensagem_id: $json.provedor_mensagem_id || undefined, "
        "erro: $json.erro || undefined }) }}",
    )
    se(
        f,
        "Abrir exceção?",
        "={{ Boolean($('Normalizar resultado').first().json.motivo_excecao) }}",
        (3960, 300),
    )
    nada(f, "Fim: registrado", (4180, 200))
    http(
        f,
        "Abrir exceção",
        "POST",
        f"={{{{ {CTX6}.cfg_pcpr }}}}/excecoes",
        (4180, 400),
        tentativas=3,
        espera_ms=1000,
        cabecalhos=[
            (
                "Idempotency-Key",
                f"=excecao:com{{{{ {CTX6}.comunicacao_id }}}}:{{{{ {CTX6}.reserva_token }}}}",
            ),
        ],
        corpo_json="={{ JSON.stringify({ fluxo: 'whatsapp', "
        f"correlacao_id: {CTX6}.correlacao_id, "
        "motivo: $('Normalizar resultado').first().json.motivo_excecao, "
        f"detalhe: 'comunicacao ' + {CTX6}.comunicacao_id + ': ' + "
        "$('Normalizar resultado').first().json.erro, "
        "execucao_orquestrador: String($execution.id), "
        f"recurso: {{ tipo: 'comunicacao', id: {CTX6}.comunicacao_id }} }}) }}}}",
    )
    for a, b in [
        ("Quando chamado pelo W2", "Configuração"),
        ("Configuração", "Decidir forma"),
        ("Decidir forma", "Forma de envio"),
        ("Montar modelo", "Enviar ao WhatsApp"),
        ("Baixar documento do PCPR", "SHA-256 do documento"),
        ("SHA-256 do documento", "Conferir documento"),
        ("Conferir documento", "Documento íntegro?"),
        ("Enviar mídia ao WhatsApp", "Montar documento"),
        ("Montar documento", "Enviar ao WhatsApp"),
        ("Documento divergente", "Normalizar resultado"),
        ("Montar texto", "Enviar ao WhatsApp"),
        ("Sem forma possível", "Normalizar resultado"),
        ("Classificar resposta", "Trocar por modelo (131047)?"),
        ("Falha de rede", "Normalizar resultado"),
        ("Montar modelo (após 131047)", "Enviar modelo (após 131047)"),
        ("Classificar resposta (após 131047)", "Normalizar resultado"),
        ("Normalizar resultado", "Registrar resultado"),
        ("Registrar resultado", "Abrir exceção?"),
    ]:
        f.liga(a, b)
    f.liga("Forma de envio", "Montar modelo", 0)
    f.liga("Forma de envio", "Baixar documento do PCPR", 1)
    f.liga("Forma de envio", "Montar texto", 2)
    f.liga("Forma de envio", "Sem forma possível", 3)
    f.liga("Documento íntegro?", "Enviar mídia ao WhatsApp", 0)
    f.liga("Documento íntegro?", "Documento divergente", 1)
    f.liga("Enviar ao WhatsApp", "Classificar resposta", 0)
    f.liga("Enviar ao WhatsApp", "Falha de rede", 1)
    f.liga("Trocar por modelo (131047)?", "Montar modelo (após 131047)", 0)
    f.liga("Trocar por modelo (131047)?", "Normalizar resultado", 1)
    f.liga("Enviar modelo (após 131047)", "Classificar resposta (após 131047)", 0)
    f.liga("Enviar modelo (após 131047)", "Falha de rede", 1)
    f.liga("Abrir exceção?", "Abrir exceção", 0)
    f.liga("Abrir exceção?", "Fim: registrado", 1)
    # destino, link-credencial, token de reserva e documento: nada fica guardado no n8n
    return f.json({"errorWorkflow": W5, "callerPolicy": "workflowsFromSameOwner", **SEM_RETENCAO})


# ------------------------------------------------------------------ W7 · webhook WhatsApp (V1)

JS_CONFERIR_VERIFICACAO = r"""
// Verificação GET da Meta: hub.mode=subscribe e hub.verify_token igual ao esperado (derivado da
// credencial pelo nó anterior), comparado em tempo constante; o desafio só é ecoado se for curto
// e alfanumérico (não reflete conteúdo arbitrário).
const q = $('Webhook WhatsApp').first().json.query || {};
const pega = (k) => String(q['hub.' + k] ?? ((q.hub || {})[k]) ?? '');
const modo = pega('mode');
const recebido = pega('verify_token');
const desafio = pega('challenge');
const esperado = String($input.first().json.esperado || '');
let dif = (recebido.length === esperado.length && esperado.length === 64) ? 0 : 1;
for (let i = 0; i < Math.min(recebido.length, esperado.length); i++) {
  dif |= recebido.charCodeAt(i) ^ esperado.charCodeAt(i);
}
const valido = modo === 'subscribe' && dif === 0 && /^[A-Za-z0-9_-]{1,64}$/.test(desafio);
return [{ json: { valido, desafio: valido ? desafio : '' } }];
"""

JS_VALIDAR_HUB = r"""
// X-Hub-Signature-256 = 'sha256=' + HMAC-SHA256(App Secret, corpo BRUTO). O HMAC foi calculado
// pelo nó Crypto sobre o binário do Raw Body (bytes exatos; nada é re-serializado).
const w = $('Webhook WhatsApp').first().json;
const recebida = String((w.headers || {})['x-hub-signature-256'] || '');
const esperada = 'sha256=' + String($input.first().json.hmac_calculado || '');
let dif = (recebida.length === esperada.length && esperada.length === 71) ? 0 : 1;
for (let i = 0; i < Math.min(recebida.length, esperada.length); i++) {
  dif |= recebida.charCodeAt(i) ^ esperada.charCodeAt(i);
}
const objeto = (w.body || {}).object;
const valido = dif === 0 && objeto === 'whatsapp_business_account';
return [{ json: { valido, motivo: dif !== 0 ? 'assinatura' : (valido ? 'ok' : 'objeto') } }];
"""

JS_SEPARAR_EVENTOS = r"""
// Um POST da Meta pode trazer várias mensagens e status. Um item por evento.
const corpo = $('Webhook WhatsApp').first().json.body || {};
const itens = [];
for (const en of corpo.entry || []) {
  for (const ch of en.changes || []) {
    const v = ch.value || {};
    for (const m of v.messages || []) {
      const tipo = String(m.type || '');
      const midia = (tipo === 'document' || tipo === 'image') ? (m[tipo] || {}) : null;
      const base = {
        wamid: String(m.id || ''),
        remetente: '+' + String(m.from || '').replace(/[^0-9]/g, ''),
        recebido_em: new Date(Number(m.timestamp || 0) * 1000).toISOString(),
        em_resposta_a: String((m.context || {}).id || ''),
      };
      if (midia && midia.id) {
        itens.push({ json: { evento: 'midia', ...base, media_id: String(midia.id),
          sha256_meta: String(midia.sha256 || ''), mime: String(midia.mime_type || ''),
          nome_arquivo: String(midia.filename || (tipo + '.bin')) } });
      } else {
        itens.push({ json: { evento: 'sem_arquivo', ...base, tipo_mensagem: tipo } });
      }
    }
    for (const s of v.statuses || []) itens.push({ json: { evento: 'status', ...s } });
  }
}
if (!itens.length) itens.push({ json: { evento: 'nada' } });
return itens;
"""

JS_CONFERIR_MIDIA = r"""
// SHA-256 do arquivo baixado × o informado pela Meta no webhook (hex ou base64: a doc consultada
// não fixa o formato). O Crypto v2 descarta o binário: reanexa do nó de download que rodou.
const ev = $('Separar eventos').item.json;
const calc = String($json.sha256_calc || '').toLowerCase();
const hexDe = (v) => {
  v = String(v || '').trim();
  if (/^[0-9a-fA-F]{64}$/.test(v)) return v.toLowerCase();
  try { return Buffer.from(v, 'base64').toString('hex'); } catch (e) { return ''; }
};
let binario = null;
try { binario = $('Baixar mídia (nova URL)').item.binary; } catch (e) { binario = null; }
if (!binario) binario = $('Baixar mídia').item.binary;
const confere = calc.length === 64 && calc === hexDe(ev.sha256_meta);
return { json: { ...ev, sha256: calc, confere }, binary: binario };
"""


def _regra_evento(valor: str) -> dict:
    return {
        "conditions": {
            "options": {
                "caseSensitive": True,
                "leftValue": "",
                "typeValidation": "strict",
                "version": 2,
            },
            "conditions": [
                {
                    "id": _uid(W7, "evento", valor),
                    "leftValue": "={{ $json.evento }}",
                    "rightValue": valor,
                    "operator": {"type": "string", "operation": "equals"},
                }
            ],
            "combinator": "and",
        },
        "renameOutput": True,
        "outputKey": valor,
    }


def w7() -> dict:
    f = Fluxo(W7)
    cfg = "$('Configuração').first().json"
    f.no(
        "Webhook WhatsApp",
        "n8n-nodes-base.webhook",
        2.1,
        {
            "multipleMethods": True,
            "httpMethod": ["GET", "POST"],
            "path": "whatsapp",
            "responseMode": "responseNode",
            "options": {"rawBody": True},
        },
        (0, 400),
        webhookId=_uid(W7, "webhook"),
    )
    # ---- GET: verificação do endpoint
    f.no(
        "Calcular verify token esperado",
        "n8n-nodes-base.crypto",
        2,
        {
            "action": "hmac",
            "type": "SHA256",
            "value": VERIFY_TOKEN_MENSAGEM,
            "dataPropertyName": "esperado",
            "encoding": "hex",
        },
        (220, 160),
        credentials={"crypto": CRED_WA_VERIFY},
    )
    codigo(f, "Conferir verificação", JS_CONFERIR_VERIFICACAO, (440, 160))
    se(f, "Verificação válida?", "={{ $json.valido === true }}", (660, 160))
    f.no(
        "Responder desafio",
        "n8n-nodes-base.respondToWebhook",
        1.1,
        {
            "respondWith": "text",
            "responseBody": "={{ $json.desafio }}",
            "options": {
                "responseCode": 200,
                "responseHeaders": {
                    "entries": [{"name": "Content-Type", "value": "text/plain; charset=utf-8"}]
                },
            },
        },
        (880, 80),
    )
    f.no(
        "Responder 403",
        "n8n-nodes-base.respondToWebhook",
        1.1,
        {
            "respondWith": "json",
            "responseBody": '{"erro":"verificacao_recusada"}',
            "options": {"responseCode": 403},
        },
        (880, 240),
    )
    # ---- POST: notificações (mensagens e status) assinadas
    f.no(
        "Calcular assinatura",
        "n8n-nodes-base.crypto",
        2,
        {
            "action": "hmac",
            "type": "SHA256",
            "binaryData": True,
            "binaryPropertyName": "data",
            "dataPropertyName": "hmac_calculado",
            "encoding": "hex",
        },
        (220, 560),
        credentials={"crypto": CRED_WA_APP_SECRET},
    )
    codigo(f, "Validar assinatura", JS_VALIDAR_HUB, (440, 560))
    se(f, "Assinatura válida?", "={{ $json.valido === true }}", (660, 560))
    f.no(
        "Responder 401",
        "n8n-nodes-base.respondToWebhook",
        1.1,
        {
            "respondWith": "json",
            "responseBody": '{"erro":"assinatura_invalida"}',
            "options": {"responseCode": 401},
        },
        (880, 720),
    )
    definir(
        f,
        "Configuração",
        [("cfg_pcpr", PCPR_PADRAO, "string"), ("cfg_graph", GRAPH_PADRAO, "string")],
        (880, 560),
    )
    codigo(f, "Separar eventos", JS_SEPARAR_EVENTOS, (1100, 560))
    f.no(
        "Tipo de evento",
        "n8n-nodes-base.switch",
        3.2,
        {
            "rules": {
                "values": [
                    _regra_evento("midia"),
                    _regra_evento("sem_arquivo"),
                    _regra_evento("status"),
                ]
            },
            "options": {"fallbackOutput": "extra", "renameFallbackOutput": "outros"},
        },
        (1320, 560),
    )
    # mídia em 2 passos, sempre com Bearer: metadados (URL de 5 min) → download
    http(
        f,
        "Obter URL da mídia",
        "GET",
        f"={{{{ {cfg}.cfg_graph }}}}/{{{{ $json.media_id }}}}",
        (1540, 300),
        cred=CRED_WA_TOKEN,
        tentativas=3,
        espera_ms=1000,
        timeout=15000,
    )
    arquivo_completo = {
        "options": {
            "timeout": 120000,
            "response": {
                "response": {
                    "fullResponse": True,
                    "neverError": True,
                    "responseFormat": "file",
                    "outputPropertyName": "arquivo",
                }
            },
        }
    }
    http(
        f,
        "Baixar mídia",
        "GET",
        "={{ $json.url }}",
        (1760, 300),
        cred=CRED_WA_TOKEN,
        extra_params=arquivo_completo,
    )
    se(f, "Download OK?", "={{ $json.statusCode === 200 }}", (1980, 300))
    # URL vencida (5 min) ou recusada → pede URL nova UMA vez; se falhar de novo, o fluxo falha,
    # responde 500 e a Meta reentrega depois (até 7 dias)
    http(
        f,
        "Obter nova URL",
        "GET",
        f"={{{{ {cfg}.cfg_graph }}}}/{{{{ $('Separar eventos').item.json.media_id }}}}",
        (2200, 420),
        cred=CRED_WA_TOKEN,
        tentativas=3,
        espera_ms=1000,
        timeout=15000,
    )
    http(
        f,
        "Baixar mídia (nova URL)",
        "GET",
        "={{ $json.url }}",
        (2420, 420),
        cred=CRED_WA_TOKEN,
        tentativas=2,
        espera_ms=1000,
        extra_params={
            "options": {
                "timeout": 120000,
                "response": {
                    "response": {"responseFormat": "file", "outputPropertyName": "arquivo"}
                },
            }
        },
    )
    f.no(
        "SHA-256 da mídia",
        "n8n-nodes-base.crypto",
        2,
        {
            "action": "hash",
            "type": "SHA256",
            "binaryData": True,
            "binaryPropertyName": "arquivo",
            "dataPropertyName": "sha256_calc",
            "encoding": "hex",
        },
        (2640, 300),
    )
    codigo(f, "Conferir SHA-256", JS_CONFERIR_MIDIA, (2860, 300), por_item=True)
    se(f, "SHA-256 confere?", "={{ $json.confere === true }}", (3080, 300))
    http(
        f,
        "Entregar ao PCPR",
        "POST",
        f"={{{{ {cfg}.cfg_pcpr }}}}/recebimentos",
        (3300, 200),
        # 20 s × 3 tentativas: uma conexão presa (visto 1× no protótipo, Docker Desktop) não
        # pode consumir o tempo inteiro em que a Meta espera a resposta do webhook
        tentativas=3,
        espera_ms=1000,
        timeout=20000,
        cabecalhos=[("Idempotency-Key", chave_recebimento_js("'whatsapp'", "$json.wamid", "0"))],
        extra_params={
            "sendBody": True,
            "contentType": "multipart-form-data",
            "bodyParameters": {
                "parameters": [
                    {
                        "parameterType": "formBinaryData",
                        "name": "arquivo",
                        "inputDataFieldName": "arquivo",
                    },
                    {"parameterType": "formData", "name": "canal", "value": "whatsapp"},
                    {
                        "parameterType": "formData",
                        "name": "mensagem_id_canal",
                        "value": "={{ $json.wamid }}",
                    },
                    {"parameterType": "formData", "name": "anexo_indice", "value": "0"},
                    {"parameterType": "formData", "name": "total_anexos", "value": "1"},
                    {
                        "parameterType": "formData",
                        "name": "nome_arquivo",
                        "value": "={{ $json.nome_arquivo }}",
                    },
                    {
                        "parameterType": "formData",
                        "name": "remetente",
                        "value": "={{ $json.remetente }}",
                    },
                    {
                        "parameterType": "formData",
                        "name": "recebido_em",
                        "value": "={{ $json.recebido_em }}",
                    },
                    {"parameterType": "formData", "name": "sha256", "value": "={{ $json.sha256 }}"},
                    {
                        "parameterType": "formData",
                        "name": "em_resposta_a_mensagem_canal",
                        "value": "={{ $json.em_resposta_a }}",
                    },
                ]
            },
        },
    )
    http(
        f,
        "Exceção: SHA-256 divergente",
        "POST",
        f"={{{{ {cfg}.cfg_pcpr }}}}/excecoes",
        (3300, 400),
        tentativas=3,
        espera_ms=1000,
        cabecalhos=[("Idempotency-Key", chave_limitada("excecao:whatsapp-sha256:", "$json.wamid"))],
        corpo_json="={{ JSON.stringify({ fluxo: 'recebimento-canais', "
        "correlacao_id: 'whatsapp:' + String($json.wamid).slice(-12), motivo: 'outro', "
        "detalhe: 'SHA-256 da mídia baixada diverge do informado pela Meta; nada importado.' "
        "}) }}",  # corpo estável sob a chave por wamid (sem id da execução)
    )
    http(
        f,
        "Registrar mensagem sem anexo",
        "POST",
        f"={{{{ {cfg}.cfg_pcpr }}}}/recebimentos/sem-arquivo",
        (1540, 560),
        tentativas=3,
        espera_ms=1000,
        cabecalhos=[("Idempotency-Key", chave_recebimento_js("'whatsapp'", "$json.wamid", "0"))],
        corpo_json="={{ JSON.stringify({ canal: 'whatsapp', mensagem_id_canal: $json.wamid, "
        "anexo_indice: 0, total_anexos: 1, remetente: $json.remetente, "
        "recebido_em: $json.recebido_em, motivo: 'sem_anexo' }) }}",
    )
    # status: sub-workflow W8; se falhar, o W7 falha → 500 → a Meta reentrega
    chamar(f, "Status → W8", W8, (1540, 760), continuar=False, alwaysOutputData=True)
    nada(f, "Ignorar evento", (1540, 920))
    f.no(
        "Juntar",
        "n8n-nodes-base.merge",
        3.2,
        {"mode": "append", "numberInputs": 4},
        (3520, 560),
    )
    # 200 só DEPOIS de o PCPR aceitar: o n8n não guarda execução (nada a reprocessar), então a
    # reentrega da Meta é a retentativa. Duplicatas: a Idempotency-Key por wamid no PCPR.
    # Status de mensagem cujo resultado ainda não foi registrado (W8 devolve adiar=true) → 503:
    # a Meta reentrega o lote; o que já foi gravado repete sem efeito (C7 do PR #23).
    codigo(
        f,
        "Decidir resposta",
        "return [{ json: { adiar: $input.all().some((i) => i.json && i.json.adiar === true) } }];",
        (3740, 560),
    )
    se(f, "Adiar algum status?", "={{ $json.adiar === true }}", (3960, 560))
    f.no(
        "Responder 503 (reentregar)",
        "n8n-nodes-base.respondToWebhook",
        1.1,
        {
            "respondWith": "json",
            "responseBody": '{"erro":"status_de_mensagem_ainda_nao_registrada"}',
            "options": {"responseCode": 503},
        },
        (4180, 660),
    )
    f.no(
        "Responder 200",
        "n8n-nodes-base.respondToWebhook",
        1.1,
        {"respondWith": "noData", "options": {"responseCode": 200}},
        (4180, 460),
    )
    for a, b in [
        ("Calcular verify token esperado", "Conferir verificação"),
        ("Conferir verificação", "Verificação válida?"),
        ("Calcular assinatura", "Validar assinatura"),
        ("Validar assinatura", "Assinatura válida?"),
        ("Configuração", "Separar eventos"),
        ("Separar eventos", "Tipo de evento"),
        ("Obter URL da mídia", "Baixar mídia"),
        ("Baixar mídia", "Download OK?"),
        ("Obter nova URL", "Baixar mídia (nova URL)"),
        ("Baixar mídia (nova URL)", "SHA-256 da mídia"),
        ("SHA-256 da mídia", "Conferir SHA-256"),
        ("Conferir SHA-256", "SHA-256 confere?"),
        ("Juntar", "Decidir resposta"),
        ("Decidir resposta", "Adiar algum status?"),
    ]:
        f.liga(a, b)
    f.liga("Adiar algum status?", "Responder 503 (reentregar)", 0)
    f.liga("Adiar algum status?", "Responder 200", 1)
    f.liga("Webhook WhatsApp", "Calcular verify token esperado", 0)  # GET
    f.liga("Webhook WhatsApp", "Calcular assinatura", 1)  # POST
    f.liga("Verificação válida?", "Responder desafio", 0)
    f.liga("Verificação válida?", "Responder 403", 1)
    f.liga("Assinatura válida?", "Configuração", 0)
    f.liga("Assinatura válida?", "Responder 401", 1)
    f.liga("Tipo de evento", "Obter URL da mídia", 0)
    f.liga("Tipo de evento", "Registrar mensagem sem anexo", 1)
    f.liga("Tipo de evento", "Status → W8", 2)
    f.liga("Tipo de evento", "Ignorar evento", 3)
    f.liga("Download OK?", "SHA-256 da mídia", 0)
    f.liga("Download OK?", "Obter nova URL", 1)
    f.liga("SHA-256 confere?", "Entregar ao PCPR", 0)
    f.liga("SHA-256 confere?", "Exceção: SHA-256 divergente", 1)
    for origem, entrada in [
        ("Entregar ao PCPR", 0),
        ("Exceção: SHA-256 divergente", 0),
        ("Registrar mensagem sem anexo", 1),
        ("Status → W8", 2),
        ("Ignorar evento", 3),
    ]:
        f.liga(origem, "Juntar", 0, entrada)
    # telefone, wamid, URL e arquivo: nada fica guardado no n8n (ver TW13 sobre o que sobra)
    return f.json({"errorWorkflow": W5, **SEM_RETENCAO})


# ------------------------------------------------------------------ W8 · status WhatsApp

JS_MAPEAR_STATUS = r"""
// sent → nada (o resultado já registrou o aceite); delivered → entregue; read → lida;
// failed → falhou. A comunicação vem de biz_opaque_callback_data ('com:<id>') quando houver.
const MAPA = { delivered: 'entregue', read: 'lida', failed: 'falhou' };
const cfg = $('Configuração').first().json;
const saida = [];
for (const it of $('Quando chamado pelo W7').all()) {
  const s = it.json;
  const status = MAPA[s.status];
  if (!status) continue;
  const m = /^com:(\d+)$/.exec(String(s.biz_opaque_callback_data || ''));
  const e = (s.errors || [])[0] || null;
  saida.push({ json: {
    cfg_pcpr: cfg.cfg_pcpr,
    comunicacao_id: m ? Number(m[1]) : null,
    wamid: String(s.id || ''),
    status,
    ocorrido_em: new Date(Number(s.timestamp || 0) * 1000).toISOString(),
    erro: e ? ('código ' + e.code + ': ' + String(e.title || e.message || '')).slice(0, 300) : '',
  } });
}
return saida;
"""

JS_USAR_ID = r"""
// Sem biz_opaque_callback_data: o PCPR resolve pelo mapeamento wamid → comunicação
// (GET /comunicacoes?provedor_mensagem_id=, operação do contrato; resposta só {id, versao}).
const ev = $('Mapear status').item.json;
const achado = ($json.itens || [])[0];
return { json: { ...ev, comunicacao_id: achado ? achado.id : null } };
"""

JS_RESUMO_W8 = r"""
// O W7 decide a resposta à Meta com isto: algum status adiado → não-2xx (a Meta reentrega).
const itens = $input.all();
const adiados = itens.filter((i) => i.json.adiar === true).length;
return [{ json: { adiar: adiados > 0, adiados, registrados: itens.length - adiados } }];
"""


def w8() -> dict:
    f = Fluxo(W8)
    f.no(
        "Quando chamado pelo W7",
        "n8n-nodes-base.executeWorkflowTrigger",
        1.1,
        {"inputSource": "passthrough"},
        (0, 300),
    )
    definir(
        f,
        "Configuração",
        [
            ("cfg_pcpr", PCPR_PADRAO, "string"),
            # status de wamid desconhecido mais velho que isto não é mais adiado: o resultado não
            # vai chegar (a reserva vence em 10 min) → exceção e 200 (a Meta reentregaria 7 dias)
            ("cfg_adiar_max_s", ADIAR_STATUS_MAX_S, "number"),
        ],
        (220, 300),
    )
    codigo(f, "Mapear status", JS_MAPEAR_STATUS, (440, 300))
    se(f, "Tem comunicação?", "={{ $json.comunicacao_id !== null }}", (660, 300))
    http(
        f,
        "Buscar pelo wamid",
        "GET",
        "={{ $json.cfg_pcpr }}/comunicacoes?provedor_mensagem_id="
        "{{ encodeURIComponent($json.wamid) }}",
        (880, 420),
        tentativas=3,
        espera_ms=1000,
    )
    codigo(f, "Usar id encontrado", JS_USAR_ID, (1100, 420), por_item=True)
    f.no(
        "Juntar ids",
        "n8n-nodes-base.merge",
        3.2,
        {"mode": "append", "numberInputs": 2},
        (1320, 300),
    )
    # Status que chegou ANTES do /resultado (wamid ainda sem comunicação no PCPR): não é
    # descartado — o W7 responde não-2xx e a Meta reentrega depois (C7 do PR #23). Só enquanto
    # for recente: um status órfão antigo vira exceção e é confirmado (sem 7 dias de reentrega).
    se(
        f,
        "Adiar? (resultado ainda não registrado)",
        "={{ $json.comunicacao_id === null && (Date.now() - Date.parse($json.ocorrido_em)) <= "
        "$('Configuração').first().json.cfg_adiar_max_s * 1000 }}",
        (1540, 300),
    )
    se(f, "Comunicação conhecida?", "={{ $json.comunicacao_id !== null }}", (1760, 300))
    http(
        f,
        "Exceção: status sem comunicação",
        "POST",
        "={{ $json.cfg_pcpr }}/excecoes",
        (1980, 420),
        tentativas=3,
        espera_ms=1000,
        cabecalhos=[
            (
                "Idempotency-Key",
                chave_limitada("excecao:whatsapp-status:", "$json.wamid + ':' + $json.status"),
            ),
        ],
        corpo_json="={{ JSON.stringify({ fluxo: 'whatsapp', "
        "correlacao_id: 'whatsapp:status:' + $json.wamid.slice(-12), motivo: 'outro', "
        # corpo = função só da chave (wamid + status): sem o limite configurável, que mudaria o
        # corpo numa reentrega depois de reconfigurar (422 "chave reutilizada" → W7 em não-2xx)
        "detalhe: 'Status ' + $json.status + ' de uma mensagem que o PCPR não conhece (nenhum "
        "resultado com este id do provedor depois do prazo de espera): confirmado à Meta sem "
        "gravar. Conferir se houve envio sem registro.' }) }}",
    )
    definir(f, "Marcar órfão", [("adiar", False, "boolean")], (2200, 420))
    definir(f, "Marcar adiado", [("adiar", True, "boolean")], (1760, 560))
    http(
        f,
        "Registrar entrega",
        "POST",
        "={{ $json.cfg_pcpr }}/comunicacoes/{{ $json.comunicacao_id }}/entrega",
        (1980, 200),
        tentativas=3,
        espera_ms=1000,
        cabecalhos=[
            (
                "Idempotency-Key",
                chave_limitada(
                    "entrega:", "$json.comunicacao_id + ':' + $json.wamid + ':' + $json.status"
                ),
            )
        ],
        corpo_json="={{ JSON.stringify({ provedor_mensagem_id: $json.wamid, status: $json.status, "
        "ocorrido_em: $json.ocorrido_em, erro: $json.erro || undefined }) }}",
    )
    definir(f, "Marcar registrado", [("adiar", False, "boolean")], (2200, 200))
    f.no(
        "Juntar resultado",
        "n8n-nodes-base.merge",
        3.2,
        {"mode": "append", "numberInputs": 3},
        (2420, 300),
    )
    codigo(f, "Resumo", JS_RESUMO_W8, (2640, 300))
    for a, b in [
        ("Quando chamado pelo W7", "Configuração"),
        ("Configuração", "Mapear status"),
        ("Mapear status", "Tem comunicação?"),
        ("Buscar pelo wamid", "Usar id encontrado"),
        ("Juntar ids", "Adiar? (resultado ainda não registrado)"),
        ("Registrar entrega", "Marcar registrado"),
        ("Juntar resultado", "Resumo"),
    ]:
        f.liga(a, b)
    f.liga("Tem comunicação?", "Juntar ids", 0, 0)
    f.liga("Tem comunicação?", "Buscar pelo wamid", 1)
    f.liga("Usar id encontrado", "Juntar ids", 0, 1)
    f.liga("Adiar? (resultado ainda não registrado)", "Marcar adiado", 0)
    f.liga("Adiar? (resultado ainda não registrado)", "Comunicação conhecida?", 1)
    f.liga("Comunicação conhecida?", "Registrar entrega", 0)
    f.liga("Comunicação conhecida?", "Exceção: status sem comunicação", 1)
    f.liga("Exceção: status sem comunicação", "Marcar órfão")
    f.liga("Marcar órfão", "Juntar resultado", 0, 2)
    f.liga("Marcar registrado", "Juntar resultado", 0, 0)
    f.liga("Marcar adiado", "Juntar resultado", 0, 1)
    return f.json({"errorWorkflow": W5, "callerPolicy": "workflowsFromSameOwner", **SEM_RETENCAO})


def construir(
    destino: Path,
    pcpr: str = PCPR_PADRAO,
    canal: str = CANAL_PADRAO,
    whatsapp: bool = False,
    graph: str = GRAPH_PADRAO,
) -> list[Path]:
    destino.mkdir(parents=True, exist_ok=True)
    saida = []
    fabricas = [(W1, w1), (W2, w2), (W3, w3), (W4, w4), (W5, w5)]
    if whatsapp:
        fabricas += [(W6, w6), (W7, w7), (W8, w8)]
    nomes = {**ARQUIVOS, **ARQUIVOS_WHATSAPP}
    for wid, fabrica in fabricas:
        texto = json.dumps(fabrica(), ensure_ascii=False, indent=2)
        texto = texto.replace(PCPR_PADRAO, pcpr).replace(CANAL_PADRAO, canal)
        texto = texto.replace(GRAPH_PADRAO, graph)
        p = destino / nomes[wid]
        p.write_text(texto, encoding="utf-8")
        saida.append(p)
    return saida


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("destino", type=Path)
    ap.add_argument("--pcpr", default=PCPR_PADRAO)
    ap.add_argument("--canal", default=CANAL_PADRAO)
    ap.add_argument("--whatsapp", action="store_true", help="inclui W6–W8 (WA-3)")
    args = ap.parse_args()
    for caminho in construir(args.destino, args.pcpr, args.canal, args.whatsapp):
        print(caminho)
