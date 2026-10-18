"""Simulador do PCPR para o protótipo de automação (dados 100% sintéticos, só stdlib).

Implementa em memória o subconjunto da API `docs/automacao/contratos/api-automacao.v1.yaml`
usado pelos workflows (W1–W5) e um emissor de eventos assinados no envelope
`evento-integracao.schema.json`. Endpoints `/_sim/*` controlam o cenário de teste.

    python simulador_pcpr.py --porta 8765
    (segredos por variável de ambiente: PCPR_SIM_TOKEN, PCPR_SIM_SEGREDO_HMAC,
     PCPR_SIM_URL_EVENTOS, PCPR_SIM_LEASE_S)

Extensões ao contrato usadas aqui (propostas, ver README):
- `X-PCPR-Versao-Esperada` no POST reservar → 409 `conflito_de_versao` se a comunicação mudou;
- `recurso` {tipo, id} opcional no corpo de POST /excecoes (liga a exceção ao registro);
- cabeçalho de resposta `Idempotency-Replayed: true` quando a chave já tinha resposta.

Canal WhatsApp oficial (frente WA-3, só contra o simulador da Graph API `simulador_graph.py`):
- `/estado.canais.whatsapp` e `canais_entrada.whatsapp` ∈ {ligado, desligado, bloqueado};
  **padrão `bloqueado`** (PCPR_SIM_CANAL_WHATSAPP só muda o padrão deste simulador);
- canal bloqueado → comunicação `aguardando_envio_manual` (WA-1: o operador envia pelo aparelho
  institucional e marca "enviado por outro meio" → `feita_a_mao`, origem `outro_meio`);
- contato verificado com opt-in obrigatório para WhatsApp (senão 409 `regra_violada`, estado
  `sem_contato` e exceção `contato_nao_verificado`);
- reserva traz `mensagem.whatsapp` (forma pedida, janela de 24 h conhecida pelo PCPR, modelo
  *utility* e variáveis) e, para documento, `anexos[].url_assinada` curta;
- mapeamento wamid → comunicação; `POST /comunicacoes/{id}/entrega` idempotente e sem regressão;
  `GET /comunicacoes?provedor_mensagem_id=` (consulta pelo wamid);
- `POST /recebimentos/sem-arquivo` (mensagem sem anexo; abre a janela);
- variante V2: `GET|POST /canais/whatsapp/webhook` — o webhook da Meta entra direto no PCPR,
  que verifica `X-Hub-Signature-256`, registra e baixa a mídia pela Graph API (o n8n não vê).

Ajustes da revisão do PR #23 (Codex):
- o envelope `comunicacao.agendada` só leva campos do contrato (o antigo `rotulo` não-ASCII saiu;
  o teste de UTF-8 usa um evento avulso válido, `POST /_sim/eventos`, e o modo de entrega
  `assinatura_ascii`) — C2;
- `POST /recebimentos` exige, como o contrato, `anexo_indice` e `total_anexos` e a chave
  `receb:<canal>:<mensagem_id_canal>:<anexo_indice>`; campo ausente/inválido → 422 — C3;
- `falha_temporaria` volta para `agendada` com backoff curto configurável (`/_sim/config`
  `backoff_s`, `max_rodadas`); esgotadas as rodadas → `falhou` + exceção `limite_tentativas`
  aberta pelo PCPR — C6;
- `GET /comunicacoes?provedor_mensagem_id=` devolve só `{id, versao}` (operação do contrato) — C10;
- deduplicação de recebimento por (servidor remetente resolvido, SHA-256), não global — C11;
- falha injetável em `POST /recebimentos` (`falhar_recebimentos`: 503 não guardado) — C9.
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
import uuid
from datetime import UTC, datetime, timedelta
from http.server import ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

from comum import (
    CABECALHO_ASSINATURA,
    CABECALHO_EVENTO_ID,
    ManipuladorBase,
    agora_utc,
    assinar,
    corpo_json,
    iso_z,
    ler_multipart,
)
from regra_vespera import FUSO, ComunicacaoRef, ViagemRef, planejar
from simulador_canal import pdf_sintetico

PREFIXO = "/api/automacao/v1"
ESTADOS_CANAL = {"ligado", "desligado", "bloqueado"}
JANELA_WHATSAPP = timedelta(hours=24)
# tipo de comunicação → modelo utility aprovado na Meta (cópia do texto versionado no PCPR)
MODELOS_WHATSAPP = {
    "link_km": "pcpr_km_vespera_v1",
    "documentos_disponiveis": "pcpr_documentos_disponiveis_v1",
    "documentos_para_assinatura": "pcpr_documentos_disponiveis_v1",
    "lembrete_pendencia": "pcpr_aviso_pendencia_v1",
}
STATUS_WHATSAPP = {"delivered": "entregue", "read": "lida", "failed": "falhou"}
RESULTADOS = {"enviada", "falha_temporaria", "falha_definitiva", "resultado_desconhecido"}
MOTIVOS_EXCECAO = {
    "canal_indisponivel",
    "resultado_desconhecido",
    "destinatario_sem_contato",
    "contato_nao_verificado",
    "documento_nao_identificado",
    "limite_tentativas",
    "outro",
}
LIMITE_ARQUIVO = 25 * 1024 * 1024
# Rodadas de envio (reservas) de uma comunicação com falha temporária no canal e espera entre
# elas. Padrão "de produção" encurtado; os testes trocam por segundos em /_sim/config.
MAX_RODADAS_PADRAO = 3
BACKOFF_PADRAO_S = [120, 600]
_ids = itertools.count(1)  # nunca reinicia: ids não se repetem entre cenários


def _iso_sp(d: datetime) -> str:
    return d.astimezone(FUSO).isoformat(timespec="seconds")


def _serializar(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return f"<{len(obj)} bytes>"
    if isinstance(obj, dict):
        return {k: _serializar(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_serializar(v) for v in obj]
    return obj


class Estado:
    def __init__(
        self,
        token: str,
        segredo: bytes,
        url_eventos: str,
        lease_s: int,
        wa: dict[str, str] | None = None,
    ) -> None:
        self.trava = threading.RLock()
        self.token = token
        self.segredo = segredo
        self.url_eventos = url_eventos
        self.lease_s = lease_s
        self.ambiente = "teste"
        # WhatsApp oficial (WA-3): segredos sintéticos por ambiente; canal BLOQUEADO por padrão
        self.wa = dict(wa or {})
        self.wa.setdefault("canal_padrao", "bloqueado")
        if self.wa["canal_padrao"] not in ESTADOS_CANAL:
            raise ValueError(f"PCPR_SIM_CANAL_WHATSAPP inválido: {self.wa['canal_padrao']}")
        self.resetar()

    def resetar(self) -> None:
        with self.trava:
            padrao_wa = self.wa["canal_padrao"]
            self.automacao: dict[str, Any] = {
                "ligada": True,
                "motivo": "",
                "fluxos": {"km-vespera": True, "envio-documentos": True, "recebimento": True},
                "canais": {"portal": "ligado", "email": "ligado", "whatsapp": padrao_wa},
                "canais_entrada": {"email": "ligado", "whatsapp": padrao_wa},
            }
            self.desligar_apos_estado = False
            self.falhar_estado = 0
            self.falhar_recebimentos = 0  # próximos N POST /recebimentos → 503 (não guardado)
            self.max_rodadas = MAX_RODADAS_PADRAO
            self.backoff_s = list(BACKOFF_PADRAO_S)
            self.viagens: dict[int, dict] = {}
            self.comunicacoes: dict[int, dict] = {}
            self.idem: dict[str, dict] = {}
            self.recebimentos: dict[int, dict] = {}
            # dedup do recebimento: (servidor remetente resolvido, SHA-256) → recebimento
            self.recebimento_por_servidor_sha: dict[str, int] = {}
            # "<canal>:<remetente>" → id do servidor (cadastro de contatos, sintético)
            self.servidor_por_remetente: dict[str, int] = {}
            self.excecoes: list[dict] = []
            self.excecao_por_chave: dict[str, dict] = {}
            self.log: list[dict] = []
            self.eventos: dict[str, dict] = {}
            # WhatsApp
            self.contatos: dict[str, dict] = {}  # destino E.164 → ContatoVerificado (sintético)
            self.janelas: dict[str, datetime] = {}  # última mensagem do contato (abre 24 h)
            self.marcas: dict[str, dict] = {}  # wamid → entregue_em/lida_em/falhou_em
            self.com_por_wamid: dict[str, int] = {}
            self.arquivos_assinados: dict[str, dict] = {}
            self.wa_vistos: dict[str, int] = {}  # V2: chave do evento → quantas vezes chegou
            self.wa_log: list[dict] = []  # V2: webhooks e downloads (sem dado pessoal)

    # ------------------------------------------------------------ WhatsApp: apoio
    def canal(self, nome: str, entrada: bool = False) -> str:
        grupo = "canais_entrada" if entrada else "canais"
        return self.automacao[grupo].get(nome, "desligado")

    def registrar_contato(self, destino: str, situacao: str = "ok") -> None:
        if situacao == "nenhum":
            self.contatos.pop(destino, None)
            return
        agora = agora_utc()
        self.contatos[destino] = {
            "destino": destino,
            "canal": "whatsapp",
            "verificado": situacao != "nao_verificado",
            "consentimento_em": None if situacao == "sem_opt_in" else agora - timedelta(days=30),
            "revogado_em": agora - timedelta(days=1) if situacao == "revogado" else None,
            "metodo": "presencial",
            "origem": "cadastro (sintético)",
        }

    def contato_apto(self, destino: str) -> bool:
        c = self.contatos.get(destino)
        return bool(c and c["verificado"] and c["consentimento_em"] and not c["revogado_em"])

    def janela_ate(self, destino: str) -> datetime | None:
        ultima = self.janelas.get(destino)
        return ultima + JANELA_WHATSAPP if ultima else None

    def entrega_de(self, c: dict) -> str | None:
        """Entrega/leitura são marcas que nunca regridem (lida não volta a entregue)."""
        m = self.marcas.get(c.get("provedor_mensagem_id") or "")
        if not m:
            return c.get("entrega")
        if m["lida_em"]:
            return "lida"
        if m["entregue_em"]:
            return "entregue"
        return "falhou" if m["falhou_em"] else None

    def aplicar_status(
        self, wamid: str, status: str, ocorrido_em: str | None, erro: str | None, cid: int | None
    ) -> dict:
        """Status do provedor (entregue/lida/falhou). Idempotente; fora de ordem não regride."""
        m = self.marcas.setdefault(
            wamid, {"entregue_em": None, "lida_em": None, "falhou_em": None, "erro": None}
        )
        campo = {"entregue": "entregue_em", "lida": "lida_em", "falhou": "falhou_em"}[status]
        novo = m[campo] is None
        if novo:
            m[campo] = ocorrido_em or iso_z(agora_utc())
            if status == "falhou":
                m["erro"] = (erro or "")[:300]
        cid = cid or self.com_por_wamid.get(wamid)
        c = self.comunicacoes.get(cid) if cid else None
        if c and novo and status == "falhou" and not (m["entregue_em"] or m["lida_em"]):
            self._apos_falha_de_entrega(c, m["erro"] or "")
        return {
            "id": c and c["id"],
            "provedor_mensagem_id": wamid,
            "entrega": (
                self.entrega_de(c) if c and c.get("provedor_mensagem_id") == wamid else None
            ),
            "marcas": {k: v for k, v in m.items() if k != "erro"},
            "novo": novo,
        }

    def _apos_falha_de_entrega(self, c: dict, erro: str) -> None:
        """`failed` com 131047 numa mensagem livre → o PCPR agenda UMA substituta por modelo
        (decisão do PCPR; o n8n só transporta). Outras falhas → exceção."""
        forma = (c.get("whatsapp") or {}).get("forma")
        tem_modelo = bool(c.get("whatsapp", {}).get("modelo"))
        if (
            "131047" in erro
            and forma in ("texto", "documento")
            and not c.get("substituta_id")
            and tem_modelo
        ):
            nova = self._nova_comunicacao(
                self.viagens[c["viagem_id"]],
                c["tipo"],
                agora_utc(),
                True,
                None,
                canal="whatsapp",
                destino=c["destino"],
                forma="modelo",
                com_modelo=True,
            )
            nova["substitui"] = c["id"]
            c["substituta_id"] = nova["id"]
            eventos = [self._evento_comunicacao(nova, None)]
            threading.Thread(
                target=lambda: [self.entregar_evento(e["id"]) for e in eventos], daemon=True
            ).start()
            return
        self._abrir_excecao(
            chave=f"pcpr:entrega-falhou:{c['id']}",
            corpo={
                "fluxo": "whatsapp",
                "correlacao_id": c["correlacao_id"],
                "motivo": "outro",
                "detalhe": f"Provedor informou falha de entrega: {erro[:200]}",
                "recurso": {"tipo": "comunicacao", "id": c["id"]},
            },
            origem="pcpr",
        )

    def novo_arquivo_assinado(self, dados: bytes, nome: str) -> dict:
        tok = "arqSIM" + secrets.token_urlsafe(18)
        expira = agora_utc() + timedelta(minutes=10)
        self.arquivos_assinados[tok] = {"dados": dados, "nome": nome, "expira": expira}
        base = self.wa.get("url_publica", "http://host.docker.internal:8765")
        return {
            "nome": nome,
            "url_assinada": f"{base}/arquivos-assinados/{tok}",
            "sha256": hashlib.sha256(dados).hexdigest(),
            "expira_em": iso_z(expira),
        }

    def criar_recebimento(
        self, campos: dict[str, str], dados: bytes | None, nome: str | None, tipo: str | None
    ) -> tuple[int, dict]:
        """Regra única de recebimento (API v1 e webhook direto V2)."""
        canal = campos.get("canal", "")
        remetente = campos.get("remetente", "")
        if canal == "whatsapp":
            try:
                quando = datetime.fromisoformat(campos["recebido_em"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                quando = agora_utc()
            if quando > self.janelas.get(remetente, quando - timedelta(seconds=1)):
                self.janelas[remetente] = quando  # mensagem do usuário abre/renova a janela
        cid_resposta = None
        if campos.get("em_resposta_a_mensagem_canal"):
            cid_resposta = self.com_por_wamid.get(campos["em_resposta_a_mensagem_canal"])
        if dados is None:  # sem arquivo (texto puro, anexo grande demais, não baixado)
            rid = next(_ids)
            self.recebimentos[rid] = {
                "id": rid,
                "estado": "rejeitado",
                "motivo": campos.get("motivo"),
                "campos": campos,
                "em_resposta_a_comunicacao": cid_resposta,
                "recebido_pela_api_em": agora_utc(),
            }
            return 202, _publico_recebimento(self.recebimentos[rid])
        sha = hashlib.sha256(dados).hexdigest()
        # Duplicado = o MESMO servidor já mandou estes bytes (por qualquer contato/mensagem). Dois
        # servidores que devolvem o mesmo arquivo (ex.: formulário em branco idêntico) são dois
        # recebimentos (C11; contrato: "mesmo SHA-256 no mesmo destino").
        servidor = self.servidor_de(canal, remetente)
        chave_dedup = f"{servidor}|{sha}"
        if chave_dedup in self.recebimento_por_servidor_sha:
            original = self.recebimentos[self.recebimento_por_servidor_sha[chave_dedup]]
            rid = next(_ids)
            self.recebimentos[rid] = {
                "id": rid,
                "estado": "duplicado",
                "duplicado_de": original["id"],
                "sha256": sha,
                "servidor": servidor,
                "campos": campos,
            }
            return 202, _publico_recebimento(self.recebimentos[rid])
        rid = next(_ids)
        if canal == "whatsapp":  # número não verificado → quarentena para conferência humana
            quarentena = not self.contatos.get(remetente, {}).get("verificado")
        else:
            quarentena = remetente.startswith("+5500999")  # "contato não verificado"
        self.recebimentos[rid] = {
            "id": rid,
            "estado": "quarentena_remetente" if quarentena else "aceito_para_processamento",
            "importacao_id": 100000 + rid,
            "sha256": sha,
            "servidor": servidor,
            "tamanho": len(dados),
            "nome": nome,
            "tipo": tipo,
            "campos": campos,
            "em_resposta_a_comunicacao": cid_resposta,
            "assinatura": "nao_verificada",
            "recebido_pela_api_em": agora_utc(),
        }
        self.recebimento_por_servidor_sha[chave_dedup] = rid
        return 202, _publico_recebimento(self.recebimentos[rid])

    def servidor_de(self, canal: str, remetente: str) -> str:
        """Servidor a quem o contato pertence (cadastro sintético em /_sim/remetentes). Contato
        sem vínculo não é "resolvido": a deduplicação fica restrita ao próprio endereço."""
        sid = self.servidor_por_remetente.get(f"{canal}:{remetente}")
        return f"servidor:{sid}" if sid else f"nao_resolvido:{canal}:{remetente}"

    # ------------------------------------------------------------ negócio
    def _nova_viagem(self, inicio: datetime) -> dict:
        v = {
            "id": next(_ids),
            "versao": 1,
            "inicio": inicio.astimezone(FUSO),
            "estado": "confirmada",
            "comunicacao_id": None,
        }
        self.viagens[v["id"]] = v
        return v

    def _nova_comunicacao(
        self,
        viagem: dict,
        tipo: str,
        enviar_em: datetime,
        imediato: bool,
        aviso: str | None,
        *,
        canal: str = "email",
        destino: str | None = None,
        forma: str = "modelo",
        com_modelo: bool = True,
        nome_modelo: str | None = None,
    ) -> dict:
        # Canal padrão = e-mail (o canal previsto). O "canal simulado" da suíte principal faz o
        # papel do transporte; antes do WA-3 ele levava o rótulo fictício "whatsapp".
        cid = next(_ids)
        c = {
            "id": cid,
            "viagem_id": viagem["id"],
            "tipo": tipo,
            "versao": 1,
            "versao_viagem": viagem["versao"],
            "enviar_em": enviar_em.astimezone(FUSO),
            "imediato": imediato,
            "aviso": aviso,
            "estado": "agendada",
            "canal": canal,
            "destino": destino or f"+550000000{cid:04d}",  # número sintético (DDD 00 não existe)
            "correlacao_id": f"viagem:{viagem['id']}",
            "reserva": None,
            "tentativas": 0,
            "resultado": None,
            "provedor_mensagem_id": None,
            "entrega": None,
            "motivo": None,
            "criada_em": agora_utc(),
            "enviada_em": None,
        }
        if canal == "whatsapp":
            nome = nome_modelo or MODELOS_WHATSAPP.get(tipo, "pcpr_documentos_disponiveis_v1")
            c["whatsapp"] = {
                "forma": forma,
                "modelo": {"nome": nome, "idioma": "pt_BR", "categoria": "utility"}
                if com_modelo
                else None,
            }
            if forma == "documento":
                pdf = pdf_sintetico(f"PCPR-DOC-SINTETICO-OUT oficio da comunicacao {cid}")
                c["whatsapp"]["pdf"] = pdf
                c["whatsapp"]["pdf_sha256"] = hashlib.sha256(pdf).hexdigest()
        self.comunicacoes[cid] = c
        viagem["comunicacao_id"] = cid
        return c

    def _envelope(
        self, tipo: str, recurso: dict, correlacao: str, dados: dict, causa: str | None = None
    ) -> dict:
        ev = {
            "id": str(uuid.uuid4()),
            "tipo": tipo,
            "versao_contrato": 1,
            "ocorrido_em": iso_z(agora_utc()),
            "ambiente": self.ambiente,
            "recurso": recurso,
            "correlacao_id": correlacao,
            "causa_id": causa,
            "dados": dados,
        }
        self.eventos[ev["id"]] = {"envelope": ev, "corpo": corpo_json(ev), "entregas": []}
        return ev

    def _evento_comunicacao(self, c: dict, causa: str | None) -> dict:
        return self._envelope(
            "comunicacao.agendada",
            {"tipo": "comunicacao", "id": c["id"], "versao": c["versao"]},
            c["correlacao_id"],
            {
                "comunicacao_id": c["id"],
                "tipo_comunicacao": c["tipo"],
                "fluxo": "km-vespera",
                "enviar_em": _iso_sp(c["enviar_em"]),
                "imediato": c["imediato"],
                "aviso": c["aviso"],
                # Só campos do contrato ($defs/dados.comunicacao.agendada, additionalProperties
                # false). O teste de UTF-8 no corpo bruto usa um evento avulso (POST /_sim/eventos).
            },
            causa,
        )

    def evento_avulso(self, tipo: str, recurso: dict, correlacao: str, dados: dict) -> dict:
        """Evento montado pelo teste (ex.: corpo com UTF-8 num campo do contrato); o teste valida
        o envelope contra o esquema antes de entregá-lo."""
        with self.trava:
            return self._envelope(tipo, recurso, correlacao, dados)

    def confirmar_viagem(self, inicio: datetime, tipo: str) -> tuple[dict, dict, list[dict]]:
        with self.trava:
            v = self._nova_viagem(inicio)
            plano = planejar(ViagemRef(v["versao"], v["inicio"]), None, agora_utc())
            d = plano.criar
            assert d is not None
            c = self._nova_comunicacao(v, tipo, d.enviar_em, d.imediato, d.aviso)
            e1 = self._envelope(
                "viagem.confirmada",
                {"tipo": "viagem", "id": v["id"], "versao": v["versao"]},
                c["correlacao_id"],
                {"inicio_previsto": _iso_sp(v["inicio"])},
            )
            e2 = self._evento_comunicacao(c, e1["id"])
            return v, c, [e1, e2]

    def reagendar_viagem(self, vid: int, inicio: datetime) -> tuple[dict, dict | None, list]:
        with self.trava:
            v = self.viagens[vid]
            anterior = v["inicio"]
            v["versao"] += 1
            v["inicio"] = inicio.astimezone(FUSO)
            atual = self.comunicacoes.get(v["comunicacao_id"] or 0)
            ref = (
                ComunicacaoRef(atual["id"], atual["versao_viagem"], atual["estado"])
                if atual
                else None
            )
            plano = planejar(ViagemRef(v["versao"], v["inicio"]), ref, agora_utc())
            eventos = [
                self._envelope(
                    "viagem.reagendada",
                    {"tipo": "viagem", "id": v["id"], "versao": v["versao"]},
                    f"viagem:{v['id']}",
                    {"inicio_previsto": _iso_sp(v["inicio"]), "inicio_anterior": _iso_sp(anterior)},
                )
            ]
            if plano.cancelar_id and atual:
                atual.update(estado="cancelada", motivo=plano.motivo_cancelamento)
                atual["versao"] += 1
                eventos.append(
                    self._envelope(
                        "comunicacao.cancelada",
                        {"tipo": "comunicacao", "id": atual["id"], "versao": atual["versao"]},
                        atual["correlacao_id"],
                        {"comunicacao_id": atual["id"], "motivo": plano.motivo_cancelamento},
                        eventos[0]["id"],
                    )
                )
            nova = None
            if plano.criar:
                d = plano.criar
                nova = self._nova_comunicacao(
                    v,
                    atual["tipo"] if atual else "link_km",
                    d.enviar_em,
                    d.imediato,
                    d.aviso,
                    canal=atual["canal"] if atual else "email",
                    destino=atual["destino"] if atual else None,
                )
                eventos.append(self._evento_comunicacao(nova, eventos[0]["id"]))
            return v, nova, eventos

    def cancelar_viagem(self, vid: int) -> list[dict]:
        with self.trava:
            v = self.viagens[vid]
            v["versao"] += 1
            v["estado"] = "cancelada"
            atual = self.comunicacoes.get(v["comunicacao_id"] or 0)
            ref = (
                ComunicacaoRef(atual["id"], atual["versao_viagem"], atual["estado"])
                if atual
                else None
            )
            plano = planejar(ViagemRef(v["versao"], v["inicio"], cancelada=True), ref, agora_utc())
            eventos = [
                self._envelope(
                    "viagem.cancelada",
                    {"tipo": "viagem", "id": v["id"], "versao": v["versao"]},
                    f"viagem:{v['id']}",
                    {},
                )
            ]
            if plano.cancelar_id and atual:
                atual.update(estado="cancelada", motivo=plano.motivo_cancelamento)
                atual["versao"] += 1
                eventos.append(
                    self._envelope(
                        "comunicacao.cancelada",
                        {"tipo": "comunicacao", "id": atual["id"], "versao": atual["versao"]},
                        atual["correlacao_id"],
                        {"comunicacao_id": atual["id"], "motivo": plano.motivo_cancelamento},
                        eventos[0]["id"],
                    )
                )
            return eventos

    def criar_comunicacao_avulsa(
        self, tipo: str, enviar_em: datetime, opcoes: dict | None = None
    ) -> tuple[dict, list]:
        o = opcoes or {}
        with self.trava:
            v = self._nova_viagem(enviar_em + timedelta(days=1))
            canal = o.get("canal", "email")
            c = self._nova_comunicacao(
                v,
                tipo,
                enviar_em,
                True,
                None,
                canal=canal,
                destino=o.get("destino"),
                forma=o.get("forma", "modelo"),
                com_modelo=o.get("com_modelo", True),
                nome_modelo=o.get("nome_modelo"),
            )
            if canal == "whatsapp":
                self.registrar_contato(c["destino"], o.get("contato", "ok"))
                if self.canal("whatsapp") == "bloqueado":
                    # WA-1: nada vai para a automação; o operador envia à mão e registra
                    c.update(estado="aguardando_envio_manual", motivo="canal_bloqueado")
                    return c, []
            return c, [self._evento_comunicacao(c, None)]

    def nova_versao_comunicacao(self, cid: int) -> list:
        with self.trava:
            c = self.comunicacoes[cid]
            c["versao"] += 1  # ex.: texto ou destinatário revisado; mesma viagem
            return [self._evento_comunicacao(c, None)]

    def reemitir_comunicacao(self, cid: int) -> list:
        """Novo evento (id novo) para a MESMA versão: simula a dedup do n8n sendo contornada
        (ex.: evento e reconciliação ao mesmo tempo, ou outbox republicando)."""
        with self.trava:
            return [self._evento_comunicacao(self.comunicacoes[cid], None)]

    def varrer_reservas(self) -> None:
        """Reserva vencida sem resultado → resultado desconhecido → exceção (não reenvia)."""
        with self.trava:
            agora = agora_utc()
            for c in self.comunicacoes.values():
                r = c["reserva"]
                if c["estado"] == "enviando" and r and r["expira_em"] < agora:
                    c.update(
                        estado="falhou",
                        resultado="resultado_desconhecido",
                        motivo="reserva_vencida_sem_resultado",
                    )
                    self._abrir_excecao(
                        chave=f"pcpr:reserva-vencida:{c['id']}:{r['token']}",
                        corpo={
                            "fluxo": "km-vespera",
                            "correlacao_id": c["correlacao_id"],
                            "motivo": "resultado_desconhecido",
                            "detalhe": "Reserva venceu sem resultado do orquestrador. Conferir no "
                            "canal se a mensagem saiu antes de reenviar manualmente.",
                            "recurso": {"tipo": "comunicacao", "id": c["id"]},
                        },
                        origem="pcpr",
                    )

    def _abrir_excecao(self, chave: str, corpo: dict, origem: str) -> tuple[dict, bool]:
        if chave in self.excecao_por_chave:
            return self.excecao_por_chave[chave], False
        ex = {
            "id": next(_ids),
            "chave": chave,
            "origem": origem,
            "fluxo": corpo.get("fluxo"),
            "correlacao_id": corpo.get("correlacao_id"),
            "motivo": corpo.get("motivo"),
            "detalhe": (corpo.get("detalhe") or "")[:2000],
            "execucao_orquestrador": corpo.get("execucao_orquestrador"),
            "recurso": corpo.get("recurso"),
            "aberta_em": agora_utc(),
            "situacao": "aberta",
        }
        self.excecoes.append(ex)
        self.excecao_por_chave[chave] = ex
        return ex, True

    # ------------------------------------------------------------ entrega de eventos
    def entregar_evento(self, evento_id: str, modo: str = "normal") -> dict:
        with self.trava:
            reg = self.eventos[evento_id]
            corpo = reg["corpo"]
            correlacao = reg["envelope"]["correlacao_id"]
        t = int(time.time())
        segredo = self.segredo
        if modo == "antigo":
            t -= 600  # assinado corretamente, mas fora da janela de ±5 min
        if modo == "assinatura_invalida":
            segredo = b"segredo-errado-" + secrets.token_bytes(8)
        if modo == "outro_ambiente":  # assinado certo, mas declara outro ambiente
            corpo = corpo_json({**reg["envelope"], "ambiente": "producao"})
        assinado = corpo
        if modo == "assinatura_ascii":
            # assina a MESMA informação re-serializada com escapes (é…), mas envia os bytes
            # UTF-8: só passa se o n8n verificar uma re-serialização em vez do corpo bruto
            assinado = json.dumps(reg["envelope"], ensure_ascii=True, separators=(",", ":")).encode(
                "ascii"
            )
        cabecalhos = {
            "Content-Type": "application/json; charset=utf-8",
            CABECALHO_EVENTO_ID: evento_id,
            # cabeçalho HTTP é latin-1: a correlação vai com escapes (o corpo leva o texto real)
            "X-PCPR-Correlacao": correlacao.encode("ascii", "backslashreplace").decode("ascii"),
        }
        if modo != "sem_assinatura":
            cabecalhos[CABECALHO_ASSINATURA] = assinar(segredo, assinado, t)
        enviado = corpo + b" " if modo == "corpo_adulterado" else corpo  # JSON ainda válido
        inicio = time.time()
        entrega: dict[str, Any] = {"modo": modo, "em": inicio, "status": None, "erro": None}
        try:
            req = urllib.request.Request(
                self.url_eventos, data=enviado, headers=cabecalhos, method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                entrega["status"] = resp.status
                entrega["resposta"] = resp.read().decode("utf-8", "replace")[:500]
        except urllib.error.HTTPError as exc:
            entrega["status"] = exc.code
            entrega["resposta"] = exc.read().decode("utf-8", "replace")[:500]
        except (urllib.error.URLError, OSError) as exc:
            entrega["erro"] = repr(exc)  # n8n fora do ar: na vida real a outbox tentaria de novo
        entrega["ms"] = round((time.time() - inicio) * 1000, 1)
        with self.trava:
            self.eventos[evento_id]["entregas"].append(entrega)
        return entrega

    def despejo(self) -> dict:
        with self.trava:
            return _serializar(
                {
                    "automacao": self.automacao,
                    "viagens": list(self.viagens.values()),
                    "comunicacoes": [
                        {**c, "entrega": self.entrega_de(c)} for c in self.comunicacoes.values()
                    ],
                    "recebimentos": list(self.recebimentos.values()),
                    "excecoes": self.excecoes,
                    "log": self.log,
                    "eventos": [
                        {"envelope": r["envelope"], "entregas": r["entregas"]}
                        for r in self.eventos.values()
                    ],
                    "contatos": list(self.contatos.values()),
                    "janelas": dict(self.janelas),
                    "marcas": self.marcas,
                    "com_por_wamid": self.com_por_wamid,
                    "wa_vistos": self.wa_vistos,
                    "wa_log": self.wa_log,
                }
            )


# ==================================================================== HTTP


class Manipulador(ManipuladorBase):
    server_version = "SimuladorPCPR/0.1"

    @property
    def estado(self) -> Estado:
        return self.server.estado  # type: ignore[attr-defined]

    def rotear(self, metodo: str) -> None:
        url = urlsplit(self.path)
        caminho = url.path.rstrip("/") or "/"
        if caminho.startswith("/_sim"):
            return self._controle(metodo, caminho)
        if caminho.startswith("/arquivos-assinados/") and metodo == "GET":
            return self._arquivo_assinado(caminho.rsplit("/", 1)[-1])
        if caminho == "/canais/whatsapp/webhook":  # variante V2 (público, sem token de serviço)
            return self._webhook_whatsapp(metodo, parse_qs(url.query))
        if not caminho.startswith(PREFIXO):
            return self.responder(
                404, {"codigo": "entrada_invalida", "mensagem": "rota inexistente"}
            )
        rota = caminho[len(PREFIXO) :] or "/"
        self._registro: dict[str, Any] = {
            "ts": time.time(),
            "metodo": metodo,
            "rota": rota,
            "chave": self.headers.get("Idempotency-Key"),
            "correlacao": self.headers.get("X-PCPR-Correlacao"),
        }
        try:
            self._api(metodo, rota, parse_qs(url.query))
        finally:
            with self.estado.trava:
                self.estado.log.append(self._registro)

    # ------------------------------------------------------------ resposta da API
    def _resp(self, status: int, corpo: Any, extra: dict | None = None) -> None:
        self._registro["status"] = status
        if isinstance(corpo, dict) and "codigo" in corpo:
            self._registro["codigo"] = corpo["codigo"]
        cab = dict(extra or {})
        if self._registro.get("correlacao"):
            cab["X-PCPR-Correlacao"] = self._registro["correlacao"]
        self.responder(status, corpo, cab)

    def _erro(self, status: int, codigo: str, mensagem: str, **mais: Any) -> tuple[int, dict]:
        return status, {"codigo": codigo, "mensagem": mensagem, **mais}

    def _api(self, metodo: str, rota: str, qs: dict) -> None:
        est = self.estado
        auth = self.headers.get("Authorization", "")
        if not hmac.compare_digest(auth.encode(), f"Bearer {est.token}".encode()):
            return self._resp(401, {"codigo": "negado", "mensagem": "Token de serviço inválido."})
        est.varrer_reservas()
        if metodo == "GET" and rota == "/estado":
            return self._estado()
        if metodo == "GET" and rota == "/comunicacoes/devidas":
            return self._devidas(qs)
        if metodo == "GET" and rota == "/comunicacoes":
            return self._por_mensagem_canal(qs)
        m = re.fullmatch(r"/recebimentos/(\d+)", rota)
        if metodo == "GET" and m:
            with est.trava:
                r = est.recebimentos.get(int(m.group(1)))
            if not r:
                return self._resp(404, {"codigo": "entrada_invalida", "mensagem": "não existe"})
            return self._resp(200, _publico_recebimento(r))
        if metodo != "POST":
            return self._resp(405, {"codigo": "entrada_invalida", "mensagem": "método"})

        chave = self.headers.get("Idempotency-Key") or ""
        if not 16 <= len(chave) <= 200:
            return self._resp(
                400,
                {
                    "codigo": "entrada_invalida",
                    "mensagem": "Idempotency-Key obrigatório (16 a 200 caracteres).",
                },
            )
        corpo = self.corpo_bruto()
        impressao = self._impressao(metodo, rota, corpo)
        with est.trava:  # a trava cobre efeito + gravação da resposta: repetição é atômica
            salvo = est.idem.get(chave)
            if salvo:
                if salvo["impressao"] != impressao:
                    return self._resp(
                        422,
                        {
                            "codigo": "entrada_invalida",
                            "mensagem": "Idempotency-Key reutilizada com outra requisição.",
                        },
                    )
                self._registro["replay"] = True
                self._registro["comunicacao_id"] = salvo.get("comunicacao_id")
                return self._resp(salvo["status"], salvo["corpo"], {"Idempotency-Replayed": "true"})
            status, resposta, guardar = self._post(rota, corpo)
            if guardar:
                est.idem[chave] = {
                    "impressao": impressao,
                    "status": status,
                    "corpo": resposta,
                    "comunicacao_id": self._registro.get("comunicacao_id"),
                }
        return self._resp(status, resposta)

    def _impressao(self, metodo: str, rota: str, corpo: bytes) -> str:
        """Impressão digital da requisição para conferir reuso da Idempotency-Key.

        multipart/form-data NÃO pode ser comparado byte a byte: o boundary muda a cada envio
        (descoberto no T9 — o n8n reenvia o mesmo arquivo com outro boundary). Usa-se o
        conteúdo semântico: campos + SHA-256 de cada arquivo.
        """
        tipo = self.headers.get("Content-Type", "")
        if tipo.startswith("multipart/form-data"):
            campos, arquivos = ler_multipart(tipo, corpo)
            canonico = json.dumps(
                {
                    "campos": campos,
                    "arquivos": {
                        k: hashlib.sha256(v["dados"]).hexdigest() for k, v in arquivos.items()
                    },
                },
                sort_keys=True,
            ).encode()
        elif re.fullmatch(r"/comunicacoes/\d+/entrega", rota):
            # status repetido pela Meta pode vir com outro timestamp: a identidade é
            # (mensagem, status) — senão a repetição daria 422 e o webhook entraria em laço
            b = self.corpo_dict()
            canonico = json.dumps([b.get("provedor_mensagem_id"), b.get("status")]).encode()
        else:
            canonico = corpo
        extra = (self.headers.get("X-PCPR-Versao-Esperada") or "").encode()
        return hashlib.sha256(f"{metodo} {rota} ".encode() + canonico + b"|" + extra).hexdigest()

    # ------------------------------------------------------------ GET
    def _estado(self) -> None:
        est = self.estado
        with est.trava:
            if est.falhar_estado > 0:
                est.falhar_estado -= 1
                return self._resp(
                    500, {"codigo": "integracao_indisponivel", "mensagem": "falha simulada"}
                )
            a = est.automacao
            corpo = {
                "ligada": a["ligada"],
                "motivo": a["motivo"],
                "ambiente": est.ambiente,
                "fluxos": a["fluxos"],
                "canais": a["canais"],
                "canais_entrada": a["canais_entrada"],
            }
            if est.desligar_apos_estado and a["ligada"]:
                # corrida simulada: operador desliga logo depois desta consulta
                a.update(ligada=False, motivo="desligada durante o teste T5b")
                est.desligar_apos_estado = False
        return self._resp(200, corpo)

    def _devidas(self, qs: dict) -> None:
        est = self.estado
        limite = max(1, min(100, int((qs.get("limite") or ["50"])[0])))
        agora = agora_utc()
        with est.trava:
            devidas = sorted(
                (
                    c
                    for c in est.comunicacoes.values()
                    if c["estado"] == "agendada" and c["enviar_em"] <= agora
                ),
                key=lambda c: c["enviar_em"],
            )[:limite]
            itens = [
                {
                    "id": c["id"],
                    "tipo": c["tipo"],
                    "enviar_em": _iso_sp(c["enviar_em"]),
                    "versao": c["versao"],
                    "correlacao_id": c["correlacao_id"],
                }
                for c in devidas
            ]
        self._registro["devidas"] = [i["id"] for i in itens]
        return self._resp(200, {"itens": itens})

    # ------------------------------------------------------------ POST (sob a trava)
    def _post(self, rota: str, corpo: bytes) -> tuple[int, Any, bool]:
        m = re.fullmatch(r"/comunicacoes/(\d+)/(reservar|resultado|entrega)", rota)
        if m:
            cid = int(m.group(1))
            self._registro["comunicacao_id"] = cid
            return getattr(self, f"_{m.group(2)}")(cid)
        if rota == "/recebimentos":
            return self._recebimento(corpo)
        if rota == "/recebimentos/sem-arquivo":
            return self._recebimento_sem_arquivo()
        if rota == "/excecoes":
            return self._excecao()
        return 404, {"codigo": "entrada_invalida", "mensagem": "rota inexistente"}, False

    def _reservar(self, cid: int) -> tuple[int, Any, bool]:
        est = self.estado
        a = est.automacao
        if not a["ligada"] or not a["fluxos"].get("km-vespera", True):
            return (
                423,
                {
                    "codigo": "desligada",
                    "mensagem": "Automação desligada; nada foi feito. "
                    "O processo segue manual até religar.",
                },
                False,
            )
        c = est.comunicacoes.get(cid)
        if not c:
            return 404, {"codigo": "entrada_invalida", "mensagem": "comunicação inexistente"}, False
        v = est.viagens.get(c["viagem_id"])
        esperado = self.headers.get("X-PCPR-Versao-Esperada")
        if c["estado"] == "cancelada":
            return (
                409,
                {
                    "codigo": "obsoleta",
                    "estado_atual": "cancelada",
                    "mensagem": f"Comunicação cancelada ({c['motivo']}); não enviar.",
                },
                True,
            )
        if esperado and esperado.isdigit() and int(esperado) != c["versao"]:
            return (
                409,
                {
                    "codigo": "conflito_de_versao",
                    "estado_atual": c["estado"],
                    "mensagem": f"Versão {esperado} obsoleta; atual é {c['versao']}.",
                },
                True,
            )
        if v and c["versao_viagem"] != v["versao"]:
            return (
                409,
                {
                    "codigo": "obsoleta",
                    "estado_atual": c["estado"],
                    "mensagem": "A viagem mudou depois do agendamento; não enviar.",
                },
                True,
            )
        if c["estado"] != "agendada":
            return (
                409,
                {
                    "codigo": "ja_processada",
                    "estado_atual": c["estado"],
                    "mensagem": "Já reservada, enviada ou encerrada.",
                },
                True,
            )
        estado_canal = est.canal(c["canal"])
        if estado_canal == "bloqueado":
            # bloqueado ≠ desligado: só muda por configuração versionada + ADR. A comunicação
            # passa ao envio manual registrado (WA-1) e sai da automação.
            c.update(estado="aguardando_envio_manual", motivo="canal_bloqueado")
            return (
                409,
                {
                    "codigo": "canal_bloqueado",
                    "estado_atual": c["estado"],
                    "mensagem": f"Canal {c['canal']} bloqueado: aguardando envio manual "
                    "registrado (WA-1).",
                },
                True,
            )
        if estado_canal != "ligado":
            return (
                423,
                {
                    "codigo": "desligada",
                    "mensagem": f"Canal {c['canal']} desligado; nada foi feito. Segue agendada.",
                },
                False,
            )
        if c["canal"] == "whatsapp" and not est.contato_apto(c["destino"]):
            c.update(estado="sem_contato", motivo="contato_nao_verificado")
            est._abrir_excecao(
                chave=f"pcpr:contato-nao-verificado:{c['id']}",
                corpo={
                    "fluxo": "whatsapp",
                    "correlacao_id": c["correlacao_id"],
                    "motivo": "contato_nao_verificado",
                    "detalhe": "Contato de WhatsApp sem verificação, sem opt-in ou com opt-in "
                    "revogado: nada foi enviado. Usar outro canal ou o envio manual registrado.",
                    "recurso": {"tipo": "comunicacao", "id": c["id"]},
                },
                origem="pcpr",
            )
            return (
                409,
                {
                    "codigo": "regra_violada",
                    "motivo": "contato_nao_verificado",
                    "estado_atual": c["estado"],
                    "mensagem": "Contato sem verificação ou sem opt-in para WhatsApp; não enviar.",
                },
                True,
            )
        if c["enviar_em"] > agora_utc():
            return (
                409,
                {
                    "codigo": "regra_violada",
                    "estado_atual": "agendada",
                    "mensagem": f"Ainda não é hora: {_iso_sp(c['enviar_em'])}.",
                },
                True,
            )
        token = "rsvSIM" + secrets.token_urlsafe(18)  # prefixo para o T13 achar o valor
        expira = agora_utc() + timedelta(seconds=est.lease_s)
        c.update(
            estado="enviando",
            reserva={
                "token": token,
                "expira_em": expira,
                "chave": self.headers.get("Idempotency-Key"),
            },
        )
        c["tentativas"] += 1
        inicio = est.viagens[c["viagem_id"]]["inicio"]
        link_km = f"https://pcpr.example.invalid/km/c{c['id']}"
        corpo: dict[str, Any] = {
            "id": c["id"],
            "tipo": c["tipo"],
            "canal": c["canal"],
            "destino": c["destino"],
            "mensagem": {
                "modelo": "km_vespera_v1",
                "assunto": "Registro de quilometragem",
                "texto": f"Mensagem sintética de teste: viagem em {_iso_sp(inicio)}. "
                f"Registre a quilometragem em {link_km}",
                "variaveis": {"inicio": _iso_sp(inicio)},
            },
            "anexos": [],
            "reserva": {"token": token, "expira_em": iso_z(expira)},
            "idempotencia_canal": f"pcpr-com-{c['id']}-v{c['versao']}",
            "versao": c["versao"],
            "correlacao_id": c["correlacao_id"],
        }
        if c["canal"] == "whatsapp":
            corpo["conteudo_sensivel"] = c["tipo"] == "link_km"
            corpo["mensagem"]["whatsapp"] = self._conteudo_whatsapp(c, link_km)
            if c["whatsapp"]["forma"] == "documento":
                corpo["anexos"] = [
                    est.novo_arquivo_assinado(
                        c["whatsapp"]["pdf"], f"oficio-sintetico-{c['id']}.pdf"
                    )
                ]
        return 200, corpo, True

    def _conteudo_whatsapp(self, c: dict, link_km: str) -> dict:
        """Renderizador `para_whatsapp` (sintético): forma pedida pelo PCPR, janela que o PCPR
        conhece e o modelo utility de reserva, com variáveis sem CPF, RG, telefone ou valores."""
        est = self.estado
        wa = c["whatsapp"]
        janela = est.janela_ate(c["destino"])
        link = (
            link_km if c["tipo"] == "link_km" else "https://pcpr.example.invalid/meus-documentos/"
        )
        modelo = None
        if wa["modelo"]:
            n = 1 if wa["modelo"]["nome"] == "pcpr_aviso_pendencia_v1" else 2
            modelo = {**wa["modelo"], "parametros": ["Fulana", link][:n]}
        return {
            "forma": wa["forma"],
            "janela_aberta_ate": iso_z(janela) if janela else None,
            "modelo": modelo,
            "texto": "Mensagem sintética: seus documentos estão disponíveis no portal "
            "(acesse com login; nenhum dado pessoal nesta mensagem).",
            "legenda": "Documento sintético de teste",
        }

    def _resultado(self, cid: int) -> tuple[int, Any, bool]:
        est = self.estado
        c = est.comunicacoes.get(cid)
        if not c:
            return 404, {"codigo": "entrada_invalida", "mensagem": "comunicação inexistente"}, False
        b = self.corpo_dict()
        resultado = b.get("resultado")
        if resultado not in RESULTADOS or not b.get("reserva_token"):
            return 400, {"codigo": "entrada_invalida", "mensagem": "resultado/reserva_token"}, False
        r = c["reserva"]
        if not r or not hmac.compare_digest(r["token"], str(b["reserva_token"])):
            return (
                409,
                {"codigo": "conflito_de_versao", "mensagem": "Reserva de outra execução."},
                True,
            )
        if c["estado"] != "enviando":
            return (
                409,
                {
                    "codigo": "ja_processada",
                    "estado_atual": c["estado"],
                    "mensagem": "Reserva vencida ou já encerrada.",
                },
                True,
            )
        self._registro["resultado"] = resultado
        c["resultado"] = resultado
        c["provedor_mensagem_id"] = b.get("provedor_mensagem_id")
        if c["provedor_mensagem_id"]:  # wamid → comunicação (status chegam só com o wamid)
            est.com_por_wamid[c["provedor_mensagem_id"]] = c["id"]
        c.setdefault("rodadas", []).append(
            {"resultado": resultado, "erro": (b.get("erro") or "")[:300], "em": agora_utc()}
        )
        if resultado == "enviada":
            c.update(estado="enviada", enviada_em=agora_utc())
        elif resultado == "falha_temporaria" and c["tentativas"] < est.max_rodadas:
            # o canal provou que NÃO aceitou: o PCPR reagenda (nova reserva na próxima rodada,
            # pela reconciliação) com backoff; nada de laço dentro do n8n (C6)
            espera = est.backoff_s[min(c["tentativas"], len(est.backoff_s)) - 1]
            c.update(
                estado="agendada",
                reserva=None,
                enviar_em=agora_utc() + timedelta(seconds=espera),
            )
        elif resultado == "falha_temporaria":
            # rodadas esgotadas: exceção humana no fim (o PCPR abre; o n8n não abre para temporária)
            c.update(estado="falhou", motivo="limite_tentativas")
            est._abrir_excecao(
                chave=f"pcpr:limite-tentativas:{c['id']}",
                corpo={
                    "fluxo": "km-vespera",
                    "correlacao_id": c["correlacao_id"],
                    "motivo": "limite_tentativas",
                    "detalhe": f"{c['tentativas']} rodadas de envio com falha temporária no "
                    f"canal; última: {(b.get('erro') or '')[:200]}",
                    "recurso": {"tipo": "comunicacao", "id": c["id"]},
                },
                origem="pcpr",
            )
        else:
            c.update(estado="falhou", motivo=b.get("erro") or resultado)
        return 200, {"id": c["id"], "estado": c["estado"], "resultado": resultado}, True

    def _entrega(self, cid: int) -> tuple[int, Any, bool]:
        est = self.estado
        c = est.comunicacoes.get(cid)
        b = self.corpo_dict()
        wamid = str(b.get("provedor_mensagem_id") or "")
        if not c or not wamid:
            return 404, {"codigo": "entrada_invalida", "mensagem": "mensagem desconhecida"}, False
        if b.get("status") not in ("entregue", "lida", "falhou"):
            return 400, {"codigo": "entrada_invalida", "mensagem": "status"}, False
        if c["provedor_mensagem_id"] and c["provedor_mensagem_id"] != wamid:
            return (
                409,
                {"codigo": "conflito_de_versao", "mensagem": "Status de outra mensagem do canal."},
                True,
            )
        # se o resultado ainda não chegou (status antes do POST resultado), a marca fica
        # guardada pelo wamid e passa a valer quando o resultado registrar o mesmo wamid
        r = est.aplicar_status(wamid, b["status"], b.get("ocorrido_em"), b.get("erro"), cid)
        self._registro["entrega"] = {"status": b["status"], "novo": r["novo"]}
        return 200, {"id": c["id"], "entrega": est.entrega_de(c) or r["entrega"]}, True

    def _por_mensagem_canal(self, qs: dict) -> None:
        """`GET /comunicacoes?provedor_mensagem_id=` (contrato, C10): resposta mínima {id, versao},
        sem destino nem conteúdo. Lista vazia = o resultado com esse id ainda não foi registrado
        (o n8n responde não-2xx ao provedor para ele reentregar o status depois)."""
        wamid = (qs.get("provedor_mensagem_id") or [""])[0]
        if not wamid or len(wamid) > 300:
            return self._resp(
                422,
                {"codigo": "entrada_invalida", "mensagem": "provedor_mensagem_id obrigatório"},
            )
        with self.estado.trava:
            cid = self.estado.com_por_wamid.get(wamid)
            c = self.estado.comunicacoes.get(cid) if cid else None
            itens = [{"id": c["id"], "versao": c["versao"]}] if c else []
        self._registro["encontrou"] = bool(itens)
        return self._resp(200, {"itens": itens})

    def _recebimento(self, corpo: bytes) -> tuple[int, Any, bool]:
        est = self.estado
        if len(corpo) > LIMITE_ARQUIVO + 64 * 1024:
            return (
                413,
                {"codigo": "entrada_invalida", "mensagem": "Acima de 25 MiB: use o portal."},
                False,
            )
        if est.falhar_recebimentos > 0:  # falha injetada (C9): nada gravado, nada guardado
            est.falhar_recebimentos -= 1
            return (
                503,
                {"codigo": "integracao_indisponivel", "mensagem": "falha simulada; repita"},
                False,
            )
        campos, arquivos = ler_multipart(self.headers.get("Content-Type", ""), corpo)
        recusa = self._recusa_canal_entrada(campos.get("canal", ""))
        if recusa:
            return recusa
        obrigatorios = (
            "canal",
            "mensagem_id_canal",
            "anexo_indice",
            "total_anexos",
            "remetente",
            "recebido_em",
            "sha256",
        )
        faltando = [k for k in obrigatorios if not campos.get(k)]
        if "arquivo" not in arquivos or faltando:
            return self._invalido(f"Campos obrigatórios ausentes: {faltando or ['arquivo']}")
        problema = self._conferir_anexo(campos)
        if problema:
            return self._invalido(problema)
        dados = arquivos["arquivo"]["dados"]
        sha = hashlib.sha256(dados).hexdigest()
        if sha != campos["sha256"].lower():
            return self._invalido("SHA-256 informado não confere com o arquivo.")
        status, resposta = est.criar_recebimento(
            campos, dados, arquivos["arquivo"]["filename"], arquivos["arquivo"]["content_type"]
        )
        self._registro["recebimento_id"] = resposta["id"]
        return status, resposta, True

    def _recusa_canal_entrada(self, canal: str) -> tuple[int, Any, bool] | None:
        situacao = self.estado.canal(canal, entrada=True)
        if situacao == "bloqueado":
            return (
                409,
                {"codigo": "canal_bloqueado", "mensagem": f"Canal de entrada {canal} bloqueado."},
                True,
            )
        if situacao != "ligado":
            return 423, {"codigo": "desligada", "mensagem": f"Canal {canal} desligado."}, False
        return None

    def _invalido(self, mensagem: str) -> tuple[int, Any, bool]:
        return 422, {"codigo": "entrada_invalida", "mensagem": mensagem}, False

    def _conferir_anexo(self, campos: dict) -> str | None:
        """Regras do contrato para `anexo_indice`/`total_anexos` e a chave de idempotência
        `receb:<canal>:<mensagem_id_canal>:<anexo_indice>` (10-6 E1; C3 do PR #23)."""
        try:
            indice = int(str(campos["anexo_indice"]))
            total = int(str(campos["total_anexos"]))
        except (KeyError, ValueError):
            return "anexo_indice e total_anexos devem ser inteiros"
        if indice < 0 or total < 1 or indice >= total:
            return f"anexo_indice {indice} fora de 0..total_anexos-1 ({total})"
        esperada = f"receb:{campos['canal']}:{campos['mensagem_id_canal']}:{indice}"
        if self.headers.get("Idempotency-Key") != esperada:
            return "Idempotency-Key deve ser receb:<canal>:<mensagem_id_canal>:<anexo_indice>"
        return None

    def _recebimento_sem_arquivo(self) -> tuple[int, Any, bool]:
        b = self.corpo_dict()
        recusa = self._recusa_canal_entrada(str(b.get("canal", "")))
        if recusa:
            return recusa
        obrigatorios = (
            "canal",
            "mensagem_id_canal",
            "anexo_indice",
            "total_anexos",
            "remetente",
            "recebido_em",
            "motivo",
        )
        faltando = [k for k in obrigatorios if b.get(k) in (None, "")]
        if faltando or b.get("motivo") not in ("acima_do_limite", "sem_anexo", "nao_baixado"):
            return self._invalido(f"faltando: {faltando}")
        problema = self._conferir_anexo(b)
        if problema:
            return self._invalido(problema)
        status, resposta = self.estado.criar_recebimento(
            {k: str(v) for k, v in b.items()}, None, None, None
        )
        self._registro["recebimento_id"] = resposta["id"]
        return status, resposta, True

    # ------------------------------------------------------------ arquivo assinado (W6 baixa)
    def _arquivo_assinado(self, tok: str) -> None:
        with self.estado.trava:
            a = self.estado.arquivos_assinados.get(tok)
        if not a or a["expira"] < agora_utc():
            return self.responder(404, {"codigo": "entrada_invalida", "mensagem": "link vencido"})
        return self.responder(
            200,
            a["dados"],
            {"Content-Disposition": f'attachment; filename="{a["nome"]}"'},
            tipo="application/pdf",
        )

    # ------------------------------------------------------------ V2: webhook direto no PCPR
    def _webhook_whatsapp(self, metodo: str, qs: dict) -> None:
        """Variante V2: a Meta chama o PCPR; o n8n não vê telefone, wamid nem mídia."""
        est = self.estado
        reg: dict[str, Any] = {
            "ts": time.time(),
            "rota": "/canais/whatsapp/webhook",
            "metodo": metodo,
        }

        def fim(status: int, corpo: Any = None, tipo: str = "application/json") -> None:
            reg["status"] = status
            with est.trava:
                est.wa_log.append(reg)
            if isinstance(corpo, str):
                return self.responder(status, corpo.encode(), tipo="text/plain; charset=utf-8")
            return self.responder(status, corpo if corpo is not None else {"ok": status == 200})

        if metodo == "GET":
            modo = (qs.get("hub.mode") or [""])[0]
            recebido = (qs.get("hub.verify_token") or [""])[0].encode()
            desafio = (qs.get("hub.challenge") or [""])[0]
            esperado = est.wa.get("verify_token", "").encode()
            ok = (
                modo == "subscribe"
                and bool(esperado)
                and hmac.compare_digest(recebido, esperado)
                and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", desafio) is not None
            )
            reg["verificacao_ok"] = ok
            return fim(200, desafio) if ok else fim(403, {"erro": "verificação recusada"})
        if metodo != "POST":
            return fim(405, {"erro": "método"})
        bruto = self.corpo_bruto()
        recebida = (self.headers.get("X-Hub-Signature-256") or "").encode()
        esperada = (
            "sha256="
            + hmac.new(est.wa.get("app_secret", "").encode(), bruto, hashlib.sha256).hexdigest()
        ).encode()
        if not est.wa.get("app_secret") or not hmac.compare_digest(recebida, esperada):
            reg["assinatura_ok"] = False
            return fim(401, {"erro": "assinatura inválida"})  # nada é gravado
        reg["assinatura_ok"] = True
        situacao = est.canal("whatsapp", entrada=True)
        if situacao == "bloqueado":
            return fim(403, {"erro": "canal bloqueado"})
        if situacao != "ligado" or not est.automacao["ligada"]:
            return fim(503, {"erro": "desligado; a Meta reentrega depois"})  # nada gravado
        try:
            corpo = json.loads(bruto)
        except ValueError:
            return fim(400, {"erro": "json"})
        if corpo.get("object") != "whatsapp_business_account":
            return fim(400, {"erro": "objeto"})
        novos = duplicados = 0
        with est.trava:  # registro durável ANTES do 200 (no PCPR real: transação + outbox)
            for entrada in corpo.get("entry") or []:
                for mudanca in entrada.get("changes") or []:
                    v = mudanca.get("value") or {}
                    for msg in v.get("messages") or []:
                        n, d = self._v2_mensagem(msg)
                        novos, duplicados = novos + n, duplicados + d
                    for st in v.get("statuses") or []:
                        n, d = self._v2_status(st)
                        novos, duplicados = novos + n, duplicados + d
        reg.update(novos=novos, duplicados=duplicados)
        return fim(200)

    def _v2_mensagem(self, msg: dict) -> tuple[int, int]:
        est = self.estado
        wamid = str(msg.get("id") or "")
        chave = f"receb:whatsapp:{wamid}:0"
        est.wa_vistos[chave] = est.wa_vistos.get(chave, 0) + 1
        if est.wa_vistos[chave] > 1:
            return 0, 1  # reentrega da Meta: já registrado
        quando = datetime.fromtimestamp(int(msg.get("timestamp") or time.time()), UTC)
        campos = {
            "canal": "whatsapp",
            "mensagem_id_canal": wamid,
            "anexo_indice": "0",
            "total_anexos": "1",
            "remetente": "+" + re.sub(r"\D", "", str(msg.get("from") or "")),
            "recebido_em": iso_z(quando),
            "em_resposta_a_mensagem_canal": str((msg.get("context") or {}).get("id") or ""),
        }
        tipo = msg.get("type")
        midia = msg.get(tipo) if tipo in ("document", "image") else None
        if midia:
            job = {
                "media_id": str(midia.get("id")),
                "sha256_webhook": str(midia.get("sha256") or ""),
                "nome": str(midia.get("filename") or f"{tipo}.bin"),
                "mime": str(midia.get("mime_type") or ""),
                "campos": campos,
            }
            # janela abre já no registro; o download segue em segundo plano (fila do PCPR)
            if quando > est.janelas.get(campos["remetente"], quando - timedelta(seconds=1)):
                est.janelas[campos["remetente"]] = quando
            threading.Thread(target=self._v2_baixar, args=(job,), daemon=True).start()
        else:
            est.criar_recebimento({**campos, "motivo": "sem_anexo"}, None, None, None)
        return 1, 0

    def _v2_status(self, st: dict) -> tuple[int, int]:
        est = self.estado
        status = STATUS_WHATSAPP.get(str(st.get("status")))
        wamid = str(st.get("id") or "")
        chave = f"status:{wamid}:{st.get('status')}"
        est.wa_vistos[chave] = est.wa_vistos.get(chave, 0) + 1
        if est.wa_vistos[chave] > 1:
            return 0, 1
        if not status:  # `sent` só confirma o que o resultado já registrou
            return 1, 0
        quando = datetime.fromtimestamp(int(st.get("timestamp") or time.time()), UTC)
        erro = ""
        if st.get("errors"):
            e = st["errors"][0]
            erro = f"código {e.get('code')}: {e.get('title') or e.get('message') or ''}"
        est.aplicar_status(wamid, status, iso_z(quando), erro, None)
        return 1, 0

    def _v2_baixar(self, job: dict) -> None:
        """Mídia em 2 passos com Bearer (metadados → URL de 5 min); URL vencida → pede outra."""
        est = self.estado
        graph = est.wa.get("graph_url", "http://127.0.0.1:8767/v21.0")
        cab = {"Authorization": f"Bearer {est.wa.get('token_graph', '')}"}
        dados, meta, tentativas = None, {}, []
        for _ in range(3):
            try:
                req = urllib.request.Request(f"{graph}/{job['media_id']}", headers=cab)
                with urllib.request.urlopen(req, timeout=30) as r:
                    meta = json.loads(r.read())
                req = urllib.request.Request(meta["url"], headers=cab)
                with urllib.request.urlopen(req, timeout=120) as r:
                    dados = r.read()
                tentativas.append(200)
                break
            except urllib.error.HTTPError as exc:
                tentativas.append(exc.code)
            except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
                tentativas.append(repr(exc)[:80])
            time.sleep(0.5)
        reg: dict[str, Any] = {
            "ts": time.time(),
            "rota": "download_midia",
            "tentativas": tentativas,
        }
        with est.trava:
            if dados is None:
                reg["ok"] = False
                est.wa_log.append(reg)
                est._abrir_excecao(
                    chave=f"pcpr:midia-nao-baixada:{job['campos']['mensagem_id_canal']}",
                    corpo={
                        "fluxo": "recebimento-canais",
                        "correlacao_id": "whatsapp:" + job["campos"]["mensagem_id_canal"][-12:],
                        "motivo": "outro",
                        "detalhe": f"Mídia não baixada após {len(tentativas)} tentativas.",
                    },
                    origem="pcpr",
                )
                return
            sha = hashlib.sha256(dados).hexdigest()
            confere = sha == _sha_hex(job["sha256_webhook"]) and sha == _sha_hex(meta.get("sha256"))
            reg.update(ok=confere, sha256_confere=confere)
            est.wa_log.append(reg)
            if not confere:
                est._abrir_excecao(
                    chave=f"pcpr:sha256-divergente:{job['campos']['mensagem_id_canal']}",
                    corpo={
                        "fluxo": "recebimento-canais",
                        "correlacao_id": "whatsapp:" + job["campos"]["mensagem_id_canal"][-12:],
                        "motivo": "outro",
                        "detalhe": "SHA-256 da mídia baixada diverge do informado pela Meta.",
                    },
                    origem="pcpr",
                )
                return
            est.criar_recebimento({**job["campos"], "sha256": sha}, dados, job["nome"], job["mime"])

    def _excecao(self) -> tuple[int, Any, bool]:
        b = self.corpo_dict()
        if (
            not b.get("fluxo")
            or not b.get("correlacao_id")
            or b.get("motivo") not in MOTIVOS_EXCECAO
        ):
            return (
                400,
                {"codigo": "entrada_invalida", "mensagem": "fluxo/correlacao_id/motivo"},
                False,
            )
        ex, nova = self.estado._abrir_excecao(self.headers["Idempotency-Key"], b, origem="n8n")
        self._registro["excecao_id"] = ex["id"]
        return 201, {"id": ex["id"], "situacao": ex["situacao"], "nova": nova}, True

    # ------------------------------------------------------------ controle /_sim
    def _controle(self, metodo: str, caminho: str) -> None:
        est = self.estado
        b = self.corpo_dict() if metodo == "POST" else {}
        entregar = bool(b.get("entregar", True))

        def com_entrega(eventos: list[dict]) -> list[dict]:
            saida = []
            for e in eventos:
                item = {"id": e["id"], "tipo": e["tipo"], "recurso": e["recurso"]}
                if entregar:
                    item["entrega"] = est.entregar_evento(e["id"])
                saida.append(item)
            return saida

        if caminho == "/_sim/saude":
            return self.responder(200, {"ok": True})
        if caminho == "/_sim/estado":
            return self.responder(200, est.despejo())
        if metodo != "POST":
            return self.responder(405, {"erro": "use POST"})
        if caminho == "/_sim/resetar":
            est.resetar()
            return self.responder(200, {"ok": True})
        if caminho == "/_sim/config":
            with est.trava:
                if "lease_segundos" in b:
                    est.lease_s = int(b["lease_segundos"])
                if "backoff_s" in b:
                    est.backoff_s = [float(x) for x in b["backoff_s"]] or list(BACKOFF_PADRAO_S)
                if "max_rodadas" in b:
                    est.max_rodadas = max(1, int(b["max_rodadas"]))
                if "falhar_recebimentos" in b:
                    est.falhar_recebimentos = int(b["falhar_recebimentos"])
                atual = {
                    "lease_segundos": est.lease_s,
                    "backoff_s": est.backoff_s,
                    "max_rodadas": est.max_rodadas,
                    "falhar_recebimentos": est.falhar_recebimentos,
                }
            return self.responder(200, atual)
        if caminho == "/_sim/remetentes":  # contato → servidor (dedup por servidor, C11)
            with est.trava:
                est.servidor_por_remetente[f"{b['canal']}:{b['remetente']}"] = int(b["servidor_id"])
            return self.responder(200, {"servidor": est.servidor_de(b["canal"], b["remetente"])})
        if caminho == "/_sim/eventos":  # evento avulso (teste de UTF-8 no corpo bruto)
            ev = est.evento_avulso(
                b["tipo"], b["recurso"], b["correlacao_id"], b.get("dados") or {}
            )
            return self.responder(200, {"id": ev["id"], "envelope": ev})
        if caminho == "/_sim/automacao":
            with est.trava:
                if "ligada" in b:
                    est.automacao.update(ligada=bool(b["ligada"]), motivo=b.get("motivo", ""))
                if "desligar_apos_estado" in b:
                    est.desligar_apos_estado = bool(b["desligar_apos_estado"])
                if "falhar_estado" in b:
                    est.falhar_estado = int(b["falhar_estado"])
            return self.responder(200, {"ok": True})
        if caminho == "/_sim/varrer":
            est.varrer_reservas()
            return self.responder(200, {"ok": True})
        if caminho == "/_sim/viagens":
            inicio = datetime.fromisoformat(b["inicio"])
            v, c, evs = est.confirmar_viagem(inicio, b.get("tipo_comunicacao", "link_km"))
            return self.responder(
                200,
                {
                    "viagem_id": v["id"],
                    "comunicacao_id": c["id"],
                    "enviar_em": _iso_sp(c["enviar_em"]),
                    "imediato": c["imediato"],
                    "eventos": com_entrega(evs),
                },
            )
        m = re.fullmatch(r"/_sim/viagens/(\d+)/(reagendar|cancelar)", caminho)
        if m:
            if m.group(2) == "reagendar":
                v, nova, evs = est.reagendar_viagem(
                    int(m.group(1)), datetime.fromisoformat(b["inicio"])
                )
                return self.responder(
                    200, {"nova_comunicacao_id": nova and nova["id"], "eventos": com_entrega(evs)}
                )
            return self.responder(
                200, {"eventos": com_entrega(est.cancelar_viagem(int(m.group(1))))}
            )
        if caminho == "/_sim/comunicacoes":
            enviar_em = (
                datetime.fromisoformat(b["enviar_em"]) if b.get("enviar_em") else agora_utc()
            )
            c, evs = est.criar_comunicacao_avulsa(
                b.get("tipo", "documentos_para_assinatura"), enviar_em, b
            )
            return self.responder(
                200,
                {
                    "comunicacao_id": c["id"],
                    "estado": c["estado"],
                    "destino": c["destino"],
                    "eventos": com_entrega(evs),
                },
            )
        if caminho == "/_sim/canais":
            with est.trava:
                for chave, grupo in (
                    ("whatsapp", "canais"),
                    ("whatsapp_entrada", "canais_entrada"),
                ):
                    if chave in b:
                        if b[chave] not in ESTADOS_CANAL:
                            return self.responder(400, {"erro": f"{chave} inválido"})
                        est.automacao[grupo]["whatsapp"] = b[chave]
            return self.responder(
                200,
                {
                    "canais": est.automacao["canais"],
                    "canais_entrada": est.automacao["canais_entrada"],
                },
            )
        if caminho == "/_sim/contatos":
            with est.trava:
                est.registrar_contato(b["destino"], b.get("situacao", "ok"))
            return self.responder(200, _serializar(est.contatos.get(b["destino"])))
        if caminho == "/_sim/janela_pcpr":  # o que o PCPR "acha" da janela (TW3b/c)
            with est.trava:
                if b.get("ultima_em"):
                    est.janelas[b["destino"]] = datetime.fromisoformat(b["ultima_em"])
                else:
                    est.janelas.pop(b["destino"], None)
            return self.responder(200, {"ok": True})
        m = re.fullmatch(r"/_sim/comunicacoes/(\d+)/(envio_manual|enviado_por_outro_meio)", caminho)
        if m:
            with est.trava:
                c = est.comunicacoes[int(m.group(1))]
                if m.group(2) == "envio_manual":  # WA-1: o que a tela mostraria ao operador
                    texto = (
                        "PCPR (mensagem sintética): seus documentos estão disponíveis no portal. "
                        "Acesse com login."
                    )
                    numero = re.sub(r"\D", "", c["destino"])
                    return self.responder(
                        200,
                        {
                            "estado": c["estado"],
                            "texto": texto,
                            "link_wa_me": f"https://wa.me/{numero}?text={quote(texto)}",
                        },
                    )
                if c["estado"] not in ("aguardando_envio_manual", "sem_contato", "falhou"):
                    return self.responder(409, {"erro": f"estado {c['estado']}"})
                c.update(
                    estado="feita_a_mao",
                    origem="outro_meio",
                    registrado_por=b.get("por", "operador.sintetico"),
                    registrado_em=agora_utc(),
                )
                return self.responder(200, _serializar(c))
        m = re.fullmatch(r"/_sim/comunicacoes/(\d+)/nova_versao", caminho)
        if m:
            return self.responder(
                200, {"eventos": com_entrega(est.nova_versao_comunicacao(int(m.group(1))))}
            )
        m = re.fullmatch(r"/_sim/comunicacoes/(\d+)/reemitir", caminho)
        if m:
            return self.responder(
                200, {"eventos": com_entrega(est.reemitir_comunicacao(int(m.group(1))))}
            )
        m = re.fullmatch(r"/_sim/eventos/([0-9a-f-]{36})/entregar", caminho)
        if m:
            return self.responder(200, est.entregar_evento(m.group(1), b.get("modo", "normal")))
        return self.responder(404, {"erro": "rota de controle inexistente"})


def _sha_hex(valor: Any) -> str:
    """sha256 da Meta pode vir em hex ou em base64 (formatos vistos; doc não é explícita)."""
    v = str(valor or "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{64}", v):
        return v.lower()
    try:
        return base64.b64decode(v, validate=True).hex()
    except ValueError:
        return ""


def _publico_recebimento(r: dict) -> dict:
    corpo = {"id": r["id"], "estado": r["estado"]}
    if r.get("importacao_id"):
        corpo["importacao_id"] = r["importacao_id"]
        corpo["assinatura"] = r["assinatura"]
        corpo["resposta_ao_remetente"] = (
            "Recebemos seu arquivo; a equipe vai conferir. (mensagem sintética)"
        )
    if r.get("duplicado_de"):
        corpo["duplicado_de"] = r["duplicado_de"]
    return corpo


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--porta", type=int, default=8765)
    a = p.parse_args()
    token = os.environ.get("PCPR_SIM_TOKEN") or secrets.token_urlsafe(32)
    segredo = (os.environ.get("PCPR_SIM_SEGREDO_HMAC") or secrets.token_hex(32)).encode()
    url = os.environ.get("PCPR_SIM_URL_EVENTOS", "http://127.0.0.1:5678/webhook/pcpr-eventos")
    lease = int(os.environ.get("PCPR_SIM_LEASE_S", "600"))
    wa = {
        "canal_padrao": os.environ.get("PCPR_SIM_CANAL_WHATSAPP", "bloqueado"),
        "app_secret": os.environ.get("PCPR_SIM_WA_APP_SECRET", ""),
        "verify_token": os.environ.get("PCPR_SIM_WA_VERIFY_TOKEN", ""),
        "token_graph": os.environ.get("PCPR_SIM_WA_TOKEN", ""),
        "graph_url": os.environ.get("PCPR_SIM_GRAPH_URL", "http://127.0.0.1:8767/v21.0"),
        "url_publica": os.environ.get("PCPR_SIM_URL_PUBLICA", "http://host.docker.internal:8765"),
    }
    estado = Estado(token, segredo, url, lease, wa)
    srv = ThreadingHTTPServer((a.host, a.porta), Manipulador)
    srv.daemon_threads = True
    srv.estado = estado  # type: ignore[attr-defined]

    def varredor() -> None:
        while True:
            time.sleep(1)
            estado.varrer_reservas()

    threading.Thread(target=varredor, daemon=True).start()
    print(json.dumps({"simulador": "pcpr", "porta": a.porta}), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
