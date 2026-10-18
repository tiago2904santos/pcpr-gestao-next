"""O contrato com o canal WhatsApp, em primitivos.

Saída: `MensagemSaida` (texto livre dentro da janela de 24 h, ou modelo aprovado fora dela)
→ `Envio` (o provedor ACEITOU; entregue/lida chegam depois, por webhook).
Entrada: o webhook vira `Lote` com `StatusRecebido` e `MensagemRecebida` (ver `webhook.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class Origem(StrEnum):
    SIMULADO = "simulado"    # nada saiu para a rede
    CLOUD_API = "cloud_api"  # Meta, de verdade


@dataclass(frozen=True)
class ModeloSaida:
    nome: str
    idioma: str = "pt_BR"
    parametros: tuple[str, ...] = ()


@dataclass(frozen=True)
class MensagemSaida:
    para: str                       # E.164 só com dígitos (ex.: 5541999990000)
    texto: str                      # o texto livre (ou o que o modelo diz, para o registro)
    referencia: str                 # id interno (vai em biz_opaque_callback_data)
    modelo: ModeloSaida | None = None
    responder_a: str = ""           # wamid de contexto (resposta citando a mensagem)
    para_usuario: str = ""          # BSUID, quando conhecido (a Meta ainda não aceita só ele)


@dataclass(frozen=True)
class Envio:
    mensagem_id: str                # wamid
    wa_id: str = ""                 # como a Meta normalizou o número (9º dígito no Brasil)
    usuario_id: str = ""            # BSUID devolvido
    situacao: str = "accepted"      # accepted | held_for_quality_assessment | paused
    origem: Origem = Origem.SIMULADO


@dataclass(frozen=True)
class Preco:
    categoria: str = ""             # utility | marketing | authentication | service …
    tipo: str = ""                  # regular | free_customer_service | free_entry_point
    cobravel: bool | None = None    # `billable` (vai ser descontinuado pela Meta)


@dataclass(frozen=True)
class StatusRecebido:
    mensagem_id: str
    status: str                     # sent | delivered | read | failed | played
    ocorrido_em: datetime | None
    destinatario: str = ""          # recipient_id (pode faltar com BSUID)
    destinatario_usuario: str = ""  # recipient_user_id
    referencia: str = ""            # biz_opaque_callback_data
    erro_codigo: str = ""
    erro_detalhe: str = ""
    preco: Preco | None = None


@dataclass(frozen=True)
class Anexo:
    midia_id: str
    tipo: str                       # document | image | audio | video | sticker
    mime: str = ""
    sha256: str = ""                # como veio (base64 ou hex)
    nome: str = ""
    legenda: str = ""
    url: str = ""                   # vale 5 min; pedir de novo se vencer


@dataclass(frozen=True)
class MensagemRecebida:
    mensagem_id: str
    tipo: str                       # text | document | image | interactive | button | outro
    recebida_em: datetime | None
    remetente: str = ""             # from (pode faltar com BSUID)
    remetente_usuario: str = ""     # from_user_id (BSUID)
    nome_perfil: str = ""
    texto: str = ""                 # corpo do texto, legenda ou rótulo do botão
    resposta_id: str = ""           # id do botão de resposta
    em_resposta_a: str = ""         # context.id (o wamid que a pessoa respondeu)
    anexo: Anexo | None = None
    erro_codigo: str = ""


@dataclass(frozen=True)
class Lote:
    status: tuple[StatusRecebido, ...] = field(default_factory=tuple)
    mensagens: tuple[MensagemRecebida, ...] = field(default_factory=tuple)
    erros: tuple[str, ...] = field(default_factory=tuple)  # códigos de erro de conta/sistema
    ignorados: int = 0


@dataclass(frozen=True)
class MidiaBaixada:
    conteudo: bytes
    mime: str
    sha256_hex: str


class PortaWhatsapp(Protocol):
    origem: Origem

    def enviar(self, mensagem: MensagemSaida, simular: str = "") -> Envio: ...

    def baixar_midia(self, anexo: Anexo, limite: int) -> MidiaBaixada: ...

    def marcar_lida(self, mensagem_id: str) -> None: ...
