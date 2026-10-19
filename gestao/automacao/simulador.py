"""Simulador do WhatsApp para o LAB, o DEV e o PREVIEW: produz exatamente o corpo que a Meta
mandaria (status de entrega, resposta com texto ou arquivo) e o entrega pelo mesmo caminho do
webhook real — gravação, worker, identificação, download, associação. Nada sai da máquina.

Só existe com o canal simulado: com a Cloud API configurada, toda função recusa.
"""

from __future__ import annotations

import base64
import hashlib
import secrets

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from gestao.integracoes.whatsapp import config as whatsapp_config
from gestao.integracoes.whatsapp import webhook
from gestao.integracoes.whatsapp.adaptadores import PREFIXO_SIMULADO, tipo_pelos_bytes
from gestao.integracoes.whatsapp.porta import Anexo

from . import dominio, entrada, policies
from .models import Comunicacao

STATUS = {"entregue": "delivered", "lida": "read", "falhou": "failed", "enviada": "sent"}
LIMITE = 10 * 1024 * 1024


class SimuladorIndisponivel(Exception):
    pass


def disponivel() -> bool:
    return not whatsapp_config.carregar().real


def _exigir(usuario) -> None:
    policies.exigir(policies.pode_operar(usuario), "O simulador é de quem opera a automação.")
    if not disponivel():
        raise SimuladorIndisponivel("Com a Cloud API ligada não existe simulador.")


def _comunicacao(usuario, pk: int) -> Comunicacao:
    c = Comunicacao.objects.select_related("contato").get(pk=pk)
    policies.exigir(policies.pode_operar_objeto(usuario, c))
    return c


def simular_status(usuario, pk: int, status: str, erro_codigo: str = "") -> None:
    _exigir(usuario)
    c = _comunicacao(usuario, pk)
    if status not in STATUS:
        raise SimuladorIndisponivel("Status simulado inválido.")
    if not c.mensagem_id:
        raise SimuladorIndisponivel("A mensagem ainda não saiu: não há o que confirmar.")
    if status == "falhou" and not erro_codigo:
        erro_codigo = "131026"
    corpo = webhook.montar_status(mensagem_id=c.mensagem_id, status=STATUS[status],
                                  destinatario=getattr(c.contato, "endereco", ""),
                                  erro_codigo=erro_codigo,
                                  referencia=f"com:{c.pk}:t{c.tentativas}")
    entrada.registrar_entrada(corpo, origem="simulador")


def _guardar_midia(conteudo: bytes) -> tuple[str, str, str]:
    """Guarda como se estivesse na Meta; devolve (id, mime declarado, sha256 base64)."""
    midia_id = "SIM" + secrets.token_hex(12).upper()
    default_storage.save(PREFIXO_SIMULADO + midia_id, ContentFile(conteudo))
    sha = base64.b64encode(hashlib.sha256(conteudo).digest()).decode()
    return midia_id, tipo_pelos_bytes(conteudo) or "application/octet-stream", sha


def simular_resposta(usuario, pk: int, *, texto: str = "", conteudo: bytes | None = None,
                     nome: str = "") -> None:
    """O servidor responde à comunicação (citando a mensagem, como no app)."""
    _exigir(usuario)
    c = _comunicacao(usuario, pk)
    if c.contato is None:
        raise SimuladorIndisponivel("A comunicação não tem contato: não há quem responda.")
    anexo = None
    if conteudo:
        if len(conteudo) > LIMITE:
            raise SimuladorIndisponivel("Arquivo acima de 10 MB.")
        midia_id, mime, sha = _guardar_midia(conteudo)
        tipo = "image" if mime.startswith("image/") else "document"
        anexo = Anexo(midia_id=midia_id, tipo=tipo, mime=mime, sha256=sha,
                      nome=(nome or "comprovante.pdf")[:120], legenda=texto[:1024])
    corpo = webhook.montar_mensagem(
        mensagem_id="wamid.SIMIN." + secrets.token_hex(12).upper(), remetente=c.contato.endereco,
        texto=texto, anexo=anexo, em_resposta_a=c.mensagem_id,
        nome_perfil=c.contato.servidor.nome.split(" ")[0],
        remetente_usuario=c.contato.usuario_canal)
    entrada.registrar_entrada(corpo, origem="simulador")


def simular_mensagem(usuario, telefone: str, texto: str) -> None:
    """Uma mensagem espontânea de um número (de um contato ou desconhecido). Só quem
    administra: o número pode ser de qualquer unidade."""
    _exigir(usuario)
    policies.exigir(policies.pode_administrar(usuario),
                    "Mensagem de um número qualquer só para quem administra a automação.")
    endereco = dominio.e164_do_brasil(telefone)
    if not endereco:
        raise SimuladorIndisponivel("Telefone inválido.")
    corpo = webhook.montar_mensagem(
        mensagem_id="wamid.SIMIN." + secrets.token_hex(12).upper(), remetente=endereco,
        texto=texto[:1000])
    entrada.registrar_entrada(corpo, origem="simulador")


def processar_agora(usuario) -> int:
    """Roda o worker uma vez, na própria requisição (só no simulado: não há rede)."""
    _exigir(usuario)
    from .management.commands.processar_automacao import rodada

    total = 0
    for _ in range(10):
        feitos = rodada()
        total += feitos
        if not feitos:
            break
    return total
