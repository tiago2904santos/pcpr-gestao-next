"""Webhook da Cloud API: verificação da inscrição (GET), assinatura do corpo bruto e leitura
tolerante do payload (seção 5 da referência).

A leitura não confia em nada: campos ausentes viram vazio, tipos estranhos são contados em
`ignorados`, e há teto de itens para um corpo malicioso não virar milhares de registros.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import UTC, datetime
from typing import Any

from .erros import PayloadInvalido
from .porta import Anexo, Lote, MensagemRecebida, Preco, StatusRecebido

TAMANHO_MAXIMO = 3 * 1024 * 1024  # a Meta manda até 3 MB por payload
MAXIMO_DE_ITENS = 1000            # lote da Meta: até 1000 atualizações
TIPOS_DE_MIDIA = ("document", "image", "audio", "video", "sticker")


def assinatura_valida(corpo: bytes, cabecalho: str | None, segredo: str) -> bool:
    """`X-Hub-Signature-256: sha256=<hex>` = HMAC-SHA256(App Secret, corpo bruto)."""
    if not segredo or not cabecalho:
        return False
    prefixo, _, recebido = cabecalho.strip().partition("=")
    if prefixo.lower() != "sha256" or len(recebido) != 64:
        return False
    esperado = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, recebido.lower())


def assinar(corpo: bytes, segredo: str) -> str:
    """O cabeçalho que a Meta mandaria (para os testes e o simulador)."""
    return "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()


_DESAFIO = re.compile(r"[A-Za-z0-9_-]+")


def desafio(parametros: dict[str, str], verify_token: str) -> str | None:
    """GET de inscrição: devolve o `hub.challenge` quando o token confere, senão None."""
    if not verify_token:
        return None
    if parametros.get("hub.mode") != "subscribe":
        return None
    recebido = parametros.get("hub.verify_token") or ""
    if not hmac.compare_digest(recebido.encode(), verify_token.encode()):
        return None
    challenge = parametros.get("hub.challenge") or ""
    # A Meta manda um número; só ecoa [A-Za-z0-9_-] (nada de HTML/JS refletido, mesmo em
    # text/plain).
    if not challenge or len(challenge) > 200 or not _DESAFIO.fullmatch(challenge):
        return None
    return challenge


# ----------------------------------------------------------------------- leitura
def _texto(valor: Any, limite: int = 4096) -> str:
    if valor is None or isinstance(valor, dict | list):
        return ""
    return str(valor)[:limite]


def _quando(valor: Any) -> datetime | None:
    texto = _texto(valor, 20)
    if not texto.isdigit():
        return None
    try:
        return datetime.fromtimestamp(int(texto), tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _dict(valor: Any) -> dict[str, Any]:
    return valor if isinstance(valor, dict) else {}


def _lista(valor: Any) -> list[Any]:
    return valor if isinstance(valor, list) else []


def _erro(itens: Any) -> tuple[str, str]:
    for e in _lista(itens):
        e = _dict(e)
        codigo = _texto(e.get("code"), 20)
        detalhe = _texto(_dict(e.get("error_data")).get("details") or e.get("title"), 255)
        if codigo:
            return codigo, detalhe
    return "", ""


def _status(s: dict[str, Any]) -> StatusRecebido | None:
    mensagem_id, status = _texto(s.get("id"), 128), _texto(s.get("status"), 20).lower()
    if not mensagem_id or not status:
        return None
    preco = None
    if isinstance(s.get("pricing"), dict):
        p = s["pricing"]
        cobravel = p.get("billable")
        preco = Preco(categoria=_texto(p.get("category"), 40), tipo=_texto(p.get("type"), 40),
                      cobravel=cobravel if isinstance(cobravel, bool) else None)
    codigo, detalhe = _erro(s.get("errors"))
    return StatusRecebido(
        mensagem_id=mensagem_id, status=status, ocorrido_em=_quando(s.get("timestamp")),
        destinatario=_texto(s.get("recipient_id"), 20),
        destinatario_usuario=_texto(s.get("recipient_user_id"), 140),
        referencia=_texto(s.get("biz_opaque_callback_data"), 512),
        erro_codigo=codigo, erro_detalhe=detalhe, preco=preco)


def _mensagem(m: dict[str, Any], perfis: dict[str, str]) -> MensagemRecebida | None:
    mensagem_id, tipo = _texto(m.get("id"), 128), _texto(m.get("type"), 20).lower()
    if not mensagem_id or not tipo:
        return None
    remetente = _texto(m.get("from"), 20)
    remetente_usuario = _texto(m.get("from_user_id"), 140)
    texto, resposta_id, anexo = "", "", None
    if tipo == "text":
        texto = _texto(_dict(m.get("text")).get("body"))
    elif tipo in TIPOS_DE_MIDIA:
        bruto = _dict(m.get(tipo))
        texto = _texto(bruto.get("caption"), 1024)
        midia_id = _texto(bruto.get("id"), 128)
        if not midia_id:
            return None  # mídia sem id: malformada (contada em `ignorados`), nada a baixar
        anexo = Anexo(midia_id=midia_id, tipo=tipo, mime=_texto(bruto.get("mime_type"), 100),
                      sha256=_texto(bruto.get("sha256"), 100),
                      nome=_texto(bruto.get("filename"), 255), legenda=texto,
                      url=_texto(bruto.get("url"), 2000))
    elif tipo == "interactive":
        bruto = _dict(m.get("interactive"))
        botao = _dict(bruto.get("button_reply") or bruto.get("list_reply"))
        resposta_id, texto = _texto(botao.get("id"), 256), _texto(botao.get("title"), 100)
    elif tipo == "button":  # botão de resposta rápida de modelo
        bruto = _dict(m.get("button"))
        resposta_id, texto = _texto(bruto.get("payload"), 256), _texto(bruto.get("text"), 100)
    else:
        tipo = "outro"
    codigo, _ = _erro(m.get("errors"))
    chave_perfil = remetente_usuario or remetente
    return MensagemRecebida(
        mensagem_id=mensagem_id, tipo=tipo, recebida_em=_quando(m.get("timestamp")),
        remetente=remetente, remetente_usuario=remetente_usuario,
        nome_perfil=perfis.get(chave_perfil, ""), texto=texto, resposta_id=resposta_id,
        em_resposta_a=_texto(_dict(m.get("context")).get("id"), 128), anexo=anexo,
        erro_codigo=codigo)


def ler(corpo: bytes, numero_esperado: str = "") -> Lote:
    """Corpo bruto → `Lote`. Malformado, grande demais ou de outro objeto → PayloadInvalido.
    Com `numero_esperado` (o phone_number_id configurado), mudanças de outro número são
    ignoradas — o mesmo app da Meta pode servir números de outros ambientes."""
    if len(corpo) > TAMANHO_MAXIMO:
        raise PayloadInvalido("Corpo do webhook acima de 3 MB.", "grande")
    try:
        dados = json.loads(corpo.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise PayloadInvalido("Corpo do webhook não é JSON válido.", "json") from erro
    if not isinstance(dados, dict) or dados.get("object") != "whatsapp_business_account":
        raise PayloadInvalido("Webhook de outro objeto (não é WhatsApp Business).", "objeto")
    status: list[StatusRecebido] = []
    mensagens: list[MensagemRecebida] = []
    erros: list[str] = []
    ignorados = 0
    for entrada in _lista(dados.get("entry")):
        for mudanca in _lista(_dict(entrada).get("changes")):
            mudanca = _dict(mudanca)
            valor = _dict(mudanca.get("value"))
            if mudanca.get("field") != "messages":
                ignorados += 1
                continue
            numero = _texto(_dict(valor.get("metadata")).get("phone_number_id"), 40)
            if numero_esperado and numero != numero_esperado:
                ignorados += 1
                continue
            perfis = {}
            for c in _lista(valor.get("contacts")):
                c = _dict(c)
                nome = _texto(_dict(c.get("profile")).get("name"), 120)
                for chave in (_texto(c.get("user_id"), 140), _texto(c.get("wa_id"), 20)):
                    if chave:
                        perfis[chave] = nome
            for s in _lista(valor.get("statuses")):
                _contar_item(status, mensagens, ignorados)  # o teto vale ANTES de processar
                lido = _status(_dict(s))
                if lido is None:
                    ignorados += 1
                else:
                    status.append(lido)
            for m in _lista(valor.get("messages")):
                _contar_item(status, mensagens, ignorados)
                lida = _mensagem(_dict(m), perfis)
                if lida is None:
                    ignorados += 1
                else:
                    mensagens.append(lida)
            codigo, _ = _erro(valor.get("errors"))
            if codigo:
                erros.append(codigo)
            if len(status) + len(mensagens) > MAXIMO_DE_ITENS:
                raise PayloadInvalido("Webhook com itens demais.", "itens")
    return Lote(tuple(status), tuple(mensagens), tuple(erros), ignorados)


def _contar_item(status: list, mensagens: list, ignorados: int) -> None:
    """Teto de itens por corpo, conferido a cada item (inclusive os malformados, que só
    contam como ignorados): um corpo assinado gigante não consome CPU/memória até o fim."""
    if len(status) + len(mensagens) + ignorados >= MAXIMO_DE_ITENS:
        raise PayloadInvalido("Webhook com itens demais.", "itens")


# ------------------------------------------------------------- montagem (simulador)
def montar_status(*, mensagem_id: str, status: str, destinatario: str, referencia: str = "",
                  quando: datetime | None = None, erro_codigo: str = "",
                  phone_number_id: str = "SIMULADO") -> bytes:
    """O corpo que a Meta mandaria para um status (o simulador usa o mesmo caminho)."""
    item: dict[str, Any] = {
        "id": mensagem_id, "status": status,
        "timestamp": str(int((quando or datetime.now(tz=UTC)).timestamp())),
        "recipient_id": destinatario}
    if referencia:
        item["biz_opaque_callback_data"] = referencia
    if status in ("sent", "delivered"):  # a Meta manda `pricing` no sent e em um dos outros
        item["pricing"] = {"billable": False, "pricing_model": "PMP",
                           "type": "free_customer_service", "category": "service"}
    if erro_codigo:
        item["errors"] = [{"code": int(erro_codigo) if erro_codigo.isdigit() else erro_codigo,
                           "title": "Simulado", "error_data": {"details": "Falha simulada"}}]
    return _envelope(phone_number_id, {"statuses": [item]})


def montar_mensagem(*, mensagem_id: str, remetente: str, texto: str = "",
                    anexo: Anexo | None = None, em_resposta_a: str = "", nome_perfil: str = "",
                    quando: datetime | None = None, remetente_usuario: str = "",
                    phone_number_id: str = "SIMULADO") -> bytes:
    m: dict[str, Any] = {"from": remetente, "id": mensagem_id,
                         "timestamp": str(int((quando or datetime.now(tz=UTC)).timestamp()))}
    if remetente_usuario:
        m["from_user_id"] = remetente_usuario
    if anexo is not None:
        m["type"] = anexo.tipo
        m[anexo.tipo] = {k: v for k, v in {
            "id": anexo.midia_id, "mime_type": anexo.mime, "sha256": anexo.sha256,
            "filename": anexo.nome, "caption": anexo.legenda or texto}.items() if v}
    else:
        m["type"] = "text"
        m["text"] = {"body": texto}
    if em_resposta_a:
        m["context"] = {"from": "SIMULADO", "id": em_resposta_a}
    contato = {"profile": {"name": nome_perfil or "Testador"}, "wa_id": remetente}
    if remetente_usuario:
        contato["user_id"] = remetente_usuario
    return _envelope(phone_number_id, {"contacts": [contato], "messages": [m]})


def _envelope(phone_number_id: str, valor: dict[str, Any]) -> bytes:
    corpo = {"object": "whatsapp_business_account", "entry": [{
        "id": "SIMULADO", "changes": [{"field": "messages", "value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "SIMULADO", "phone_number_id": phone_number_id},
            **valor}}]}]}
    return json.dumps(corpo, ensure_ascii=False).encode()
