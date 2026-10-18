"""Roda os cenários do protótipo (T1–T13, TW0–TW13) contra a API de automação REAL do PCPR.

    .venv/Scripts/python.exe docs/automacao/prototipo/testar_pcpr_real.py
        [--apenas T1,T2,TW5]   só alguns cenários (dependências entram sozinhas)
        [--sem-exportar]       não grava docs/automacao/n8n/pcpr/*.json
        [--manter]             deixa tudo no ar no fim (depuração; limpar à mão depois)
        [--relatorio CAMINHO]  grava o relatório em outro arquivo

Diferença para `testar_prototipo.py`/`testar_whatsapp.py`: aqui NÃO há `simulador_pcpr.py`. O n8n
fala com o PCPR de verdade (Django `runserver` do worktree, PostgreSQL descartável, `APP_ENV=lab`,
`AUTOMACAO_TRANSPORTE=n8n`), os eventos saem do emissor real (`gestao.automacao.eventos`, pelo
mesmo `rodada()` do `manage.py processar_automacao`, num fio desta suíte) e o webhook V2 da Meta é
o do próprio PCPR (`/integracoes/whatsapp/webhook/`). Continua simulada só a Graph API
(`simulador_graph.py`). Tudo em 127.0.0.1; nenhum segredo real; nada ativado fora do contêiner.

Peças (todas criadas e removidas pela suíte):

| Peça | Porta | O que é |
|---|---|---|
| `pcpr-testdb-n8n` (postgres:16, tmpfs) | 55439 | banco descartável do PCPR |
| `manage.py runserver` | 8770 | PCPR real (LAB) com a guarda de rede (`guarda_rede/`) |
| `espiao_pcpr.py` | 8775 | proxy transparente n8n → PCPR que anota status e rotas |
| `simulador_graph.py` | 8777 | Graph API simulada |
| `pcpr-real-n8n` (n8n 2.43.7) | 5679 | W1–W3, W5–W8 gerados com `--alvo pcpr` |

Relógio: dois cenários (T7 e T10) precisam que o tempo passe (espera de 2 e 8 min entre
rodadas; reserva de 10 min). A suíte "avança o relógio" mudando `proxima_tentativa_em` ou
`reservada_ate` no banco descartável — o efeito é o mesmo de esperar, e o relatório diz onde.

Resultado: `resultados/resultados-pcpr-real.json` (sem segredos: a suíte confere e registra).
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import contextlib
import hashlib
import hmac
import importlib.util
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import construir_workflows as cw  # noqa: E402
import n8n_local  # noqa: E402
from regra_vespera import FUSO  # noqa: E402
from validar_esquema import validar  # noqa: E402

REPO = RAIZ.parents[2]
SAIDA = RAIZ / "resultados"
RELATORIO = SAIDA / "resultados-pcpr-real.json"
DOCS_N8N_PCPR = REPO / "docs" / "automacao" / "n8n" / "pcpr"
SCHEMA_EVENTOS = REPO / "docs" / "automacao" / "contratos" / "evento-integracao.schema.json"
GUARDA = RAIZ / "guarda_rede"
PYTHON = REPO / ".venv" / "Scripts" / "python.exe"

PORTAS = {"n8n": 5679, "pcpr": 8770, "espiao": 8775, "graph": 8777, "postgres": 55439}
CONTEINER_PG = "pcpr-testdb-n8n"
n8n_local.configurar("pcpr-real-n8n", "pcpr-real-n8n-dados", PORTAS["n8n"])
N8N = n8n_local.URL
PCPR = f"http://127.0.0.1:{PORTAS['pcpr']}"
API = f"{PCPR}/api/automacao/v1"  # chamadas diretas da suíte (sem o espião)
ESPIAO = f"http://127.0.0.1:{PORTAS['espiao']}"
GRAPH = f"http://127.0.0.1:{PORTAS['graph']}"
WEBHOOK_PCPR = f"{PCPR}/integracoes/whatsapp/webhook/"
CALLBACK = {"V1": f"{N8N}/webhook/whatsapp", "V2": WEBHOOK_PCPR}
BASE_MIDIA = {"V1": f"http://host.docker.internal:{PORTAS['graph']}", "V2": GRAPH}
SUMIDOURO = [
    "graph.facebook.com:127.0.0.1",
    "graph.whatsapp.com:127.0.0.1",
    "lookaside.fbsbx.com:127.0.0.1",
    "facebook.com:127.0.0.1",
    "www.facebook.com:127.0.0.1",
]
MODELO_AVISO = "pcpr_diarias_liberadas_v1"  # 4 variáveis: nome, ofício, liberação, prazo
NUMERO_ID = cw.NUMERO_ID_PADRAO

SEGREDOS: dict[str, str] = {
    "hmac_eventos": secrets.token_hex(32),
    "disparo": secrets.token_urlsafe(24),
    "n8n_cripto": secrets.token_hex(32),
    "wa_token_graph_sim": "EAASIM" + secrets.token_urlsafe(40),
    "wa_token_falso_pcpr": "EAAFALSO" + secrets.token_urlsafe(40),
    "wa_app_secret": secrets.token_hex(16),
    "wa_chave_verify": secrets.token_hex(32),
    "django_secret": secrets.token_urlsafe(40),
}
SEGREDOS["wa_verify_token"] = hmac.new(
    SEGREDOS["wa_chave_verify"].encode(), cw.VERIFY_TOKEN_MENSAGEM.encode(), hashlib.sha256
).hexdigest()

E: dict[str, Any] = {"varreduras": {}, "defeitos": {}, "midias": {}, "prazo": 0, "seq": 0}
D = SimpleNamespace()  # módulos do PCPR, depois do django.setup()


# ===================================================================== ambiente do PCPR


def ambiente_pcpr(tmp: Path) -> dict[str, str]:
    """Variáveis do PCPR real (runserver e esta suíte). Tudo que poderia apontar para um
    serviço real fica explicitamente vazio ou simulado (não depende de .env)."""
    return {
        "PYTHONUTF8": "1",
        "PYTHONUNBUFFERED": "1",
        "DJANGO_SETTINGS_MODULE": "config.settings.lab",
        "APP_ENV": "lab",
        "DJANGO_DEBUG": "false",
        "DJANGO_SECRET_KEY": SEGREDOS["django_secret"],
        "DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost,host.docker.internal",
        "DEMO_MODE": "false",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": str(PORTAS["postgres"]),
        "POSTGRES_USER": "pcpr",
        "POSTGRES_PASSWORD": "teste",
        "POSTGRES_DB": "pcpr",
        "URL_PUBLICA": PCPR,
        # automação: o n8n é o transporte; eventos assinados para o W1 do contêiner
        "AUTOMACAO_TRANSPORTE": "n8n",
        "N8N_EVENTOS_URL": f"{N8N}/webhook/pcpr-eventos",
        "N8N_EVENTOS_SEGREDO": SEGREDOS["hmac_eventos"],
        # WhatsApp "cloud_api" com valores FALSOS: liga a conferência X-Hub-Signature-256 do
        # webhook V2. A base da Graph API é fixa (graph.facebook.com) — a guarda de rede impede
        # qualquer chamada; quem fala com a Graph API (simulada) é o n8n.
        "WHATSAPP_MODO": "cloud_api",
        "WHATSAPP_PHONE_NUMBER_ID": NUMERO_ID,
        "WHATSAPP_WABA_ID": "200000000000002",
        "WHATSAPP_ACCESS_TOKEN": SEGREDOS["wa_token_falso_pcpr"],
        "WHATSAPP_APP_SECRET": SEGREDOS["wa_app_secret"],
        "WHATSAPP_VERIFY_TOKEN": SEGREDOS["wa_verify_token"],
        "WHATSAPP_LIMITE_POR_HORA": "1000",
        "WHATSAPP_MODELOS": f"viagens.diarias_liberadas={MODELO_AVISO}:pt_BR",
        "WHATSAPP_LISTA_FECHADA": "true",
        # nada real
        "IA_MODO": "simulado",
        "IA_API_KEY": "",
        "EMAIL_HOST": "",
        "EMAIL_HOST_USER": "",
        "EMAIL_HOST_PASSWORD": "",
        "NOTIFICACOES_POR_EMAIL": "false",
        "EPROTOCOLO_AMBIENTE": "simulado",
        "EPROTOCOLO_CLIENT_ID": "",
        "EPROTOCOLO_CLIENT_SECRET": "",
        "EPROTOCOLO_BASE_URL": "",
        "EPROTOCOLO_TOKEN_URL": "",
        "ROTAS_PROVEDOR": "estimativa",
        "ROTAS_CHAVE": "",
        "ROTAS_URL": "",
        # guarda de rede (sitecustomize): só 127.0.0.1/localhost resolvem
        "PCPR_GUARDA_REDE": "1",
        "PCPR_GUARDA_LOG": str(tmp / "guarda-rede.log"),
    }


def instalar_guarda() -> None:
    spec = importlib.util.spec_from_file_location("guarda_rede", GUARDA / "sitecustomize.py")
    modulo = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(modulo)  # type: ignore[union-attr]
    modulo.instalar()


def impressao_do_codigo() -> dict[str, Any]:
    """SHA-256 do código do PCPR que rodou (o worktree muda enquanto se trabalha nele)."""
    h = hashlib.sha256()
    n = 0
    for pasta in ("gestao/automacao", "gestao/integracoes/whatsapp"):
        for p in sorted((REPO / pasta).rglob("*.py")):
            if "tests" in p.parts:
                continue
            h.update(p.relative_to(REPO).as_posix().encode() + b"\0" + p.read_bytes())
            n += 1
    for extra in ("gestao/viagens/comunicacoes.py", "gestao/viagens/prestacao.py"):
        h.update((REPO / extra).read_bytes())
        n += 1
    commit = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    return {"sha256_codigo": h.hexdigest(), "arquivos": n, "commit_base": commit}


# ===================================================================== HTTP mínimo


def http(
    metodo: str, url: str, corpo: Any = None, cab: dict | None = None, timeout: float = 60
) -> tuple[int, Any]:
    dados = None
    cabecalhos = dict(cab or {})
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        cabecalhos.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=dados, headers=cabecalhos, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            bruto, status = resp.read(), resp.status
    except urllib.error.HTTPError as exc:
        bruto, status = exc.read(), exc.code
    except (urllib.error.URLError, OSError) as exc:  # fora do ar: status 0 (as asserções pegam)
        return 0, repr(exc)[:200]
    try:
        return status, json.loads(bruto) if bruto else None
    except ValueError:
        return status, bruto.decode("utf-8", "replace")


def http_bruto(
    metodo: str, url: str, corpo: bytes | None = None, cab: dict | None = None, timeout=60
) -> tuple[int, bytes, dict]:
    req = urllib.request.Request(url, data=corpo, headers=cab or {}, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def graph(caminho: str, corpo: Any = None) -> Any:
    st, b = http("POST" if corpo is not None else "GET", GRAPH + caminho, corpo, timeout=150)
    checar(st == 200, f"simulador Graph {caminho} → {st} {b}")
    return b


def gst() -> dict:
    return graph("/_sim/estado")


def espiao(caminho: str, corpo: Any = None) -> Any:
    st, b = http("POST" if corpo is not None else "GET", ESPIAO + caminho, corpo)
    checar(st == 200, f"espião {caminho} → {st} {b}")
    return b


def api(metodo: str, rota: str, corpo: Any = None, chave: str | None = None, **cab) -> tuple:
    """Chamada direta da suíte à API real (sem o espião), com o token de transporte."""
    h = {"Authorization": f"Bearer {SEGREDOS['token_api']}", **cab}
    if chave:
        h["Idempotency-Key"] = chave
    return http(metodo, API + rota, corpo, h)


def multipart(campos: dict[str, str], arquivos: dict[str, tuple[str, str, bytes]]) -> tuple:
    fronteira = "----pcprreal" + secrets.token_hex(8)
    partes = [
        f'--{fronteira}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        for k, v in campos.items()
    ]
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


# ===================================================================== asserções


class Falha(AssertionError):
    pass


class NaoAplicavel(Exception):
    def __init__(self, motivo: str, evidencia: dict | None = None) -> None:
        super().__init__(motivo)
        self.motivo, self.evidencia = motivo, evidencia or {}


def checar(cond: Any, msg: str) -> None:
    if not cond:
        raise Falha(msg)


def esperar(fn: Callable[[], Any], timeout: float, msg: str, intervalo: float = 0.3) -> Any:
    fim = time.time() + timeout
    while True:
        valor = fn()
        if valor:
            return valor
        if time.time() > fim:
            raise Falha(f"tempo esgotado ({timeout}s): {msg}")
        time.sleep(intervalo)


def assentar(segundos: float = 3.0) -> None:
    """Tempo para efeitos INDEVIDOS aparecerem antes de afirmar que não aconteceram."""
    time.sleep(segundos)


def defeito(cod: str, titulo: str, **detalhe: Any) -> str:
    E["defeitos"][cod] = {"titulo": titulo, **detalhe}
    return cod


# ===================================================================== worker (eventos etc.)


class Trabalhador(threading.Thread):
    """`processar_automacao` em laço (a mesma `rodada()` do comando): entrega eventos ao n8n,
    processa webhooks V2, vence reservas. Pode ser pausado para segurar eventos (T3, T4, T8)."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.parar = threading.Event()
        self.pausado = threading.Event()
        self.ocioso = threading.Event()
        self.erros: list[str] = []
        self.voltas = 0

    def run(self) -> None:
        from django.db import connection
        from gestao.automacao.management.commands.processar_automacao import rodada

        while not self.parar.is_set():
            if self.pausado.is_set():
                self.ocioso.set()
                time.sleep(0.1)
                continue
            self.ocioso.clear()
            try:
                n = rodada()
            except Exception as exc:
                self.erros.append(repr(exc)[:300])
                n = 0
            self.voltas += 1
            if n == 0:
                self.ocioso.set()
                time.sleep(0.3)
        connection.close()


def pausar() -> None:
    E["trabalhador"].pausado.set()
    time.sleep(0.2)
    esperar(lambda: E["trabalhador"].ocioso.is_set(), 30, "worker não pausou")


def retomar() -> None:
    E["trabalhador"].pausado.clear()


@contextlib.contextmanager
def worker_pausado():
    pausar()
    try:
        yield
    finally:
        retomar()


# ===================================================================== PCPR: cenário e consultas


def carregar_django() -> None:
    import django

    django.setup()
    from django.db import connection, transaction
    from django.test import override_settings
    from django.utils import timezone
    from gestao.automacao import chaves, comunicacoes, contatos, entrada, entrega, eventos
    from gestao.automacao.api import credenciais
    from gestao.automacao.models import (
        ChaveAutomacao,
        Comunicacao,
        ContatoVerificado,
        EntradaWebhook,
        ExcecaoAutomacao,
        Recebimento,
        StatusEntrega,
        TentativaEntrega,
    )
    from gestao.automacao.models_api import EventoIntegracao, RegistroIdempotencia
    from gestao.viagens import comunicacoes as vcom
    from gestao.viagens import prestacao

    # explícito (não `locals()`): o linter não pode tirar o que só a suíte usa por `D.`
    D.__dict__.update(
        connection=connection,
        transaction=transaction,
        override_settings=override_settings,
        timezone=timezone,
        chaves=chaves,
        comunicacoes=comunicacoes,
        contatos=contatos,
        entrada=entrada,
        entrega=entrega,
        eventos=eventos,
        credenciais=credenciais,
        ChaveAutomacao=ChaveAutomacao,
        Comunicacao=Comunicacao,
        ContatoVerificado=ContatoVerificado,
        EntradaWebhook=EntradaWebhook,
        ExcecaoAutomacao=ExcecaoAutomacao,
        Recebimento=Recebimento,
        StatusEntrega=StatusEntrega,
        TentativaEntrega=TentativaEntrega,
        EventoIntegracao=EventoIntegracao,
        RegistroIdempotencia=RegistroIdempotencia,
        vcom=vcom,
        prestacao=prestacao,
        S=Comunicacao.Situacao,
    )


def montar_cenario() -> dict[str, Any]:
    """Cenário sintético pelos serviços do PCPR: ofício emitido com 2 servidores (o
    `cenario_completo` dos testes), telefones fictícios de DDD 23 (não existe no Brasil),
    contatos verificados com opt-in, ambos na lista de testadores do LAB, chaves ligadas e a
    credencial de transporte do n8n."""
    from django.contrib.auth.models import Group
    from gestao.identidade.models import Usuario
    from gestao.viagens.models import PrestacaoServidor
    from gestao.viagens.tests.cenarios import cenario_completo

    with D.transaction.atomic():
        cen = cenario_completo()
        admin = Usuario.objects.create_user(
            "admin-auto",
            "admin-auto@example.invalid",
            secrets.token_urlsafe(16),
            nome="Administração da automação (teste)",
        )
        admin.groups.add(Group.objects.get(name="ADMINISTRADOR"))
    op = cen.usuarios["operador"]
    pss = list(
        PrestacaoServidor.objects.filter(prestacao__oficio_id=cen.ids["oficio_emitido"])
        .select_related("servidor")
        .order_by("servidor__nome")
    )
    checar(len(pss) == 2, f"cenário com {len(pss)} prestações (esperado 2)")
    telefones = []
    for i, ps in enumerate(pss):
        ps.servidor.telefone = f"2399999{i + 1:04d}"  # DDD 23 não existe
        ps.servidor.save(update_fields=["telefone"])
    for nome in (D.chaves.GERAL, D.chaves.nome_canal("whatsapp")):
        D.chaves.alterar(admin, nome, estado="ligada")
    D.chaves.alterar(
        admin, D.chaves.nome_fluxo("diarias_liberadas"), estado="ligada", modo="automatico"
    )
    contatos_ids = []
    for i, ps in enumerate(pss):
        c = D.contatos.cadastrar(op, ps.servidor_id)
        D.contatos.confirmar_numero(op, c.pk)
        D.contatos.registrar_optin(op, c.pk, D.ContatoVerificado.OrigemOptin.FORMULARIO)
        D.contatos.autorizar_testador(admin, c.endereco, f"Testador sintético {i + 1}")
        contatos_ids.append(c.pk)
        telefones.append(c.endereco)
    # todos os escopos de transporte: a entrada V1 (`recebimentos:criar`) ficou fora do padrão
    # do PCPR e precisa ser pedida explicitamente
    cred, token = D.credenciais.emitir(
        admin,
        nome="n8n · teste local",
        tipo="transporte",
        dias=1,
        escopos=list(D.credenciais.ESCOPOS_TRANSPORTE),
    )
    SEGREDOS["token_api"] = token
    E.update(
        admin=admin,
        op=op,
        pss=[p.pk for p in pss],
        servidores=[p.servidor_id for p in pss],
        telefones=telefones,
        contatos=contatos_ids,
        credencial=cred.pk,
        outros_servidores=[s.pk for s in cen_servidores_livres(pss)],
    )
    return {
        "prestacoes": len(pss),
        "telefones": telefones,
        "credencial": {
            "tipo": cred.tipo,
            "escopos": cred.escopos,
            "prefixo": f"<opaco: {token[:9]}…>",
        },
    }


def cen_servidores_livres(pss) -> list:
    from gestao.cadastros.models import Servidor

    usados = {p.servidor_id for p in pss}
    return list(Servidor.objects.exclude(pk__in=usados).order_by("pk")[:4])


def ligar(fluxo: str, ligado: bool = True, modo: str = "automatico") -> None:
    D.chaves.alterar(
        E["admin"],
        D.chaves.nome_fluxo(fluxo),
        estado="ligada" if ligado else "desligada",
        modo=modo,
    )


def chave(nome: str, estado: str) -> None:
    D.chaves.alterar(E["admin"], nome, estado=estado)


def nova_comunicacao(i: int) -> int:
    """Um aviso de diárias novo pelo caminho de negócio (`prestacao.salvar_solicitacao`): cada
    prazo novo é uma versão nova da liberação e agenda uma comunicação nova (a anterior, se
    ainda não saiu, fica obsoleta no envio)."""
    E["prazo"] += 1
    ps = E["pss"][i]
    recurso = f"{D.vcom.RECURSO}:{ps}"
    antes = set(D.Comunicacao.objects.filter(recurso=recurso).values_list("pk", flat=True))
    hoje = D.timezone.localdate()
    D.prestacao.salvar_solicitacao(
        E["op"], ps, numero="2026/0001", liberacao=hoje, prazo=hoje + timedelta(days=E["prazo"])
    )
    nova = D.Comunicacao.objects.filter(recurso=recurso).exclude(pk__in=antes)
    checar(nova.count() == 1, f"esperada 1 comunicação nova para a prestação {ps}")
    return nova.get().pk


def agendar(tipo: str, servidor_id: int, quando=None, i_ps: int | None = None) -> int:
    """Agenda pelo serviço da automação (o mesmo que a prestação usa por baixo)."""
    E["seq"] += 1
    contexto: dict[str, Any] = {}
    versao = ""
    recurso = f"teste.pcpr-real:{E['seq']}"
    if i_ps is not None:
        from gestao.viagens.models import PrestacaoServidor

        ps = PrestacaoServidor.objects.get(pk=E["pss"][i_ps])
        contexto, versao, recurso = {"ps": ps.pk}, D.vcom.versao(ps), f"{D.vcom.RECURSO}:{ps.pk}"
    with D.transaction.atomic():
        c = D.comunicacoes.agendar(
            tipo=tipo,
            servidor_id=servidor_id,
            recurso=recurso,
            chave=f"pcpr-real:{tipo}:{E['seq']}:{secrets.token_hex(3)}",
            criada_por=E["op"],
            contexto=contexto,
            versao=versao,
            agendada_para=quando,
        )
    return c.pk


def com(cid: int) -> dict[str, Any]:
    c = D.Comunicacao.objects.get(pk=cid)
    return {
        "situacao": c.situacao,
        "revisao": c.revisao,
        "entrega": c.entrega,
        "tentativas": c.tentativas,
        "mensagem_id": c.mensagem_id,
        "motivo": c.motivo,
        "proxima_tentativa_em": c.proxima_tentativa_em,
        "reservada_ate": c.reservada_ate,
        "entregue_em": c.entregue_em,
        "lida_em": c.lida_em,
        "enviada_em": c.enviada_em,
    }


def esperar_situacao(cid: int, situacoes: tuple[str, ...], timeout: float = 60) -> dict:
    try:
        return esperar(lambda: (x := com(cid))["situacao"] in situacoes and x, timeout, "")
    except Falha:
        raise Falha(f"comunicação {cid} não chegou a {situacoes}: {diagnostico(cid)}") from None


def diagnostico(cid: int) -> dict:
    """O que se sabe de uma comunicação parada (para o relatório de falha)."""
    ev = evento_de(cid)
    c = com(cid)
    with contextlib.suppress(Exception):
        log = [
            (x["metodo"], x["rota"], x["status"], x.get("codigo"))
            for x in elog()
            if x.get("comunicacao_id") == cid or x["rota"] == "/estado"
        ][-8:]
    return {
        "situacao": c["situacao"],
        "tentativas": c["tentativas"],
        "motivo": c["motivo"],
        "evento": ev
        and {"situacao": ev.situacao, "tentativas": ev.tentativas, "ultimo_erro": ev.ultimo_erro},
        "worker_pausado": E["trabalhador"].pausado.is_set(),
        "chamadas": locals().get("log"),
        "graph": len(msgs_de(cid)),
    }


def excecoes_de(cid: int) -> list[dict]:
    return [
        {"tipo": x.tipo, "chave": x.chave[:80], "situacao": x.situacao}
        for x in D.ExcecaoAutomacao.objects.filter(comunicacao_id=cid).order_by("pk")
    ]


def evento_de(cid: int) -> Any:
    return (
        D.EventoIntegracao.objects.filter(
            tipo="comunicacao.agendada", corpo__dados__comunicacao_id=cid
        )
        .order_by("pk")
        .first()
    )


def limpar_pendentes() -> int:
    """Entre cenários: o que ficou agendado é cancelado por uma pessoa (serviço da tela)."""
    n = 0
    for c in D.Comunicacao.objects.filter(situacao__in=(D.S.AGENDADA, D.S.AGUARDANDO_APROVACAO)):
        D.comunicacoes.cancelar(E["admin"], c.pk, "limpeza entre cenários do teste")
        n += 1
    return n


def avancar_relogio(cid: int, campo: str) -> dict[str, str]:
    """Simula a passagem do tempo no banco descartável (ver docstring do módulo)."""
    c = D.Comunicacao.objects.get(pk=cid)
    antes = getattr(c, campo)
    agora = D.timezone.now() - timedelta(seconds=1)
    D.Comunicacao.objects.filter(pk=cid).update(**{campo: agora})
    return {"campo": campo, "era": antes.isoformat() if antes else None, "virou": agora.isoformat()}


# ===================================================================== eventos


def reentregar(cid: int, vezes: int = 1, paralelo: bool = False) -> list[int]:
    """Entrega de novo o evento `comunicacao.agendada` guardado, pelo emissor REAL
    (`eventos.entregar`: mesma assinatura, mesmo corpo, mesmo `X-PCPR-Evento-Id`)."""
    statuses: list[int] = []
    trava = threading.Lock()
    uid = evento_de(cid).uuid

    def postar(url, corpo, cab):
        st = D.eventos._postar(url, corpo, cab)
        with trava:
            statuses.append(st)
        return st

    def um() -> None:
        try:
            D.eventos.entregar(D.EventoIntegracao.objects.get(uuid=uid), postar)
        finally:
            if threading.current_thread() is not threading.main_thread():
                D.connection.close()

    if paralelo:
        with concurrent.futures.ThreadPoolExecutor(max_workers=vezes) as ex:
            list(ex.map(lambda _: um(), range(vezes)))
    else:
        for _ in range(vezes):
            um()
    return statuses


def corpo_do_evento(cid: int) -> dict:
    return json.loads(json.dumps(evento_de(cid).corpo))


def postar_envelope(
    corpo: bytes,
    *,
    segredo: str | None = None,
    t: int | None = None,
    evento_id: str | None = None,
    assinatura: str | None = "auto",
) -> int:
    """O papel do emissor, para envelopes adulterados (T3)."""
    cab = {"Content-Type": "application/json"}
    if evento_id is not None:
        cab["X-PCPR-Evento-Id"] = evento_id
    if assinatura == "auto":
        tt = str(int(time.time()) if t is None else t)
        mac = hmac.new(
            (segredo or SEGREDOS["hmac_eventos"]).encode(),
            tt.encode() + b"." + corpo,
            hashlib.sha256,
        ).hexdigest()
        cab["X-PCPR-Assinatura"] = f"t={tt},v1={mac}"
    elif assinatura:
        cab["X-PCPR-Assinatura"] = assinatura
    st, _, _ = http_bruto("POST", f"{N8N}/webhook/pcpr-eventos", corpo, cab)
    return st


def bytes_do_envelope(env: dict) -> bytes:
    return json.dumps(env, ensure_ascii=False, separators=(",", ":")).encode()


def reconciliar() -> tuple[int, Any]:
    return http(
        "POST",
        f"{N8N}/webhook/pcpr-reconciliar",
        {},
        {"X-Disparo-Token": SEGREDOS["disparo"]},
        timeout=180,
    )


def validar_envelopes(envelopes: list[dict]) -> dict[str, list[str]]:
    schema = json.loads(SCHEMA_EVENTOS.read_text(encoding="utf-8"))
    return {
        f"{ev['tipo']}#{i}": erros
        for i, ev in enumerate(envelopes)
        if (erros := validar(ev, schema))
    }


# ===================================================================== espião e Graph


def elog() -> list[dict]:
    return espiao("/_espiao/log")


def chamadas(
    log: list[dict], padrao: str, cid: int | None = None, metodo: str | None = None
) -> list[dict]:
    return [
        r
        for r in log
        if re.fullmatch(padrao, r["rota"])
        and (cid is None or r.get("comunicacao_id") == cid)
        and (metodo is None or r["metodo"] == metodo)
    ]


def acumular_midias() -> None:
    with contextlib.suppress(Exception):
        for mid, m in gst()["midias"].items():
            E["midias"].setdefault(m["fase"], set()).add(mid)


def resetar_graph(variante: str = "V2") -> None:
    acumular_midias()
    graph("/_sim/resetar", {})
    graph(
        "/_sim/templates",
        {"nome": MODELO_AVISO, "status": "APPROVED", "idioma": "pt_BR", "parametros": 4},
    )
    # A "Meta" simulada zera as janelas de 24 h; o PCPR real lembra quem escreveu. Sem isto o
    # PCPR mandaria texto livre (janela aberta para ele) e o simulador recusaria com 131047.
    if hasattr(D, "ContatoVerificado"):
        for c in D.ContatoVerificado.objects.exclude(ultima_mensagem_em=None):
            graph(
                "/_sim/janela", {"wa_id": c.endereco, "ultima_em": c.ultima_mensagem_em.timestamp()}
            )
    usar(variante)


def usar(variante: str) -> None:
    graph(
        "/_sim/config",
        {
            "callback_url": CALLBACK[variante],
            "base_midia_webhook": BASE_MIDIA[variante],
            "modo_131047": "sincrono",
            "url_ttl_s": 300,
            "recusas_temporarias": 0,
            "atraso_envio_s": 0,
            "respostas_ambiguas": 0,
        },
    )


def msgs_de(cid: int, g: dict | None = None) -> list[dict]:
    g = g or gst()
    return [
        m
        for m in g["mensagens"]
        if str(m.get("biz_opaque_callback_data") or "").startswith(f"com:{cid}:")
    ]


def aceitas(cid: int, g: dict | None = None) -> list[dict]:
    return [m for m in msgs_de(cid, g) if m.get("aceita")]


def preparar_cenario(variante: str = "V2") -> None:
    """Começo de cada cenário: nada pendente, Graph API zerada, log do espião limpo."""
    retomar()
    limpar_pendentes()
    resetar_graph(variante)
    espiao("/_espiao/limpar", {})


def recebimentos_de(wamid: str) -> list:
    return list(D.Recebimento.objects.filter(mensagem_id=wamid).order_by("pk"))


# ===================================================================== cenários T


def tw0() -> dict:
    """Pré-condição: o simulador aplica as regras (senão um envio 'passando' não prova nada)."""
    preparar_cenario()
    a = {"Authorization": f"Bearer {SEGREDOS['wa_token_graph_sim']}"}
    url = f"{GRAPH}/v21.0/{NUMERO_ID}/messages"
    para = "5523999990099"
    texto = {"messaging_product": "whatsapp", "to": para, "type": "text", "text": {"body": "x"}}
    sem, b1 = http("POST", url, texto)
    fora, b2 = http("POST", url, texto, a)
    modelo = {
        "messaging_product": "whatsapp",
        "to": para,
        "type": "template",
        "template": {
            "name": MODELO_AVISO,
            "language": {"code": "pt_BR"},
            "components": [
                {"type": "body", "parameters": [{"type": "text", "text": str(i)} for i in range(4)]}
            ],
        },
    }
    ok, b3 = http("POST", url, modelo, a)
    graph("/_sim/templates", {"nome": "pcpr_pendente_v1", "status": "PENDING", "parametros": 0})
    pend, b4 = http(
        "POST",
        url,
        {**modelo, "template": {"name": "pcpr_pendente_v1", "language": {"code": "pt_BR"}}},
        a,
    )
    checar(sem == 401 and b1["error"]["code"] == 190, f"sem Bearer: {sem} {b1}")
    checar(fora == 400 and b2["error"]["code"] == 131047, f"fora da janela: {fora} {b2}")
    checar(ok == 200 and b3["messages"][0]["id"].startswith("wamid."), f"modelo: {ok} {b3}")
    checar(pend in (400, 404) and b4["error"]["code"] == 132001, f"pendente: {pend} {b4}")
    return {
        "sem_bearer": [sem, 190],
        "texto_fora_da_janela": [fora, 131047],
        "modelo_aprovado": [ok, "wamid"],
        "modelo_pendente": [pend, 132001],
    }


def t1() -> dict:
    preparar_cenario()
    cid = nova_comunicacao(0)
    esperar_situacao(cid, (D.S.ENVIADA,))
    assentar()
    log, g, c = elog(), gst(), com(cid)
    envios = aceitas(cid, g)
    reservas = [x for x in chamadas(log, r"/comunicacoes/\d+/reservar", cid) if x["status"] == 200]
    resultados = [
        x
        for x in chamadas(log, r"/comunicacoes/\d+/resultado", cid)
        if x["status"] == 200 and not x.get("replay")
    ]
    ev = evento_de(cid)
    checar(len(envios) == 1, f"esperado 1 envio na Graph API, houve {len(envios)}")
    checar(len(reservas) == 1, f"esperada 1 reserva 200, houve {reservas}")
    checar(len(resultados) == 1, f"esperado 1 resultado, houve {resultados}")
    checar(c["mensagem_id"] == envios[0]["wamid"], "wamid não registrado como provedor_mensagem_id")
    checar(
        ev.situacao == "entregue" and ev.tentativas == 1, f"evento: {ev.situacao}/{ev.tentativas}"
    )
    m = envios[0]
    E["t1"] = {"cid": cid}
    # envelopes REAIS emitidos (agendada + religada da montagem) contra o esquema do contrato
    envelopes = [
        json.loads(json.dumps(e.corpo))
        for e in D.EventoIntegracao.objects.filter(
            tipo__in=("comunicacao.agendada", "automacao.religada")
        ).order_by("pk")[:3]
    ]
    erros = validar_envelopes(envelopes)
    evid = {
        "comunicacao_id": cid,
        "evento": {"tipo": ev.tipo, "situacao": ev.situacao, "tentativas": ev.tentativas},
        "reservas": len(reservas),
        "chave_idempotencia_reserva": reservas[0]["chave"],
        "versao_esperada_enviada": reservas[0]["versao_esperada"],
        "resultados_registrados": len(resultados),
        "envios_na_graph_api": len(envios),
        "mensagem": {
            "tipo": m["tipo"],
            "modelo": m.get("template"),
            "parametros": len(m.get("parametros") or []),
            "biz_opaque_callback_data": m.get("biz_opaque_callback_data"),
        },
        "estado_final": c["situacao"],
        "provedor_mensagem_id_registrado": True,
        "envelopes_validados": [e["tipo"] for e in envelopes],
        "erros_de_esquema": erros,
        "dados_da_agendada": next(
            e["dados"] for e in envelopes if e["tipo"] == "comunicacao.agendada"
        ),
    }
    if erros:
        cod = defeito(
            "D1",
            "Envelopes de evento emitidos pelo PCPR real não validam contra "
            "evento-integracao.schema.json",
            requisicao="POST {N8N_EVENTOS_URL} (emissor gestao.automacao.eventos)",
            resposta=erros,
            contrato="evento-integracao.schema.json: $defs/dados.comunicacao.agendada "
            "(fluxo ^[a-z0-9-]{1,64}$; tipo_comunicacao enum do contrato) e "
            "$defs/dados.automacao.religada (required: fluxo; additionalProperties: false); "
            "recurso.tipo enum",
            esperado="dados.fluxo com hífen (ex.: diarias-liberadas), tipo_comunicacao no "
            "vocabulário do contrato (mensagem_saque), dados.fluxo nulo na chave geral",
        )
        evid["defeito"] = cod
        E["t1"]["evid"] = evid
        raise Falha(f"fluxo OK, mas os envelopes reais violam o esquema ({cod}): {erros}")
    return evid


def t2() -> dict:
    if "t1" not in E:  # rodando sozinho (--apenas T2)
        with contextlib.suppress(Falha):
            t1()
    checar("t1" in E, "T2 depende do T1")
    cid = E["t1"]["cid"]
    espiao("/_espiao/limpar", {})
    # (a) o MESMO evento (mesmo id e bytes) reentregue 2x em série pelo emissor real
    respostas = reentregar(cid, 2)
    assentar(4)
    novas = chamadas(elog(), r"/comunicacoes/\d+/.*", cid)
    checar(respostas == [202, 202], f"reentrega deveria receber 202: {respostas}")
    checar(len(aceitas(cid)) == 1, "reentrega gerou envio")
    checar(not novas, f"reentrega chegou ao PCPR (dedup do n8n): {novas}")
    # (b) o mesmo evento 5x em paralelo
    with worker_pausado():
        cid2 = nova_comunicacao(1)
        paralelas = reentregar(cid2, 5, paralelo=True)
    esperar(lambda: len(aceitas(cid2)) == 1, 60, "entrega paralela não enviou")
    assentar(4)
    log = elog()
    reservas = chamadas(log, r"/comunicacoes/\d+/reservar", cid2)
    checar(len(aceitas(cid2)) == 1, f"paralelo gerou {len(aceitas(cid2))} envios")
    checar(sum(1 for x in reservas if x["status"] == 200) == 1, f"reservas: {reservas}")
    # (c) evento com OUTRO id para a mesma comunicação (a dedup do n8n não pega)
    env = corpo_do_evento(cid2)
    env["id"] = str(uuid.uuid4())
    n_res = len(reservas)
    st_c = postar_envelope(bytes_do_envelope(env), evento_id=env["id"])
    esperar(
        lambda: len(chamadas(elog(), r"/comunicacoes/\d+/reservar", cid2)) > n_res,
        60,
        "evento com outro id não chegou ao reservar",
    )
    assentar(3)
    extra = chamadas(elog(), r"/comunicacoes/\d+/reservar", cid2)[n_res:]
    checar([x["status"] for x in extra] == [409], f"outro id deveria levar 409: {extra}")
    checar(len(aceitas(cid2)) == 1, "evento com outro id gerou segundo envio")
    return {
        "a_reentregas_em_serie": {
            "respostas_n8n": respostas,
            "chamadas_novas_ao_pcpr": 0,
            "envios": 1,
        },
        "b_cinco_simultaneas": {
            "respostas_n8n": sorted(paralelas),
            "execucoes_que_tentaram_reservar": len(reservas),
            "reservas_por_status": {
                str(s): sum(1 for x in reservas if x["status"] == s)
                for s in sorted({x["status"] for x in reservas})
            },
            "codigos_409": sorted({x.get("codigo") for x in reservas if x["status"] == 409}),
            "envios": 1,
        },
        "c_outro_id_mesma_comunicacao": {
            "resposta_n8n": st_c,
            "reserva": [409],
            "codigo": extra[0].get("codigo"),
            "envios": 1,
        },
    }


def t3() -> dict:
    preparar_cenario()
    with worker_pausado():
        cid = nova_comunicacao(0)
        env = corpo_do_evento(cid)
        corpo = bytes_do_envelope(env)
        eid = env["id"]
        outro_amb = dict(env, ambiente="producao")
        respostas = {
            "segredo_errado": postar_envelope(corpo, segredo="errado" * 8, evento_id=eid),
            "t_de_10_min_atras": postar_envelope(corpo, t=int(time.time()) - 600, evento_id=eid),
            "sem_assinatura": postar_envelope(corpo, evento_id=eid, assinatura=None),
            "ambiente_producao": postar_envelope(bytes_do_envelope(outro_amb), evento_id=eid),
            "evento_id_divergente": postar_envelope(corpo, evento_id=str(uuid.uuid4())),
        }
        # corpo alterado: assinado o original, enviado com 1 espaço a mais
        assin = _assinar(corpo)
        st_alt, _, _ = http_bruto(
            "POST",
            f"{N8N}/webhook/pcpr-eventos",
            corpo + b" ",
            {
                "Content-Type": "application/json",
                "X-PCPR-Evento-Id": eid,
                "X-PCPR-Assinatura": assin,
            },
        )
        respostas["corpo_alterado_depois_de_assinado"] = st_alt
        assentar(4)
        checar(all(s == 401 for s in respostas.values()), f"esperado 401 em todos: {respostas}")
        checar(not chamadas(elog(), r"/comunicacoes/\d+/reservar", cid), "inválido chegou ao PCPR")
        checar(not msgs_de(cid), "houve envio com evento inválido")
        checar(com(cid)["situacao"] == D.S.AGENDADA, "comunicação mudou de estado")
        # (e) o EMISSOR REAL com o segredo errado: o n8n responde 401 e o PCPR não repete;
        # vira falha de configuração + exceção (eventos.entregar)
        with D.override_settings(N8N_EVENTOS_SEGREDO="segredo-errado-de-proposito-" + "x" * 16):
            ev = D.EventoIntegracao.objects.get(uuid=eid)
            situacao_401 = D.eventos.entregar(ev)
        ev.refresh_from_db()
        exc_cfg = D.ExcecaoAutomacao.objects.filter(chave="eventos-n8n:401").exists()
        checar(
            situacao_401 == "configuracao" and ev.situacao == "configuracao",
            f"emissor real com segredo errado: {situacao_401}/{ev.situacao}",
        )
        checar(exc_cfg, "o PCPR não abriu exceção de configuração (eventos-n8n:401)")
    # (f) controle positivo: o mesmo evento, pelo emissor real com o segredo certo
    ok = reentregar(cid, 1)
    esperar(lambda: len(aceitas(cid)) == 1, 60, "controle positivo não enviou")
    # (g) UTF-8 no corpo bruto, num campo do contrato (correlacao_id): bytes UTF-8 → 202;
    # assinado sobre a re-serialização com escapes ASCII → 401
    env2 = dict(env, id=str(uuid.uuid4()), correlacao_id="com-véspera-ação-T3")
    utf8 = bytes_do_envelope(env2)
    ascii_ = json.dumps(env2, ensure_ascii=True, separators=(",", ":")).encode()
    tt = str(int(time.time()))
    mac_ascii = hmac.new(
        SEGREDOS["hmac_eventos"].encode(), tt.encode() + b"." + ascii_, hashlib.sha256
    ).hexdigest()
    st_ascii = postar_envelope(utf8, evento_id=env2["id"], assinatura=f"t={tt},v1={mac_ascii}")
    st_utf8 = postar_envelope(utf8, evento_id=env2["id"])
    checar(st_ascii == 401 and st_utf8 == 202, f"UTF-8: ascii {st_ascii}, utf8 {st_utf8}")
    assentar(3)
    checar(len(aceitas(cid)) == 1, "o envelope UTF-8 (mesma comunicação) gerou 2º envio")
    return {
        "respostas_invalidas": respostas,
        "envios_com_eventos_invalidos": 0,
        "e_emissor_real_com_segredo_errado": {
            "situacao_do_evento": ev.situacao,
            "excecao_eventos_n8n_401": exc_cfg,
            "repete": False,
        },
        "f_controle_positivo_emissor_real": {"status": ok, "envios": 1},
        "g_utf8": {
            "assinado_sobre_reserializacao_ascii": st_ascii,
            "assinado_sobre_bytes_utf8": st_utf8,
        },
    }


def _assinar(corpo: bytes) -> str:
    tt = str(int(time.time()))
    mac = hmac.new(
        SEGREDOS["hmac_eventos"].encode(), tt.encode() + b"." + corpo, hashlib.sha256
    ).hexdigest()
    return f"t={tt},v1={mac}"


def t4() -> dict:
    preparar_cenario()
    # (a) a liberação mudou (versão nova) antes de o evento antigo chegar (fora de ordem)
    with worker_pausado():
        c1 = nova_comunicacao(0)
        c2 = nova_comunicacao(0)  # outro prazo → a c1 perde a validade
        st_antigo = reentregar(c1, 1)
        esperar(
            lambda: chamadas(elog(), r"/comunicacoes/\d+/reservar", c1),
            60,
            "W2 não tentou reservar a comunicação antiga",
        )
    esperar(lambda: len(aceitas(c2)) == 1, 60, "a versão nova não saiu")
    assentar()
    res1 = chamadas(elog(), r"/comunicacoes/\d+/reservar", c1)
    checar([x["status"] for x in res1] == [409], f"reserva antiga deveria ser 409: {res1}")
    checar(res1[0].get("codigo") == "obsoleta", f"código {res1[0].get('codigo')}")
    checar(not msgs_de(c1), "a versão antiga foi enviada")
    checar(com(c1)["situacao"] == D.S.OBSOLETA, f"c1 {com(c1)['situacao']}")
    # (a2) agendada para daqui a 3 dias: o W1 não antecipa (evento sem `imediato`)
    futura = agendar(
        D.vcom.AVISO, E["servidores"][1], quando=D.timezone.now() + timedelta(days=3), i_ps=1
    )
    esperar(
        lambda: (e := evento_de(futura)) and e.situacao == "entregue",
        60,
        "evento da futura não entregue",
    )
    assentar(4)
    checar(not chamadas(elog(), r"/comunicacoes/\d+/reservar", futura), "reservou antes da hora")
    _st_dev, dev = api("GET", "/comunicacoes/devidas")
    checar(futura not in [x["id"] for x in dev["itens"]], "a futura apareceu nas devidas")
    # (b) evento com versão antiga: modo assistido → aprovação humana (revisão 2) → evento v1
    with worker_pausado():
        c3 = nova_comunicacao(1)
        ligar("diarias_liberadas", modo="assistido")
        st_r, corpo_r = reconciliar()  # o W2 tenta, o PCPR põe em "aguardando aprovação"
        esperar(
            lambda: com(c3)["situacao"] == D.S.AGUARDANDO_APROVACAO,
            60,
            "não foi para aguardando aprovação",
        )
        D.comunicacoes.aprovar(E["admin"], c3)
        ligar("diarias_liberadas", modo="automatico")
        checar(com(c3)["revisao"] == 2, f"revisão depois de aprovar: {com(c3)['revisao']}")
        n_antes = len(chamadas(elog(), r"/comunicacoes/\d+/reservar", c3))
        st_v1 = reentregar(c3, 1)
        esperar(
            lambda: len(chamadas(elog(), r"/comunicacoes/\d+/reservar", c3)) > n_antes,
            60,
            "evento v1 não chegou ao reservar",
        )
    assentar(2)
    res3 = chamadas(elog(), r"/comunicacoes/\d+/reservar", c3)[n_antes:]
    checar(
        res3 and res3[0]["status"] == 409 and res3[0].get("codigo") == "conflito_de_versao",
        f"esperado 409 conflito_de_versao: {res3}",
    )
    checar(not msgs_de(c3), "versão antiga enviada")
    st_rec, rec = reconciliar()  # a v2 sai pela reconciliação (versao=2 nas devidas)
    esperar(lambda: len(aceitas(c3)) == 1, 60, "versão atual não foi enviada")
    reserva_v2 = [
        x for x in chamadas(elog(), r"/comunicacoes/\d+/reservar", c3) if x["status"] == 200
    ]
    return {
        "a_versao_nova_da_liberacao": {
            "comunicacao_antiga": c1,
            "resposta_n8n": st_antigo,
            "reserva": [409],
            "codigo": "obsoleta",
            "estado_antiga": com(c1)["situacao"],
            "envios_antiga": 0,
            "comunicacao_nova": c2,
            "envios_nova": 1,
        },
        "a2_futura_nao_antecipada": {
            "comunicacao": futura,
            "reservas": 0,
            "nas_devidas": False,
            "estado": com(futura)["situacao"],
        },
        "b_versao_antiga_depois_de_aprovacao": {
            "comunicacao": c3,
            "reconciliacao_assistido": [st_r, corpo_r],
            "revisao_apos_aprovar": 2,
            "evento_v1": st_v1,
            "reserva_v1": [res3[0]["status"], res3[0].get("codigo")],
            "reconciliacao": [st_rec, rec],
            "reserva_v2_versao_esperada": reserva_v2[0]["versao_esperada"],
            "envios_v2": 1,
        },
    }


def t5() -> dict:
    preparar_cenario()
    # (a) chave geral desligada antes: W2 lê /estado e encerra sem reservar
    chave(D.chaves.GERAL, "desligada")
    ca = nova_comunicacao(0)
    esperar(lambda: any(x["rota"] == "/estado" for x in elog()), 60, "W2 não leu /estado")
    assentar()
    checar(not chamadas(elog(), r"/comunicacoes/\d+/reservar", ca), "reservou desligada")
    checar(com(ca)["situacao"] == D.S.AGENDADA, "deveria continuar agendada")
    # (b) geral ligada e CANAL desligado: /estado diz "ligada", o reservar recusa com 423
    chave(D.chaves.nome_canal("whatsapp"), "desligada")
    chave(D.chaves.GERAL, "ligada")
    cb = nova_comunicacao(1)
    esperar(lambda: chamadas(elog(), r"/comunicacoes/\d+/reservar", cb), 60, "W2 não reservou")
    assentar()
    resb = chamadas(elog(), r"/comunicacoes/\d+/reservar", cb)
    _st_estado, estado = api("GET", "/estado")
    checar([x["status"] for x in resb] == [423], f"esperado 423: {resb}")
    checar(not msgs_de(ca) and not msgs_de(cb), "houve envio com a automação desligada")
    checar(com(cb)["situacao"] == D.S.AGENDADA, "deveria continuar agendada após 423")
    guardado = D.RegistroIdempotencia.objects.filter(chave=resb[0]["chave"]).exists()
    checar(not guardado, "a resposta 423 foi guardada pela idempotência (contrato: não guarda)")
    # (c) religado: a reconciliação entrega as duas, uma vez cada
    chave(D.chaves.nome_canal("whatsapp"), "ligada")
    st, corpo = reconciliar()
    checar(st == 200, f"reconciliação → {st} {corpo}")
    esperar(lambda: len(aceitas(ca)) == 1 and len(aceitas(cb)) == 1, 60, "não saíram")
    assentar()
    checar(len(aceitas(ca)) == 1 and len(aceitas(cb)) == 1, "deveria sair 1x cada")
    return {
        "a_geral_desligada": {"comunicacao": ca, "reservas": 0, "estado": "agendada"},
        "b_canal_desligado": {
            "comunicacao": cb,
            "estado_api": {
                "ligada": estado["ligada"],
                "canais.whatsapp": estado["canais"]["whatsapp"],
            },
            "reserva": [423],
            "codigo": resb[0].get("codigo"),
            "423_guardado": False,
            "estado": "agendada",
            "envios": 0,
        },
        "c_religada": {"reconciliacao": corpo, "envios": {str(ca): 1, str(cb): 1}},
    }


def t7() -> dict:
    """Adaptado: a recusa vem da Graph API (erro estruturado temporário), não do canal genérico.
    O W6 não repete o POST /messages; a rodada seguinte é do PCPR (espera 2, 8 min)."""
    preparar_cenario()
    graph("/_sim/config", {"recusas_temporarias": 99})
    cid = nova_comunicacao(0)
    rodadas = []
    for r in range(1, 4):
        if r > 1:
            rel = avancar_relogio(cid, "proxima_tentativa_em")
            _st, _corpo = reconciliar()
            rodadas[-1]["relogio_avancado"] = rel
        esperar(
            lambda r=r: (
                com(cid)["tentativas"] == r and com(cid)["situacao"] in (D.S.AGENDADA, D.S.FALHOU)
            ),
            60,
            f"rodada {r} não terminou",
        )
        c = com(cid)
        espera_s = round((c["proxima_tentativa_em"] - D.timezone.now()).total_seconds())
        rodadas.append(
            {
                "rodada": r,
                "estado": c["situacao"],
                "tentativas": c["tentativas"],
                "proxima_em_s": espera_s if c["situacao"] == D.S.AGENDADA else None,
            }
        )
    assentar()
    exc = excecoes_de(cid)
    _st, corpo = reconciliar()
    assentar()
    _st_dev, dev = api("GET", "/comunicacoes/devidas")
    g = gst()
    tentativas_graph = msgs_de(cid, g)
    checar(
        [x["estado"] for x in rodadas] == [D.S.AGENDADA, D.S.AGENDADA, D.S.FALHOU],
        f"rodadas {rodadas}",
    )
    checar(
        len(tentativas_graph) == 3 and not any(m["aceita"] for m in tentativas_graph),
        f"tentativas na Graph API: {len(tentativas_graph)}",
    )
    checar(len(exc) == 1, f"esperada 1 exceção (do PCPR), houve {exc}")
    checar(cid not in [x["id"] for x in dev["itens"]], "a falhada voltou às devidas")
    return {
        "rodadas": rodadas,
        "tentativas_na_graph_api": [m.get("erro_codigo") for m in tentativas_graph],
        "envios_aceitos": 0,
        "excecoes": exc,
        "reconciliacao_final": corpo,
        "observacao": "espera entre rodadas calculada pelo PCPR (2 min, 8 min); o relógio foi "
        "avançado no banco descartável em vez de esperar",
    }


def t8() -> dict:
    preparar_cenario()
    with worker_pausado():
        cid = nova_comunicacao(0)
        _st1, r1 = reconciliar()
        esperar(lambda: len(aceitas(cid)) == 1, 60, "reconciliação não enviou")
        assentar()
        _st2, r2 = reconciliar()
        checar(len(aceitas(cid)) == 1, "2ª reconciliação reenviou")
        checar(r2 == {"devidas": 0}, f"2ª reconciliação: {r2}")
    # o evento "perdido" chega atrasado (worker retomado): o PCPR barra no reservar
    esperar(lambda: evento_de(cid).situacao == "entregue", 60, "evento atrasado não entregue")
    esperar(
        lambda: len(chamadas(elog(), r"/comunicacoes/\d+/reservar", cid)) >= 2,
        60,
        "evento atrasado não chegou ao reservar",
    )
    assentar()
    res = chamadas(elog(), r"/comunicacoes/\d+/reservar", cid)
    checar([x["status"] for x in res] == [200, 409], f"reservas {res}")
    checar(len(aceitas(cid)) == 1, "evento atrasado reenviou")
    return {
        "reconciliacao_1": r1,
        "reconciliacao_2": r2,
        "envios": 1,
        "evento_atrasado": {"reserva": 409, "codigo": res[1].get("codigo")},
    }


def t12() -> dict:
    preparar_cenario()
    espiao("/_espiao/falhar", {"padrao": r"^/estado$", "vezes": 2, "status": 500})
    antes = set(D.ExcecaoAutomacao.objects.values_list("pk", flat=True))
    cid = nova_comunicacao(0)
    novas = esperar(
        lambda: list(
            D.ExcecaoAutomacao.objects.exclude(pk__in=antes).filter(chave__startswith="api:n8n:")
        ),
        90,
        "o W5 não abriu exceção no PCPR",
    )
    assentar()
    checar(not msgs_de(cid), "enviou apesar do erro")
    checar(com(cid)["situacao"] == D.S.AGENDADA, "deveria continuar agendada")
    post = [x for x in chamadas(elog(), r"/excecoes") if x["status"] == 201]
    _st, corpo = reconciliar()
    esperar(lambda: len(aceitas(cid)) == 1, 60, "reconciliação não enviou depois do erro")
    return {
        "estado_injetado": "2x HTTP 500 no /estado (espião; a API não foi alterada)",
        "excecao_no_pcpr": {
            "tipo": novas[0].tipo,
            "chave": novas[0].chave[:60] + "…",
            "resumo": novas[0].resumo[:160],
        },
        "post_excecoes": [x["status"] for x in post],
        "reconciliacao": corpo,
        "envios": 1,
    }


def t10() -> dict:
    preparar_cenario()
    graph("/_sim/config", {"atraso_envio_s": 8})
    grupo_a = []
    for i in (0, 1, 0, 1):  # uma de cada vez: a anterior já está "enviando" quando a nova nasce
        cid = nova_comunicacao(i)
        esperar_situacao(cid, (D.S.RESERVADA,), 60)
        esperar(lambda cid=cid: len(aceitas(cid)) == 1, 30, "Graph não recebeu")
        grupo_a.append(cid)
    t_queda = time.time()
    n8n_local.parar_abrupto()
    graph("/_sim/config", {"atraso_envio_s": 0})
    grupo_b = [nova_comunicacao(0), nova_comunicacao(1)]
    esperar(
        lambda: all(
            evento_de(c).tentativas >= 1 and evento_de(c).situacao == "pendente" for c in grupo_b
        ),
        60,
        "eventos B não falharam com o n8n fora",
    )
    eventos_b = [
        {"situacao": evento_de(c).situacao, "ultimo_erro": evento_de(c).ultimo_erro}
        for c in grupo_b
    ]
    n8n_local.iniciar()
    E["subida_n8n"] = time.time()
    volta = n8n_local.esperar_pronto()
    reentrega_a = reentregar(grupo_a[0], 1)
    _st, corpo = reconciliar()
    esperar(lambda: all(len(aceitas(c)) == 1 for c in grupo_b), 90, "B não saíram")
    # as 4 do grupo A ficaram "enviando" sem resultado (o n8n morreu esperando a resposta)
    estados_a = [com(c)["situacao"] for c in grupo_a]
    relogio = [avancar_relogio(c, "reservada_ate") for c in grupo_a]
    try:
        esperar(lambda: all(com(c)["situacao"] == D.S.INCERTA for c in grupo_a), 60, "")
    except Falha:
        raise Falha(
            "reservas vencidas não viraram resultado desconhecido: "
            + str({c: diagnostico(c) for c in grupo_a})
        ) from None
    assentar()
    g = gst()
    duplicados = {c: len(aceitas(c, g)) for c in grupo_a + grupo_b if len(aceitas(c, g)) != 1}
    exc_a = {c: [x["tipo"] for x in excecoes_de(c)] for c in grupo_a}
    checar(estados_a == [D.S.RESERVADA] * 4, f"A antes do prazo: {estados_a}")
    checar(not duplicados, f"envios duplicados ou faltando: {duplicados}")
    checar(all(v for v in exc_a.values()), f"exceções do grupo A: {exc_a}")
    checar(corpo.get("devidas") == 2, f"reconciliação depois da volta: {corpo}")
    return {
        "grupo_A_enviando_na_queda": grupo_a,
        "graph_aceitou_cada_A": 1,
        "queda": "docker kill com 4 respostas da Graph API pendentes (atraso 8 s)",
        "grupo_B_com_n8n_fora": eventos_b,
        "n8n_voltou_em_s": round(volta, 1),
        "reentrega_de_evento_A": reentrega_a,
        "reconciliacao": corpo,
        "A_estado_antes_do_prazo": estados_a,
        "relogio_avancado_reservada_ate": len(relogio),
        "A_estado_final": [com(c)["situacao"] for c in grupo_a],
        "A_excecoes": exc_a,
        "duplicados": 0,
        "segundos_desde_a_queda": round(time.time() - t_queda, 1),
    }


# ===================================================================== cenários TW (envio)


def tw1() -> dict:
    preparar_cenario()
    cid = nova_comunicacao(1)
    esperar_situacao(cid, (D.S.ENVIADA,))
    assentar()
    g, log = gst(), elog()
    ms = msgs_de(cid, g)
    checar(len(ms) == 1 and ms[0]["tipo"] == "template", f"mensagens {ms}")
    checar(ms[0]["template"] == MODELO_AVISO and len(ms[0]["parametros"]) == 4, f"{ms[0]}")
    checar(com(cid)["mensagem_id"] == ms[0]["wamid"], "wamid não registrado")
    _st, achado = api("GET", f"/comunicacoes?provedor_mensagem_id={ms[0]['wamid']}")
    checar(achado["itens"] == [{"id": cid, "versao": com(cid)["revisao"]}], f"busca {achado}")
    return {
        "mensagem": {
            "tipo": "template",
            "modelo": ms[0]["template"],
            "parametros": 4,
            "biz_opaque_callback_data": ms[0]["biz_opaque_callback_data"],
        },
        "reservas": len(
            [x for x in chamadas(log, r"/comunicacoes/\d+/reservar", cid) if x["status"] == 200]
        ),
        "resultados": len(chamadas(log, r"/comunicacoes/\d+/resultado", cid)),
        "provedor_mensagem_id_registrado": True,
        "busca_pelo_wamid": achado,
    }


def tw2() -> dict:
    preparar_cenario()
    cid = nova_comunicacao(0)
    esperar(lambda: len(aceitas(cid)) == 1, 60, "não enviou")
    serie = reentregar(cid, 2)
    with worker_pausado():
        cid2 = nova_comunicacao(1)
        paralelo = reentregar(cid2, 3, paralelo=True)
    esperar(lambda: len(aceitas(cid2)) == 1, 60, "paralelo não enviou")
    env = corpo_do_evento(cid2)
    env["id"] = str(uuid.uuid4())
    st = postar_envelope(bytes_do_envelope(env), evento_id=env["id"])
    assentar(5)
    log = elog()
    checar(len(aceitas(cid)) == 1 and len(aceitas(cid2)) == 1, "mais de 1 mensagem")
    res2 = chamadas(log, r"/comunicacoes/\d+/reservar", cid2)
    return {
        "serie": {"respostas": serie, "mensagens": 1},
        "paralelo_3x": {
            "respostas": sorted(paralelo),
            "mensagens": 1,
            "reservas": sorted(x["status"] for x in res2),
        },
        "outro_id": {"resposta": st, "mensagens": 1},
    }


def tw3() -> dict:
    preparar_cenario()
    ev: dict[str, Any] = {}
    # (a) o PCPR sabe que a janela está FECHADA → só modelo (nenhum texto tentado)
    ca = nova_comunicacao(0)
    esperar_situacao(ca, (D.S.ENVIADA,))
    ms = msgs_de(ca)
    checar([m["tipo"] for m in ms] == ["template"], f"(a) {ms}")
    ev["a_janela_fechada"] = {"mensagens": [m["tipo"] for m in ms]}
    # (b) o PCPR acha a janela ABERTA (mensagem recebida pelo webhook V2), a Meta não
    usar("V2")
    tel = E["telefones"][0]
    r = graph(
        "/_sim/receber",
        {"de": tel, "tipo": "text", "fase": "V2", "texto": "Mensagem sintética de teste"},
    )
    checar(r["entregas"][0]["status"] == 200, f"webhook V2: {r['entregas']}")
    esperar(
        lambda: D.ContatoVerificado.objects.get(pk=E["contatos"][0]).ultima_mensagem_em,
        60,
        "o PCPR não registrou a mensagem recebida (janela)",
    )
    graph("/_sim/janela", {"wa_id": tel, "ultima_em": None})  # na Meta, fechada
    cb = nova_comunicacao(0)
    esperar_situacao(cb, (D.S.FALHOU,), 60)
    assentar()
    msb = msgs_de(cb)
    checar([(m["tipo"], m.get("erro_codigo")) for m in msb] == [("text", 131047)], f"(b) {msb}")
    ev["b_pcpr_aberta_meta_fechada"] = {
        "mensagens": [(m["tipo"], m.get("erro_codigo")) for m in msb],
        "estado": com(cb)["situacao"],
        "excecoes": excecoes_de(cb),
        "troca_por_modelo": "não aplicável: a reserva real só traz `mensagem.modelo` quando o "
        "PCPR acha a janela fechada (extensão `mensagem.whatsapp` do protótipo não adotada)",
    }
    checar(excecoes_de(cb), "(b) sem exceção")
    # (c) 131047 assíncrono: aceito na API e `failed` depois, pelo webhook V2 do PCPR
    graph("/_sim/config", {"modo_131047": "assincrono"})
    cc = nova_comunicacao(0)
    esperar(lambda: com(cc)["situacao"] == D.S.FALHOU, 90, "(c) status failed não aplicado")
    assentar()
    msc = msgs_de(cc)
    checar(len(msc) == 1 and msc[0]["tipo"] == "text" and msc[0]["aceita"], f"(c) {msc}")
    ev["c_131047_assincrono"] = {
        "mensagens": 1,
        "estado": com(cc)["situacao"],
        "entrega": com(cc)["entrega"],
        "excecoes": excecoes_de(cc),
        "substituta_por_modelo": "não aplicável (extensão `substitui` "
        "do protótipo não adotada no contrato)",
    }
    graph("/_sim/config", {"modo_131047": "sincrono"})
    # (d) fora da janela e SEM modelo configurado → 0 chamada à Graph API
    ligar("respostas_automaticas")
    try:
        cd = agendar("automacao.encaminhada", E["servidores"][1])
        esperar(lambda: com(cd)["situacao"] == D.S.FALHOU, 60, "(d) não falhou")
        assentar()
        resd = chamadas(elog(), r"/comunicacoes/\d+/reservar", cd)
    finally:
        ligar("respostas_automaticas", False)
    checar(not msgs_de(cd), f"(d) chamou a Graph API: {msgs_de(cd)}")
    checar(resd and resd[-1]["status"] == 409, f"(d) reserva {resd}")
    ev["d_sem_modelo"] = {
        "graph": 0,
        "reserva": [resd[-1]["status"], resd[-1].get("codigo")],
        "estado": com(cd)["situacao"],
        "excecoes": excecoes_de(cd),
    }
    # (e) modelo NÃO aprovado na Meta → 1 recusa 132001, exceção, sem repetição
    graph("/_sim/templates", {"nome": MODELO_AVISO, "status": "PENDING", "parametros": 4})
    ce = nova_comunicacao(1)
    esperar(lambda: com(ce)["situacao"] == D.S.FALHOU, 60, "(e) não falhou")
    assentar(3)
    mse = msgs_de(ce)
    graph("/_sim/templates", {"nome": MODELO_AVISO, "status": "APPROVED", "parametros": 4})
    checar([m.get("erro_codigo") for m in mse] == [132001], f"(e) {mse}")
    checar(excecoes_de(ce), "(e) sem exceção")
    ev["e_modelo_nao_aprovado"] = {
        "tentativas": [132001],
        "estado": com(ce)["situacao"],
        "excecoes": excecoes_de(ce),
    }
    com_131047 = [m for m in gst()["mensagens"] if m.get("erro_codigo") == 131047]
    ev["131047_na_bateria"] = [
        {"comunicacao": str(m.get("biz_opaque_callback_data")), "tipo": m["tipo"]}
        for m in com_131047
    ]
    # no máximo UMA recusa 131047 por comunicação (nenhuma repetição em laço)
    por_com: dict[str, int] = {}
    for m in com_131047:
        k = str(m.get("biz_opaque_callback_data") or "").rsplit(":t", 1)[0]
        por_com[k] = por_com.get(k, 0) + 1
    E["tw3"] = ev
    checar(all(n == 1 for n in por_com.values()), f"131047 em laço? {por_com} {ev}")
    return ev


def tw11() -> dict:
    preparar_cenario()
    canal = D.chaves.nome_canal("whatsapp")
    ev: dict[str, Any] = {}
    # (a) canal BLOQUEADO → reservar 409 canal_bloqueado, 0 chamada à Graph API
    chave(canal, "bloqueada")
    try:
        _st, estado = api("GET", "/estado")
        ca = nova_comunicacao(0)
        esperar(lambda: chamadas(elog(), r"/comunicacoes/\d+/reservar", ca), 60, "não reservou")
        assentar()
        resa = chamadas(elog(), r"/comunicacoes/\d+/reservar", ca)
        checar(
            [(x["status"], x.get("codigo")) for x in resa] == [(409, "canal_bloqueado")],
            f"(a) {resa}",
        )
        checar(not msgs_de(ca), "(a) chamou a Graph API com o canal bloqueado")
        ev["a_bloqueado"] = {
            "estado_api": {
                "canais.whatsapp": estado["canais"]["whatsapp"],
                "canais_entrada.whatsapp": estado["canais_entrada"]["whatsapp"],
            },
            "reserva": [409, "canal_bloqueado"],
            "estado": com(ca)["situacao"],
            "graph": 0,
            "aguardando_envio_manual": "não aplicável (estado da extensão WA-1 do protótipo; "
            "no PCPR real a comunicação segue `agendada`)",
        }
        # (c) entrada com o canal bloqueado: webhook V2 e POST /recebimentos
        usar("V2")
        n_ent = D.EntradaWebhook.objects.count()
        rv2 = graph("/_sim/receber", {"de": E["telefones"][1], "tipo": "text", "fase": "V2"})
        n_ent2 = D.EntradaWebhook.objects.count()
        pdf = b"%PDF-1.4\n% bloqueado\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
        corpo, tipo = multipart(
            {
                "canal": "whatsapp",
                "mensagem_id_canal": "wamid.SIMBLOQ" + secrets.token_hex(4),
                "anexo_indice": "0",
                "total_anexos": "1",
                "remetente": "+" + E["telefones"][1],
                "recebido_em": datetime.now(FUSO).isoformat(),
                "nome_arquivo": "x.pdf",
                "sha256": hashlib.sha256(pdf).hexdigest(),
            },
            {"arquivo": ("x.pdf", "application/pdf", pdf)},
        )
        st_rec, b_rec, _ = http_bruto(
            "POST",
            API + "/recebimentos",
            corpo,
            {
                "Authorization": f"Bearer {SEGREDOS['token_api']}",
                "Content-Type": tipo,
                "Idempotency-Key": "receb:whatsapp:bloqueado-tw11:0",
            },
        )
        ev["c_entrada_bloqueada"] = {
            "webhook_v2": rv2["entregas"][0]["status"],
            "entradas_gravadas": n_ent2 - n_ent,
            "post_recebimentos": [
                st_rec,
                json.loads(b_rec or b"{}").get("codigo")
                or json.loads(b_rec or b"{}").get("estado"),
            ],
        }
    finally:
        chave(canal, "ligada")
    if st_rec != 409:
        ev["c_entrada_bloqueada"]["defeito"] = defeito(
            "D3",
            "POST /recebimentos aceita arquivo com o canal de entrada WhatsApp bloqueado",
            requisicao="POST /api/automacao/v1/recebimentos (multipart, canal=whatsapp), com "
            "a chave canal:whatsapp = bloqueada (/estado.canais_entrada.whatsapp = bloqueado)",
            resposta=f"HTTP {st_rec} {b_rec[:200].decode('utf-8', 'replace')}",
            contrato='api-automacao.v1.yaml, /recebimentos (descrição): "Canal `bloqueado` em '
            '`/estado.canais_entrada` → 409 `canal_bloqueado`"; /recebimentos/sem-arquivo: '
            "409 `canal_bloqueado`",
            esperado="409 {codigo: canal_bloqueado}, nada gravado",
        )
    # (d) DESLIGADO ≠ bloqueado: 423, segue agendada; religado → 1 mensagem
    chave(canal, "desligada")
    try:
        cd = nova_comunicacao(1)
        esperar(lambda: chamadas(elog(), r"/comunicacoes/\d+/reservar", cd), 60, "não reservou")
        assentar()
        resd = chamadas(elog(), r"/comunicacoes/\d+/reservar", cd)
    finally:
        chave(canal, "ligada")
    _st, rec = reconciliar()
    esperar(lambda: len(aceitas(cd)) == 1, 60, "(d) religado não enviou")
    checar([x["status"] for x in resd] == [423], f"(d) {resd}")
    ev["d_desligado"] = {"reserva": [423], "reconciliacao": rec, "mensagens": 1}
    ev["mensagens_enquanto_bloqueado"] = ev["a_bloqueado"]["graph"]
    ev["a_depois_de_desbloqueado"] = {
        "estado": com(ca)["situacao"],
        "mensagens": len(msgs_de(ca)),
        "nota": "a comunicação recusada com canal_bloqueado segue agendada no PCPR real e sai "
        "na primeira reconciliação depois de o canal voltar a `ligado`",
    }
    if st_rec != 409:
        raise Falha(f"saída OK, mas a entrada com canal bloqueado foi aceita (D3): {ev}")
    return ev


def tw12() -> dict:
    preparar_cenario()
    ligar("respostas_automaticas")
    op = E["op"]
    ev: dict[str, Any] = {}
    try:
        livres = E["outros_servidores"]
        # (i) servidor sem contato
        c1 = agendar("automacao.ajuda", livres[0])
        # (ii) contato cadastrado mas não verificado
        from gestao.cadastros.models import Servidor

        s2 = Servidor.objects.get(pk=livres[1])
        s2.telefone = "23999990011"
        s2.save(update_fields=["telefone"])
        D.contatos.cadastrar(op, s2.pk)
        c2 = agendar("automacao.ajuda", s2.pk)
        # (iii) opt-in revogado depois de agendar (a pendente é cancelada na revogação) e
        #       agendada depois da revogação
        s3 = Servidor.objects.get(pk=livres[2])
        s3.telefone = "23999990012"
        s3.save(update_fields=["telefone"])
        k3 = D.contatos.cadastrar(op, s3.pk)
        D.contatos.confirmar_numero(op, k3.pk)
        D.contatos.registrar_optin(op, k3.pk, D.ContatoVerificado.OrigemOptin.FORMULARIO)
        with worker_pausado():
            c3 = agendar("automacao.ajuda", s3.pk)
            D.contatos.revogar(op, k3.pk, "pediu para sair (teste)")
        c4 = agendar("automacao.ajuda", s3.pk)
        for c in (c1, c2, c3, c4):
            esperar(
                lambda c=c: chamadas(elog(), r"/comunicacoes/\d+/reservar", c),
                60,
                f"{c} não chegou ao reservar",
            )
        assentar(3)
    finally:
        ligar("respostas_automaticas", False)
    log = elog()
    for nome, c in (
        ("i_sem_contato", c1),
        ("ii_nao_verificado", c2),
        ("iii_revogado_com_pendente", c3),
        ("iii_revogado_depois", c4),
    ):
        res = chamadas(log, r"/comunicacoes/\d+/reservar", c)
        ev[nome] = {
            "reserva": [(x["status"], x.get("codigo")) for x in res],
            "estado": com(c)["situacao"],
            "excecoes": [x["tipo"] for x in excecoes_de(c)],
            "graph": len(msgs_de(c)),
        }
        checar(not msgs_de(c), f"{nome}: enviou")
        checar(res and res[0]["status"] == 409, f"{nome}: {res}")
    checar(
        all(
            ev[k]["excecoes"] for k in ("i_sem_contato", "ii_nao_verificado", "iii_revogado_depois")
        ),
        f"exceções: {ev}",
    )
    return ev


# ===================================================================== cenários TW (entrada)


def enviada(i: int = 0) -> tuple[int, str]:
    cid = nova_comunicacao(i)
    esperar_situacao(cid, (D.S.ENVIADA,))
    return cid, com(cid)["mensagem_id"]


def tw5(variante: str) -> dict:
    preparar_cenario(variante)
    cid, wamid = enviada(0)
    t0 = int(time.time())
    sequencia = [
        {"status": "read", "timestamp": t0},
        {"status": "delivered", "timestamp": t0 - 60},
        {"status": "sent", "timestamp": t0 - 120},  # atrasado
    ]
    respostas, entregas = [], []
    for s in sequencia:
        r = graph("/_sim/status", {"wamid": wamid, **s})
        respostas.append(r["entregas"][0]["status"])
        entregas.append(r["entrega_id"])
    # reentrega IDÊNTICA (mesmos bytes e assinatura) do "delivered"
    respostas += [
        x["status"] for x in graph("/_sim/reentregar", {"entrega_id": entregas[1]})["entregas"]
    ]
    # o MESMO status ("read") de novo, com outro horário (outro aparelho/nova notificação)
    r2 = graph("/_sim/status", {"wamid": wamid, "status": "read", "timestamp": t0 + 5})
    repetido_outro_horario = r2["entregas"][0]["status"]
    ev: dict[str, Any] = {
        "webhooks": respostas,
        "read_repetido_com_outro_horario": repetido_outro_horario,
    }
    if variante == "V1":
        cid2, wamid2 = enviada(1)
        r = graph(
            "/_sim/status", {"wamid": wamid2, "status": "delivered", "sem_callback_data": True}
        )
        ev["sem_callback_data"] = r["entregas"][0]["status"]
        assentar(3)
        log = elog()
        posts = chamadas(log, r"/comunicacoes/\d+/entrega", cid)
        ev["posts_entrega"] = [(x["status"], x.get("replay"), x.get("codigo")) for x in posts]
        busca = chamadas(log, r"/comunicacoes", metodo="GET")
        ev["busca_pelo_wamid"] = [x["status"] for x in busca]
        checar(com(cid2)["entrega"] == "entregue", f"sem callback data: {com(cid2)['entrega']}")
        checar(busca and busca[-1]["status"] == 200, "W8 não consultou o PCPR pelo wamid")
    else:
        esperar(lambda: com(cid)["entrega"] == "lida", 60, "V2: lida não aplicada")
        assentar(2)
        ev["status_registrados"] = sorted(
            D.StatusEntrega.objects.filter(mensagem_id=wamid).values_list("status", flat=True)
        )
        ev["entradas_webhook"] = D.EntradaWebhook.objects.filter(
            resumo__startswith="1 status"
        ).count()
    c = com(cid)
    ev.update(
        estado_final_entrega=c["entrega"],
        entregue_em=bool(c["entregue_em"]),
        lida_em=bool(c["lida_em"]),
        situacao=c["situacao"],
    )
    checar(all(s == 200 for s in respostas), f"webhooks {respostas}")
    checar(c["entrega"] == "lida" and c["entregue_em"] and c["lida_em"], f"final {c}")
    if repetido_outro_horario != 200:
        posts = chamadas(elog(), r"/comunicacoes/\d+/entrega", cid)
        ev["defeito"] = defeito(
            "D2",
            "POST /comunicacoes/{id}/entrega: o mesmo status repetido pela Meta com outro "
            "horário vira 422 (mesma Idempotency-Key, corpo diferente) e o webhook não sai do "
            "erro",
            requisicao="POST /api/automacao/v1/comunicacoes/<id>/entrega com Idempotency-Key "
            "entrega:<id>:<wamid>:lida e corpo {provedor_mensagem_id, status: lida, "
            "ocorrido_em: <outro horário>} depois de um primeiro 'lida' já registrado",
            resposta=[(x["status"], x.get("codigo")) for x in posts][-3:],
            contrato="api-automacao.v1.yaml, /comunicacoes/{id}/entrega: Idempotency-Key "
            "`entrega:<comunicacao>:<provedor_mensagem_id>:<status>` e corpo com `ocorrido_em` "
            'obrigatório; regra geral "Mesma chave com outra requisição → 422"',
            esperado="200 (repetição sem efeito; status nunca regride). Proposta do protótipo "
            "(README, WA-3): impressão de /entrega = (provedor_mensagem_id, status), sem "
            "ocorrido_em — ou chave com o horário",
        )
        raise Falha(f"read repetido com outro horário → webhook {repetido_outro_horario} (D2)")
    return ev


def tw6(variante: str) -> dict:
    preparar_cenario(variante)
    de = E["telefones"][0]
    n_ent = D.EntradaWebhook.objects.count()
    respostas, medias = {}, []
    for modo in ("segredo_errado", "sem_assinatura", "corpo_alterado", "sha1"):
        r = graph(
            "/_sim/receber",
            {
                "de": de,
                "tipo": "document",
                "fase": variante,
                "modo": modo,
                "prefixo_midia": _prefixo(variante),
            },
        )
        respostas[modo] = r["entregas"][0]["status"]
        medias.append(r["media_id"])
    assentar(3)
    g = gst()
    checar(all(s == 401 for s in respostas.values()), f"esperado 401: {respostas}")
    checar(D.EntradaWebhook.objects.count() == n_ent, "assinatura inválida gravou entrada")
    checar(not chamadas(elog(), r"/recebimentos.*"), "assinatura inválida chamou o PCPR")
    tocadas = [x for x in g["metadados"] + g["downloads"] if x.get("media_id") in medias]
    checar(not tocadas, f"assinatura inválida baixou mídia: {tocadas}")
    ok = graph(
        "/_sim/receber",
        {"de": de, "tipo": "document", "fase": variante, "prefixo_midia": _prefixo(variante)},
    )
    esperar(lambda: recebimentos_de(ok["wamid"]), 60, "controle positivo não registrou")
    return {
        "respostas_invalidas": respostas,
        "entradas_gravadas": 0,
        "midias_tocadas": 0,
        "controle_positivo": {"status": ok["entregas"][0]["status"], "recebimentos": 1},
    }


def _prefixo(variante: str) -> str:
    return "91011" if variante == "V1" else "92022"


def tw7(variante: str) -> dict:
    preparar_cenario(variante)
    destino = CALLBACK[variante]
    certo = graph(
        "/_sim/verificar", {"destino": destino, "verify_token": SEGREDOS["wa_verify_token"]}
    )
    errado = graph(
        "/_sim/verificar",
        {"destino": destino, "verify_token": "token-errado-" + secrets.token_hex(4)},
    )
    modo = graph(
        "/_sim/verificar",
        {"destino": destino, "modo": "unsubscribe", "verify_token": SEGREDOS["wa_verify_token"]},
    )
    hostil = graph(
        "/_sim/verificar",
        {
            "destino": destino,
            "verify_token": SEGREDOS["wa_verify_token"],
            "challenge": "<script>alert(1)</script>",
        },
    )
    ev = {
        "correta": [certo["status"], certo.get("content_type")],
        "token_errado": errado["status"],
        "modo_errado": modo["status"],
        "desafio_nao_alfanumerico": [hostil["status"], hostil.get("content_type")],
    }
    checar(certo["status"] == 200 and certo["confere"], f"correta: {certo}")
    checar("text/plain" in (certo.get("content_type") or ""), f"content-type {certo}")
    checar(errado["status"] == 403 and modo["status"] == 403, f"recusas: {ev}")
    if hostil["status"] != 403:
        ev["divergencia"] = defeito(
            "O1",
            "Webhook V2 do PCPR ecoa desafio não alfanumérico na verificação GET",
            requisicao="GET /integracoes/whatsapp/webhook/?hub.mode=subscribe&hub.verify_token="
            "<certo>&hub.challenge=<script>alert(1)</script>",
            resposta=f"HTTP {hostil['status']} {hostil.get('content_type')} (desafio ecoado)",
            contrato="nenhuma linha do api-automacao.v1.yaml (a rota V2 fica fora de "
            "/api/automacao/v1); critério do protótipo WA-3 (TW7: desafio só ecoado se curto e "
            "alfanumérico)",
            esperado="403 (a Meta manda desafio numérico); risco baixo: text/plain, no-store",
            gravidade="observação",
        )
        raise Falha(
            f"desafio não alfanumérico ecoado ({hostil['status']}) — critério do "
            "protótipo, não do contrato (O1)"
        )
    return ev


def tw8(variante: str) -> dict:
    preparar_cenario(variante)
    cid, wamid_out = enviada(0)
    usar(variante)
    de = E["telefones"][0]
    r = graph(
        "/_sim/receber",
        {
            "de": de,
            "tipo": "document",
            "fase": variante,
            "prefixo_midia": _prefixo(variante),
            "contexto_wamid": wamid_out,
            "nome_arquivo": "comprovante.pdf",
        },
    )
    checar(r["entregas"][0]["status"] == 200, f"webhook {r['entregas']}")
    recs = esperar(lambda: recebimentos_de(r["wamid"]), 60, "recebimento não registrado")
    assentar(3)
    g = gst()
    rec = recebimentos_de(r["wamid"])[0]
    midia = g["midias"][r["media_id"]]
    downs = [x for x in g["downloads"] if x["media_id"] == r["media_id"]]
    metas = [x for x in g["metadados"] if x["media_id"] == r["media_id"]]
    ev: dict[str, Any] = {
        "webhook": r["entregas"][0]["status"],
        "recebimentos": len(recs),
        "situacao": rec.situacao,
        "comunicacao_respondida": rec.comunicacao_id,
        "passos_na_graph_api": {"metadados": len(metas), "downloads": [x["status"] for x in downs]},
    }
    checar(len(recebimentos_de(r["wamid"])) == 1, "mais de 1 recebimento")
    checar(rec.comunicacao_id == cid, "resposta não ligada à comunicação (context.id)")
    if variante == "V1":
        checar(rec.sha256 == midia["sha256"], "SHA-256 do recebimento ≠ da mídia")
        checar(downs and all(x["bearer"] for x in downs) and downs[-1]["status"] == 200, f"{downs}")
        ev["sha256_conferido"] = True
        # (b) mídia corrompida → SHA-256 não confere → nada importado, exceção
        graph("/_sim/config", {"corromper_proximos_downloads": 1})
        antes = D.ExcecaoAutomacao.objects.count()
        rb = graph(
            "/_sim/receber",
            {"de": de, "tipo": "document", "fase": variante, "prefixo_midia": _prefixo(variante)},
        )
        esperar(lambda: D.ExcecaoAutomacao.objects.count() > antes, 60, "sem exceção do SHA")
        assentar(2)
        checar(not recebimentos_de(rb["wamid"]), "arquivo corrompido importado")
        ev["b_sha256_divergente"] = {
            "recebimentos": 0,
            "excecao": True,
            "webhook": rb["entregas"][0]["status"],
        }
    else:
        bloqueados = _guarda_hosts()
        ev["download_pelo_pcpr"] = (
            "não aplicável: o PCPR baixa da base fixa https://graph.facebook.com "
            "(gestao/integracoes/whatsapp/config.py: BASE_URL constante) — a guarda de rede "
            f"bloqueou {sorted(set(bloqueados))}; 0 download no simulador"
        )
        checar(not downs, "V2: download no simulador (não deveria haver)")
        checar(rec.midia_id, "V2: recebimento sem id de mídia")
    # (c) lote misto (documento + status no mesmo POST)
    cid3, wamid3 = enviada(1)
    usar(variante)
    lote = graph(
        "/_sim/lote",
        {
            "eventos": [
                {
                    "de": de,
                    "tipo": "document",
                    "fase": variante,
                    "prefixo_midia": _prefixo(variante),
                },
                {"wamid": wamid3, "status": "delivered"},
            ]
        },
    )
    checar(lote["entregas"][0]["status"] == 200, f"lote {lote['entregas']}")
    wamid_doc = lote["itens"][0]["wamid"]
    if variante == "V1":
        imediato = bool(recebimentos_de(wamid_doc)) and com(cid3)["entrega"] == "entregue"
        checar(imediato, "W7 respondeu 200 antes de concluir os eventos do lote")
    else:
        esperar(
            lambda: recebimentos_de(wamid_doc) and com(cid3)["entrega"] == "entregue", 60, "lote V2"
        )
    ev["c_lote_misto"] = {"resposta": 200, "recebimentos": 1, "entrega": com(cid3)["entrega"]}
    return ev


def tw9(variante: str) -> dict:
    preparar_cenario(variante)
    de = E["telefones"][1]
    r = graph(
        "/_sim/receber",
        {
            "de": de,
            "tipo": "document",
            "fase": variante,
            "prefixo_midia": _prefixo(variante),
            "duplicar": 2,
        },
    )
    respostas = [x["status"] for x in r["entregas"]]
    esperar(lambda: recebimentos_de(r["wamid"]), 60, "recebimento não registrado")
    assentar(3)
    g = gst()
    downs = [x for x in g["downloads"] if x["media_id"] == r["media_id"]]
    ev = {
        "entregas_identicas": 3,
        "respostas": respostas,
        "recebimentos": len(recebimentos_de(r["wamid"])),
        "downloads_no_simulador": len(downs),
    }
    checar(respostas == [200, 200, 200], f"entregas {respostas}")
    checar(len(recebimentos_de(r["wamid"])) == 1, "mais de 1 recebimento")
    if variante == "V1":
        posts = chamadas(elog(), r"/recebimentos")
        ev["post_recebimentos"] = [(x["status"], x.get("replay")) for x in posts]
        checar(len(posts) == 3 and sum(1 for p in posts if p.get("replay")) == 2, f"{posts}")
    else:
        n = D.EntradaWebhook.objects.filter(resumo__contains="mensagem").count()
        ev["entradas_webhook_com_mensagem"] = n
    return ev


def tw10(variante: str) -> dict:
    if variante == "V2":
        raise NaoAplicavel(
            "na V2 quem baixa é o PCPR, da base fixa https://graph.facebook.com "
            "(BASE_URL constante em gestao/integracoes/whatsapp/config.py): não dá para "
            "apontar para o simulador sem mudar o código; a guarda de rede bloqueia a chamada"
        )
    preparar_cenario(variante)
    graph("/_sim/config", {"expirar_proximas_urls": 1})
    r = graph(
        "/_sim/receber",
        {
            "de": E["telefones"][0],
            "tipo": "document",
            "fase": variante,
            "prefixo_midia": _prefixo(variante),
            "incluir_url": False,
        },
    )
    esperar(lambda: recebimentos_de(r["wamid"]), 60, "recebimento não registrado")
    assentar(2)
    g = gst()
    downs = [x["status"] for x in g["downloads"] if x["media_id"] == r["media_id"]]
    metas = [x for x in g["metadados"] if x["media_id"] == r["media_id"]]
    checar(downs == [404, 200], f"downloads {downs}")
    checar(len(metas) == 2, f"pedidos de URL {len(metas)}")
    checar(len(recebimentos_de(r["wamid"])) == 1, "recebimento")
    return {
        "pedidos_de_url": 2,
        "downloads": downs,
        "recebimentos": 1,
        "webhook": r["entregas"][0]["status"],
    }


def x2() -> dict:
    """Idempotency-Key acima de 200 caracteres: o PCPR recusa (422) e os workflows do alvo pcpr
    trocam a chave por `<prefixo>sha256:<hex>`. Prova ponta a ponta: um webhook V1 (assinado como
    a Meta) com wamid de 250 caracteres → W7 → POST /recebimentos/sem-arquivo."""
    preparar_cenario("V1")
    longa = "receb:whatsapp:" + "x" * 200 + ":0"
    st_direto, b_direto = api(
        "POST", "/recebimentos/sem-arquivo", {"canal": "whatsapp"}, chave=longa
    )
    wamid = "wamid.SIMLONGO" + "A" * 236
    corpo = json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "200000000000002",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "550030000001",
                                    "phone_number_id": NUMERO_ID,
                                },
                                "contacts": [
                                    {
                                        "profile": {"name": "Servidora SINTETICA-V1"},
                                        "wa_id": E["telefones"][0],
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": E["telefones"][0],
                                        "id": wamid,
                                        "timestamp": str(int(time.time())),
                                        "type": "text",
                                        "text": {"body": "chave longa"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
    ).encode()
    assinatura = (
        "sha256=" + hmac.new(SEGREDOS["wa_app_secret"].encode(), corpo, hashlib.sha256).hexdigest()
    )
    st, _, _ = http_bruto(
        "POST",
        CALLBACK["V1"],
        corpo,
        {"Content-Type": "application/json", "X-Hub-Signature-256": assinatura},
    )
    assentar(3)
    posts = chamadas(elog(), r"/recebimentos/sem-arquivo")
    ev = {
        "pcpr_com_chave_de_216": [st_direto, (b_direto or {}).get("codigo")],
        "webhook_w7": st,
        "post_sem_arquivo": [(x["status"], len(x["chave"]), x["chave"][:14] + "…") for x in posts],
    }
    checar(st_direto == 422, f"o PCPR deveria recusar chave > 200: {st_direto}")
    checar(st == 200, f"W7 → {st}")
    checar(
        posts and all(x["status"] == 202 and len(x["chave"]) <= 200 for x in posts),
        f"chave limitada: {ev}",
    )
    checar(
        re.fullmatch(r"receb#sha256:whatsapp:[0-9a-f]{64}:0", posts[0]["chave"]), f"formato {ev}"
    )
    return ev


def x1() -> dict:
    """Contrato de /recebimentos: mesma chave + SHA-256 diferente → 409 conflito_de_versao."""
    preparar_cenario()
    pdf1 = b"%PDF-1.4\n% x1-a\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    pdf2 = b"%PDF-1.4\n% x1-b (outro conteudo)\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    wamid = "wamid.SIMX1" + secrets.token_hex(6)
    chave_r = f"receb:whatsapp:{wamid}:0"

    recebido_em = datetime.now(FUSO).isoformat()

    def post(pdf: bytes) -> tuple[int, dict, dict]:
        corpo, tipo = multipart(
            {
                "canal": "whatsapp",
                "mensagem_id_canal": wamid,
                "anexo_indice": "0",
                "total_anexos": "1",
                "remetente": "+" + E["telefones"][0],
                "recebido_em": recebido_em,
                "nome_arquivo": "c.pdf",
                "sha256": hashlib.sha256(pdf).hexdigest(),
            },
            {"arquivo": ("c.pdf", "application/pdf", pdf)},
        )
        st, b, h = http_bruto(
            "POST",
            API + "/recebimentos",
            corpo,
            {
                "Authorization": f"Bearer {SEGREDOS['token_api']}",
                "Content-Type": tipo,
                "Idempotency-Key": chave_r,
            },
        )
        return st, json.loads(b or b"{}"), h

    st1, b1, _ = post(pdf1)
    st2, b2, h2 = post(pdf1)
    st3, b3, _ = post(pdf2)
    corpo_e, tipo_e = multipart(
        {
            "canal": "email",
            "mensagem_id_canal": "<x1@example.invalid>",
            "anexo_indice": "0",
            "total_anexos": "1",
            "remetente": "x1@example.invalid",
            "recebido_em": datetime.now(FUSO).isoformat(),
            "sha256": hashlib.sha256(pdf1).hexdigest(),
        },
        {"arquivo": ("c.pdf", "application/pdf", pdf1)},
    )
    st_email, b_e, _ = http_bruto(
        "POST",
        API + "/recebimentos",
        corpo_e,
        {
            "Authorization": f"Bearer {SEGREDOS['token_api']}",
            "Content-Type": tipo_e,
            "Idempotency-Key": "receb:email:<x1@example.invalid>:0",
        },
    )
    b_email = json.loads(b_e or b"{}")
    ev = {
        "primeiro": [st1, b1.get("estado")],
        "repeticao_identica": [st2, b2.get("estado"), h2.get("Idempotency-Replayed")],
        "mesma_chave_outro_sha256": [st3, b3.get("codigo")],
        "recebimentos": len(recebimentos_de(wamid)),
        "canal_email_json": [st_email, (b_email or {}).get("codigo")],
    }
    checar(st1 == 202 and st2 == 202 and h2.get("Idempotency-Replayed") == "true", f"{ev}")
    checar(len(recebimentos_de(wamid)) == 1, "mais de 1 recebimento")
    if not (st3 == 409 and b3.get("codigo") == "conflito_de_versao"):
        ev["defeito"] = defeito(
            "D4",
            "POST /recebimentos com a mesma Idempotency-Key e outro arquivo devolve "
            f"{st3} {b3.get('codigo')} em vez de 409 conflito_de_versao",
            requisicao=f"POST /api/automacao/v1/recebimentos, Idempotency-Key {chave_r}, "
            "1º com o PDF A (202), depois com o PDF B (sha256 diferente)",
            resposta=f"HTTP {st3} {json.dumps(b3, ensure_ascii=False)[:200]}",
            contrato='api-automacao.v1.yaml, /recebimentos: "Repetir a mesma chave devolve o '
            "mesmo `Recebimento` sem efeito; **mesma chave com SHA-256 diferente → 409 "
            "`conflito_de_versao`** (o canal mudou o anexo; vira exceção), em vez do 422 "
            'genérico"; e em Idempotência: "(exceção: `/recebimentos`, ver a operação)"',
            esperado="409 {codigo: conflito_de_versao}. Causa provável: a camada de "
            "idempotência (api/base.py) compara a impressão (campos + SHA-256) antes da rota e "
            "responde 422; o 409 de recebimentos.receber_arquivo nunca é alcançado",
        )
        raise Falha(f"mesma chave com outro SHA-256 → {st3} {b3.get('codigo')} (D4)")
    return ev


# ===================================================================== retenção (T13/TW13)

_RE_B64 = re.compile(rb"[A-Za-z0-9+/]{40,}={0,2}")


def contar(dados: bytes, mk: dict[str, list[str]]) -> dict[str, int]:
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


def marcadores() -> dict[str, list[str]]:
    acumular_midias()
    esp = espiao("/_espiao/marcadores")
    por_fase = {f: sorted(ids) for f, ids in E["midias"].items()}
    base = {
        "envio·destino": esp["destino"],
        "envio·token_reserva": esp["token_reserva"],
        "status·wamid_saida": ["wamid.SIMOUT"],
    }
    for v in ("V1", "V2"):
        base.update(
            {
                f"{v}·wamid": [f"wamid.SIMIN{v}"],
                f"{v}·nome_perfil": [f"SINTETICA-{v}"],
                f"{v}·url_midia": [f"urlSIM-{v}"],
                f"{v}·id_midia": por_fase.get(v, []),
                f"{v}·documento": [f"PCPR-DOC-SINTETICO-{v}"],
            }
        )
    for nome, valor in SEGREDOS.items():
        base[f"segredo·{nome}"] = [valor]
    return base


def varrer(rotulo: str) -> dict:
    mk = marcadores()
    d = Path(tempfile.mkdtemp(prefix="pcpr-real-varredura-"))
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
        outras: dict[str, dict[str, int]] = {}
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
                            outras.setdefault(t, {}).setdefault(k, 0)
                            outras[t][k] += n
        linhas: dict[str, int] = {}
        onde: dict[str, dict[str, int]] = {}
        if "execution_data" in tabelas and "execution_entity" in tabelas:
            for wid, status, apagada, dados in con.execute(
                "select e.workflowId, e.status, e.deletedAt is not null, d.data "
                "from execution_data d join execution_entity e on e.id = d.executionId"
            ):
                k = f"{wid}|{status}|{'soft-deleted' if apagada else 'ativa'}"
                for m, n in contar(f"{dados or ''}".encode(), mk).items():
                    onde.setdefault(k, {}).setdefault(m, 0)
                    onde[k][m] += n
        if "execution_entity" in tabelas:
            for wid, status, apagada in con.execute(
                "select workflowId, status, deletedAt is not null from execution_entity"
            ):
                k = f"{wid}|{status}|{'soft-deleted' if apagada else 'ativa'}"
                linhas[k] = linhas.get(k, 0) + 1
        con.close()
        arq: dict[str, int] = {}
        for p in d.rglob("*"):
            if not p.is_file() or p.name.startswith("database.sqlite") or p.name == "config":
                continue
            for k, n in contar(p.read_bytes(), mk).items():
                arq[k] = arq.get(k, 0) + n
        r = {
            "rotulo": rotulo,
            "em": datetime.now(FUSO).isoformat(timespec="seconds"),
            "segundos_desde_subida_do_n8n": round(time.time() - E.get("subida_n8n", 0), 1),
            "tabelas_de_execucao": exec_cont,
            "demais_tabelas": outras,
            "arquivos": arq,
            "linhas_execution_entity": linhas,
            "execucoes_com_marcadores": onde,
        }
        grupos: dict[str, int] = {}
        for fonte in ("tabelas_de_execucao", "arquivos"):
            for k, v in r[fonte].items():
                g = k.split("·")[0] + ("·" + k.split("·")[1].split("[")[0] if "·" in k else "")
                grupos[g] = grupos.get(g, 0) + v
        r["por_grupo"] = grupos
        E["varreduras"][rotulo] = r
        return r
    finally:
        shutil.rmtree(d, ignore_errors=True)


def controle_positivo_v1() -> dict:
    """Uma mensagem V1 logo antes da varredura: prova que a varredura enxerga o que procura."""
    usar("V1")
    r = graph(
        "/_sim/receber",
        {"de": E["telefones"][1], "tipo": "document", "fase": "V1", "prefixo_midia": "91011"},
    )
    esperar(lambda: recebimentos_de(r["wamid"]), 60, "controle V1 não registrou")
    return {"wamid": "…" + r["wamid"][-6:]}


def proibidos_achados(r: dict) -> list[str]:
    """Credenciais que o n8n usa para FALAR com alguém (nunca podem aparecer)."""
    fala = (
        "token_api",
        "hmac_eventos",
        "n8n_cripto",
        "wa_token_graph_sim",
        "wa_app_secret",
        "wa_chave_verify",
        "wa_token_falso_pcpr",
        "django_secret",
    )
    alvo = {f"segredo·{k}" for k in fala}
    alvo |= {f"{k}[b64]" for k in alvo}
    return [k for k in (*r["tabelas_de_execucao"], *r["arquivos"]) if k in alvo]


def t13() -> dict:
    v = E["varreduras"]
    checar({"imediata", "apos_hard_delete"} <= set(v), "T13 precisa das 2 varreduras")
    pessoais = ("envio·destino", "envio·token_reserva")
    imediata = {k: n for k, n in v["imediata"]["por_grupo"].items() if k in pessoais}
    depois = {k: n for k, n in v["apos_hard_delete"]["por_grupo"].items() if k in pessoais}
    for rot, r in v.items():
        achados = proibidos_achados(r)
        checar(not achados, f"credencial encontrada no n8n em {rot}: {achados}")
    checar(not depois, f"após o hard-delete ainda sobrou destino/token de reserva: {depois}")
    return {
        "imediata": {
            "segundos_desde_subida": v["imediata"]["segundos_desde_subida_do_n8n"],
            "destino_e_token": imediata,
        },
        "apos_hard_delete": {
            "segundos_desde_subida": v["apos_hard_delete"]["segundos_desde_subida_do_n8n"],
            "destino_e_token": depois,
        },
        "credenciais_no_n8n": 0,
        "configuracao": "EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL=1 (n8n_local.py)",
    }


def tw13() -> dict:
    v = E["varreduras"]
    checar({"apos_v1", "apos_v2", "apos_hard_delete"} <= set(v), "TW13 precisa das varreduras")
    v2 = {k: n for r in v.values() for k, n in r["por_grupo"].items() if k.startswith("V2·")}
    v1_ctrl = {k: n for k, n in v["apos_v1"]["por_grupo"].items() if k.startswith("V1·")}
    sobra = {
        k: n
        for k, n in v["apos_hard_delete"]["por_grupo"].items()
        if k.startswith(("V1·", "V2·", "envio·", "status·"))
    }
    vindos_de_fora = {
        rot: {
            k: n
            for k, n in {**r["tabelas_de_execucao"], **r["arquivos"]}.items()
            if k.startswith(("segredo·disparo", "segredo·wa_verify_token"))
        }
        for rot, r in v.items()
    }
    checar(not v2, f"V2 deixou dado de entrada no n8n: {v2}")
    checar(v1_ctrl, "controle positivo: a varredura não achou o rastro da V1 (insensível?)")
    checar(not sobra, f"depois do hard-delete sobrou: {sobra}")
    return {
        "V1_logo_apos": v1_ctrl,
        "V2_em_qualquer_varredura": 0,
        "apos_hard_delete": sobra or 0,
        "segredos_vindos_de_fora_retidos": vindos_de_fora,
    }


# ===================================================================== orquestração

NAO_APLICAVEIS = {
    "T6": "Canal genérico com recusa 1× e 2ª tentativa no W2: o PCPR real só tem o canal "
    "WhatsApp (toda reserva vem com canal=whatsapp → W6), e o W6 por desenho NÃO repete o POST "
    "/messages (a Cloud API não tem chave de idempotência). O caminho de 3 tentativas do W2 não "
    "existe no alvo pcpr. Recusa temporária do WhatsApp: ver T7 (adaptado).",
    "T9": "W4 é o recebimento do canal genérico (e-mail): a API real responde 501 "
    "integracao_inexistente para canal≠whatsapp (piloto WhatsApp). A idempotência de "
    "/recebimentos com canal whatsapp está em TW9 e X1.",
    "T11": "Regra da véspera (`regra_vespera.py`) é uma função pura do protótipo; o PCPR real "
    "não implementa o link de km da véspera pela API de automação. Não toca a API.",
    "TW4": "Documento por id de mídia: a reserva real (`ComunicacaoReservada`) não traz `anexos` "
    "nem `url_assinada` para nenhum tipo implementado; o W6 do alvo pcpr não tem o ramo de "
    "documento.",
}

CENARIOS: list[tuple[str, str, str, Callable[..., dict]]] = [
    ("TW0", "-", "simulador da Graph API aplica as regras (pré-condição)", tw0),
    ("T1", "-", "evento válido do emissor real → 1 envio e 1 resultado; envelope no esquema", t1),
    ("T2", "-", "mesmo evento reenviado (série, paralelo, outro id) → 1 envio", t2),
    ("T3", "-", "assinatura inválida → 401 e 0 envio; emissor real com segredo errado", t3),
    ("T4", "-", "evento obsoleto/versão antiga → 409 e 0 envio", t4),
    ("T5", "-", "automação desligada → 0 envio; 423 no reservar; religada → 1 cada", t5),
    ("T7", "-", "Graph API sempre recusa (temporário) → rodadas do PCPR, exceção no fim", t7),
    ("T8", "-", "evento perdido → reconciliação envia 1 vez", t8),
    ("T12", "-", "erro inesperado → W5 abre exceção no PCPR", t12),
    ("T10", "-", "queda do n8n no meio → nada duplicado, reconciliação completa", t10),
    ("TW1", "-", "modelo enviado 1× e wamid registrado no PCPR", tw1),
    ("TW2", "-", "evento duplicado → 1 mensagem", tw2),
    ("TW3", "-", "fora da janela: modelo; 131047 nunca em laço", tw3),
    ("TW11", "-", "canal bloqueado → 0 chamada à Graph API; desligado ≠ bloqueado", tw11),
    ("TW12", "-", "contato sem opt-in/verificação → não envia", tw12),
    ("X1", "-", "contrato de /recebimentos: mesma chave, outro SHA-256 → 409", x1),
    ("X2", "-", "Idempotency-Key > 200: workflows usam <prefixo>sha256:<hex>", x2),
    ("TW5", "V1", "status fora de ordem e duplicado → lida, sem regressão", tw5),
    ("TW6", "V1", "assinatura inválida → 401, nada gravado", tw6),
    ("TW7", "V1", "verificação GET", tw7),
    ("TW8", "V1", "documento recebido → 1 recebimento", tw8),
    ("TW9", "V1", "reentrega do mesmo webhook → 1 recebimento", tw9),
    ("TW10", "V1", "URL de mídia vencida → pede nova", tw10),
    ("VARRER", "apos_v1", "", varrer),
    ("TW5", "V2", "status fora de ordem e duplicado → lida, sem regressão", tw5),
    ("TW6", "V2", "assinatura inválida → 401, nada gravado", tw6),
    ("TW7", "V2", "verificação GET", tw7),
    ("TW8", "V2", "documento recebido → 1 recebimento", tw8),
    ("TW9", "V2", "reentrega do mesmo webhook → 1 recebimento", tw9),
    ("TW10", "V2", "URL de mídia vencida → pede nova", tw10),
    ("VARRER", "apos_v2", "", varrer),
]


def subir_processos(tmp: Path, env: dict[str, str]) -> list[subprocess.Popen]:
    procs = []
    env_pcpr = {**os.environ, **env, "PYTHONPATH": str(GUARDA)}
    env_sim = {
        **os.environ,
        "PYTHONUNBUFFERED": "1",
        "GRAPH_SIM_TOKEN": SEGREDOS["wa_token_graph_sim"],
        "GRAPH_SIM_APP_SECRET": SEGREDOS["wa_app_secret"],
    }
    comandos = [
        (
            "runserver",
            [str(PYTHON), "manage.py", "runserver", f"127.0.0.1:{PORTAS['pcpr']}", "--noreload"],
            REPO,
            env_pcpr,
        ),
        (
            "espiao",
            [
                sys.executable,
                str(RAIZ / "espiao_pcpr.py"),
                "--porta",
                str(PORTAS["espiao"]),
                "--destino",
                f"127.0.0.1:{PORTAS['pcpr']}",
            ],
            RAIZ,
            env_sim,
        ),
        (
            "graph",
            [sys.executable, str(RAIZ / "simulador_graph.py"), "--porta", str(PORTAS["graph"])],
            RAIZ,
            env_sim,
        ),
    ]
    for nome, cmd, cwd, amb in comandos:
        log = (tmp / f"{nome}.log").open("w", encoding="utf-8")
        procs.append(subprocess.Popen(cmd, cwd=cwd, env=amb, stdout=log, stderr=subprocess.STDOUT))
        E.setdefault("procs", []).append(procs[-1])
    esperar(
        lambda: http("GET", f"{PCPR}/api/automacao/v1/estado")[0] == 401, 300, "runserver não subiu"
    )
    esperar(lambda: http("GET", f"{ESPIAO}/_espiao/saude")[0] == 200, 20, "espião não subiu")
    esperar(lambda: http("GET", f"{GRAPH}/_sim/saude")[0] == 200, 20, "Graph não subiu")
    return procs


def subir_postgres() -> float:
    t0 = time.time()
    n8n_local.docker("rm", "-f", CONTEINER_PG, check=False)
    n8n_local.docker(
        "run",
        "-d",
        "--name",
        CONTEINER_PG,
        "-e",
        "POSTGRES_PASSWORD=teste",
        "-e",
        "POSTGRES_USER=pcpr",
        "-e",
        "POSTGRES_DB=pcpr",
        "-p",
        f"127.0.0.1:{PORTAS['postgres']}:5432",
        "--tmpfs",
        "/var/lib/postgresql/data",
        "postgres:16",
        "-c",
        "fsync=off",
        "-c",
        "max_connections=300",
    )
    esperar(
        lambda: (
            n8n_local.docker(
                "exec", CONTEINER_PG, "pg_isready", "-U", "pcpr", "-d", "pcpr", check=False
            ).returncode
            == 0
        ),
        60,
        "pg não subiu",
    )
    time.sleep(2)
    return time.time() - t0


def migrar(env: dict[str, str], tmp: Path) -> float:
    t0 = time.time()
    r = subprocess.run(
        [str(PYTHON), "manage.py", "migrate", "--noinput"],
        cwd=REPO,
        env={**os.environ, **env, "PYTHONPATH": str(GUARDA)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
        check=False,
    )
    (tmp / "migrate.log").write_text(r.stdout + r.stderr, encoding="utf-8")
    checar(r.returncode == 0, f"migrate falhou: {(r.stdout + r.stderr)[-1500:]}")
    return time.time() - t0


def credenciais_n8n() -> list[dict]:
    return [
        {
            **cw.CRED_API,
            "type": "httpHeaderAuth",
            "data": {"name": "Authorization", "value": f"Bearer {SEGREDOS['token_api']}"},
        },
        {**cw.CRED_HMAC, "type": "crypto", "data": {"hmacSecret": SEGREDOS["hmac_eventos"]}},
        {
            **cw.CRED_DISPARO,
            "type": "httpHeaderAuth",
            "data": {"name": "X-Disparo-Token", "value": SEGREDOS["disparo"]},
        },
        {
            **cw.CRED_WA_TOKEN,
            "type": "httpHeaderAuth",
            "data": {"name": "Authorization", "value": f"Bearer {SEGREDOS['wa_token_graph_sim']}"},
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
    vazou = [k for k, v in SEGREDOS.items() if v and v in cred]
    checar(not vazou, f"credenciais exportadas em claro: {vazou}")
    evid["credenciais_criptografadas_no_banco"] = True
    DOCS_N8N_PCPR.mkdir(parents=True, exist_ok=True)
    for wid, nome in cw.ARQUIVOS_PCPR.items():
        bruto = (destino / "workflows" / f"{wid}.json").read_text(encoding="utf-8")
        dados = json.loads(bruto)
        segredos_no_arquivo = [k for k, v in SEGREDOS.items() if v and v in bruto]
        checar(not segredos_no_arquivo, f"{nome} contém segredo: {segredos_no_arquivo}")
        checar(not re.search(r"pcpr_(test|lab|prod|stg|prev|dev)_", bruto), f"{nome}: token")
        checar(dados.get("active") is False, f"{nome}: active={dados.get('active')!r}")
        checar("facebook.com" not in bruto, f"{nome} aponta para a Meta")
        (DOCS_N8N_PCPR / nome).write_text(
            json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        evid["arquivos"][nome] = {
            "active": dados["active"],
            "nos": len(dados["nodes"]),
            "credenciais": sorted(
                {
                    f"{c['id']} ({c['name']})"
                    for n in dados["nodes"]
                    for c in (n.get("credentials") or {}).values()
                }
            ),
        }
    return evid


def versoes_graph_nos_oficiais() -> dict[str, Any]:
    """Lê na própria imagem 2.43.7 a base da Graph API dos nós oficiais do WhatsApp."""
    base = "/usr/local/lib/node_modules/n8n/node_modules/n8n-nodes-base/dist/nodes/WhatsApp"
    r = n8n_local.docker(
        "exec",
        n8n_local.CONTEINER,
        "sh",
        "-c",
        f"grep -rhoE 'graph\\.facebook\\.com/v[0-9.]+' {base} | sort | uniq -c",
        check=False,
    )
    return {
        "pasta": base,
        "ocorrencias": [x.strip() for x in r.stdout.splitlines()],
        "erro": r.stderr.strip()[-200:] or None,
    }


def matar(p: subprocess.Popen) -> None:
    """No Windows o python.exe do .venv é um lançador que cria o python de verdade como filho:
    `terminate()` mataria só o lançador. `taskkill /T` derruba a árvore inteira."""
    if p.poll() is None:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, check=False
        )
    with contextlib.suppress(subprocess.TimeoutExpired):
        p.wait(10)


def portas_abertas() -> list[str]:
    r = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    alvo = "|".join(str(p) for p in PORTAS.values())
    return [
        linha.strip()
        for linha in r.stdout.splitlines()
        if re.search(rf":({alvo})\s", linha)
        and ("LISTEN" in linha.upper() or "ESCUTANDO" in linha.upper())
    ]


def _guarda_hosts() -> list[str]:
    caminho = Path(os.environ.get("PCPR_GUARDA_LOG", ""))
    if not caminho.is_file():
        return []
    return [
        linha.split("\t")[2].strip()
        for linha in caminho.read_text().splitlines()
        if linha.count("\t") >= 2
    ]


def rodar_cenario(cid: str, variante: str, nome: str, fn: Callable, resultados: dict) -> None:
    inicio = time.time()
    item = resultados.setdefault(cid, {"id": cid, "nome": nome, "resultado": "PASSOU"})
    sub: dict[str, Any] = {"inicio": datetime.now(FUSO).isoformat(timespec="seconds")}
    try:
        sub["evidencia"] = fn(variante) if variante != "-" else fn()
        sub["resultado"] = "PASSOU"
    except NaoAplicavel as na:
        sub.update(resultado="NÃO APLICÁVEL", motivo=na.motivo, evidencia=na.evidencia)
    except Exception as exc:
        sub["resultado"] = "FALHOU"
        sub["erro"] = f"{type(exc).__name__}: {exc}"[:3000]
        sub["traceback"] = traceback.format_exc()[-2500:]
        if cid == "T1" and E.get("t1", {}).get("evid"):
            sub["evidencia"] = E["t1"]["evid"]
        if cid == "TW3" and E.get("tw3"):
            sub["evidencia"] = E["tw3"]
        with contextlib.suppress(Exception):
            sub["log_n8n"] = n8n_local.logs(25).splitlines()[-25:]
    sub["segundos"] = round(time.time() - inicio, 1)
    if variante == "-":
        item.update(sub)
    else:
        item.setdefault("variantes", {})[variante] = sub
        estados = [v["resultado"] for v in item["variantes"].values()]
        item["resultado"] = (
            "FALHOU"
            if "FALHOU" in estados
            else "PASSOU"
            if "PASSOU" in estados
            else "NÃO APLICÁVEL"
        )
    print(
        f"{cid} {variante}: {sub['resultado']} ({sub['segundos']}s) "
        f"{sub.get('erro', sub.get('motivo', ''))[:300]}",
        flush=True,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manter", action="store_true")
    ap.add_argument("--sem-exportar", action="store_true")
    ap.add_argument("--apenas", default="")
    ap.add_argument("--relatorio", type=Path, default=RELATORIO)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    if n8n_local.existe():
        print(f"contêiner {n8n_local.CONTEINER} já existe (outra execução?) — abortado")
        return 2
    if ocupadas := portas_abertas():
        print(f"portas da suíte ocupadas (outra execução?) — abortado: {ocupadas}")
        return 2
    filtro = {x.strip().upper() for x in a.apenas.split(",") if x.strip()}
    SAIDA.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="pcpr-real-"))
    env = ambiente_pcpr(tmp)
    os.environ.update(env)
    instalar_guarda()
    sys.path.insert(0, str(REPO))
    E["procs"] = []
    relatorio: dict[str, Any] = {
        "inicio": datetime.now(FUSO).isoformat(timespec="seconds"),
        "codigo_do_pcpr": impressao_do_codigo(),
        "imagem_n8n": n8n_local.IMAGEM,
        "python": sys.version.split()[0],
        "portas": PORTAS,
        "garantias": {
            "pcpr": "real (runserver do worktree, APP_ENV=lab, PostgreSQL descartável em tmpfs, "
            "AUTOMACAO_TRANSPORTE=n8n)",
            "graph_api": f"simulada em 127.0.0.1:{PORTAS['graph']}; no contêiner "
            + ", ".join(h.split(":")[0] for h in SUMIDOURO)
            + " → 127.0.0.1",
            "guarda_de_rede_no_pcpr": "sitecustomize: só 127.0.0.1/localhost resolvem",
            "segredos": "sintéticos, gerados nesta execução; o token da API só em memória e num "
            "arquivo temporário fora do repositório, apagado no fim",
            "numeros": "fictícios 5523999990001… (DDD 23 não existe)",
        },
        "cenarios": [],
    }
    resultados: dict[str, dict] = {}
    try:
        relatorio["postgres_s"] = round(subir_postgres(), 1)
        relatorio["migrate_s"] = round(migrar(env, tmp), 1)
        carregar_django()
        relatorio["cenario"] = montar_cenario()
        (tmp / "token-api.txt").write_text(SEGREDOS["token_api"], encoding="utf-8")
        subir_processos(tmp, env)
        imp = tmp / "importar"
        cw.construir(imp / "workflows", alvo="pcpr")
        (imp / "credenciais.json").write_text(json.dumps(credenciais_n8n()), encoding="utf-8")
        t0 = time.time()
        log_prep = n8n_local.preparar(imp, SEGREDOS["n8n_cripto"], list(cw.ARQUIVOS_PCPR))
        relatorio["preparacao_n8n"] = {
            "segundos": round(time.time() - t0, 1),
            "saida_cli": log_prep.strip().splitlines()[-14:],
        }
        shutil.rmtree(imp, ignore_errors=True)
        n8n_local.subir(SEGREDOS["n8n_cripto"], hosts_extras=SUMIDOURO)
        E["subida_n8n"] = time.time()
        relatorio["primeira_subida_n8n_s"] = round(n8n_local.esperar_pronto(), 1)
        esperar(lambda: http("GET", f"{N8N}/webhook/whatsapp")[0] == 403, 60, "W7 não registrou")
        relatorio["config_efetiva_n8n"] = n8n_local.config_efetiva()
        relatorio["nos_oficiais_whatsapp_na_imagem"] = versoes_graph_nos_oficiais()
        E["trabalhador"] = Trabalhador()
        E["trabalhador"].start()
        resetar_graph()
        for cid, variante, nome, fn in CENARIOS:
            if cid == "VARRER":
                if not filtro or "TW13" in filtro:
                    try:
                        if variante == "apos_v1":
                            relatorio["controle_positivo_v1"] = controle_positivo_v1()
                        varrer(variante)
                    except Exception as exc:
                        relatorio.setdefault("erros_varredura", {})[variante] = repr(exc)[:600]
                continue
            if filtro and cid not in filtro:
                continue
            rodar_cenario(cid, variante, nome, fn, resultados)
        if not filtro or {"T13", "TW13"} & filtro:
            varrer("imediata")
            espera = max(0.0, 100 - (time.time() - E["subida_n8n"]))
            time.sleep(max(espera, 75))  # hard-delete a cada 1 min (n8n_local.py)
            varrer("apos_hard_delete")
            rodar_cenario("T13", "-", "nada sensível retido no n8n (envio)", t13, resultados)
            rodar_cenario("TW13", "-", "retenção no n8n: V1 × V2", tw13, resultados)
        for cid, motivo in NAO_APLICAVEIS.items():
            if not filtro or cid in filtro:
                resultados[cid] = {"id": cid, "resultado": "NÃO APLICÁVEL", "motivo": motivo}
        relatorio["cenarios"] = sorted(resultados.values(), key=lambda c: _ordem(c["id"]))
        relatorio["defeitos"] = E["defeitos"]
        relatorio["varreduras"] = E["varreduras"]
        relatorio["worker"] = {
            "voltas": E["trabalhador"].voltas,
            "erros": E["trabalhador"].erros[:10],
        }
        relatorio["guarda_de_rede_bloqueou"] = sorted(set(_guarda_hosts()))
        relatorio["n8n_log_menciona_facebook"] = "facebook" in n8n_local.logs(5000).lower()
        if a.manter:
            print("mantido: tudo no ar", flush=True)
            return 0
        E["trabalhador"].parar.set()
        n8n_local.parar()
        if not a.sem_exportar:
            try:
                relatorio["exportacao"] = exportar_workflows(tmp)
            except Exception as exc:
                relatorio["exportacao"] = {"erro": repr(exc)}
        return 0 if all(c["resultado"] != "FALHOU" for c in relatorio["cenarios"]) else 1
    except Exception as exc:
        relatorio["erro_fatal"] = f"{type(exc).__name__}: {exc}"[:3000]
        relatorio["traceback"] = traceback.format_exc()[-3000:]
        for log in tmp.glob("*.log"):
            relatorio.setdefault("logs", {})[log.name] = log.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()[-30:]
        relatorio["cenarios"] = sorted(resultados.values(), key=lambda c: _ordem(c["id"]))
        relatorio["defeitos"] = E["defeitos"]
        print(relatorio["traceback"], flush=True)
        return 3
    finally:
        if not a.manter:
            if "trabalhador" in E:
                E["trabalhador"].parar.set()
                E["trabalhador"].join(10)
            with contextlib.suppress(Exception):
                D.connection.close()
            for p in E.get("procs", []):
                matar(p)
            n8n_local.remover()
            n8n_local.docker("rm", "-f", CONTEINER_PG, check=False)
            shutil.rmtree(tmp, ignore_errors=True)
            time.sleep(1)
            relatorio["limpeza"] = {
                "conteiner_n8n_existe": n8n_local.existe(),
                "volume_n8n_existe": bool(
                    n8n_local.docker(
                        "volume", "ls", "-q", "--filter", f"name={n8n_local.VOLUME}", check=False
                    ).stdout.strip()
                ),
                "conteiner_postgres_existe": CONTEINER_PG
                in n8n_local.docker("ps", "-a", "--format", "{{.Names}}", check=False).stdout,
                "pasta_temporaria_existe": tmp.exists(),
                "portas_ainda_abertas": portas_abertas(),
            }
        relatorio["fim"] = datetime.now(FUSO).isoformat(timespec="seconds")
        texto = json.dumps(relatorio, ensure_ascii=False, indent=2, default=str)
        vazados = [k for k, v in SEGREDOS.items() if v and v in texto]
        for k in vazados:
            texto = texto.replace(SEGREDOS[k], f"<opaco: {k}>")
        texto = re.sub(
            r"pcpr_(test|lab|prod|stg|prev|dev)_[A-Za-z0-9_-]+", r"<opaco: pcpr_\1_…>", texto
        )
        final = json.loads(texto)
        final["segredos_no_relatorio"] = vazados
        a.relatorio.write_text(
            json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        for c in final["cenarios"]:
            print(f"{c['id']:>5}  {c['resultado']:<14} {c.get('nome', '')}")


def _ordem(cid: str) -> tuple:
    m = re.match(r"([A-Z]+)(\d+)", cid)
    return ({"T": 0, "TW": 1, "X": 2}.get(m.group(1), 3), int(m.group(2))) if m else (9, 0)


if __name__ == "__main__":
    sys.exit(main())
