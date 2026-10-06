"""Vias dos documentos do Coffee Break (CB4; paridade com `coffee_break/vias.py`): o que sai
fica guardado; a assinada vale no lugar do gerado. Mensagens da referência."""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from . import documentos, policies
from .forms import MSG_PDF, conferir_pdf
from .models import Movimento, Solicitacao, Via
from .pedidos import PedidoInvalido

MSG_ESCOLHA = "Escolha o PDF assinado."
MSG_ANEXADA = ("Documento assinado anexado. Ele passa a valer no lugar do gerado; a versão "
               "anterior fica guardada.")
MSG_REMOVIDA = "Versão assinada removida. O PDF gerado volta a valer."
MSG_BLOQUEADA = "Solicitações canceladas ou concluídas não recebem documento assinado."


@dataclass
class Arquivo:
    conteudo: bytes
    nome: str
    assinada: bool


def assinada_vigente(s: Solicitacao, tipo: str) -> Via | None:
    return (s.vias.filter(tipo=tipo, assinada=True, removida_em__isnull=True)
            .order_by("-emitida_em", "-pk").first())


@transaction.atomic
def obter(usuario, s: Solicitacao, tipo: str) -> Arquivo:
    """A assinada vigente, senão o PDF gerado agora (guardado como via se mudou)."""
    if not policies.pode_acessar(usuario):
        raise PermissionDenied
    faltas = documentos.pendencias(tipo, s)
    if faltas:
        raise PedidoInvalido(" ".join(faltas))
    via = assinada_vigente(s, tipo) if tipo in documentos.ASSINAVEIS else None
    if via is not None:
        with via.arquivo.open("rb") as f:
            return Arquivo(f.read(), via.nome, True)
    conteudo, folha = documentos.gerar_pdf(tipo, s)
    nome = documentos.nome_do_arquivo(tipo, s)
    resumo = documentos.sha256(folha.encode())
    if tipo not in documentos.ASSINAVEIS:  # o certificado é espelho do momento: não se guarda
        return Arquivo(conteudo, nome, False)
    ultima = s.vias.filter(tipo=tipo, assinada=False).order_by("-emitida_em", "-pk").first()
    if ultima is None or ultima.sha256 != resumo:
        Via.objects.create(solicitacao=s, tipo=tipo, nome=nome, sha256=resumo,
                           emitida_por=usuario, arquivo=ContentFile(conteudo, name=nome))
    return Arquivo(conteudo, nome, False)


@transaction.atomic
def anexar_assinada(usuario, pk: int, tipo: str, arquivo) -> Via:
    if not policies.pode_acessar(usuario):
        raise PermissionDenied
    if tipo not in documentos.ASSINAVEIS:
        raise PedidoInvalido("Este documento não recebe versão assinada.")
    s = Solicitacao.objects.select_for_update().get(pk=pk)
    if s.bloqueada:
        raise PedidoInvalido(MSG_BLOQUEADA)
    if not arquivo:
        raise PedidoInvalido(MSG_ESCOLHA)
    try:
        conferir_pdf(arquivo)
    except ValidationError as exc:  # a mensagem do formulário (PDF, tamanho)
        raise PedidoInvalido(" ".join(exc.messages) or MSG_PDF) from None
    conteudo = arquivo.read()
    nome = documentos.nome_do_arquivo(tipo, s).replace(".pdf", " (assinado).pdf")
    via = Via.objects.create(solicitacao=s, tipo=tipo, nome=nome, assinada=True,
                             sha256=documentos.sha256(conteudo), emitida_por=usuario,
                             arquivo=ContentFile(conteudo, name=nome))
    Movimento.objects.create(solicitacao=s, acao=Movimento.Acao.DOCUMENTO, usuario=usuario,
                             texto=f"{documentos.TIPOS[tipo].titulo}: versão assinada anexada.")
    return via


@transaction.atomic
def remover_assinada(usuario, pk: int, tipo: str) -> None:
    if not policies.pode_acessar(usuario):
        raise PermissionDenied
    s = Solicitacao.objects.select_for_update().get(pk=pk)
    if s.bloqueada:
        raise PedidoInvalido(MSG_BLOQUEADA)
    via = assinada_vigente(s, tipo)
    if via is None:
        raise PedidoInvalido("Não há versão assinada deste documento.")
    via.removida_em = timezone.now()
    via.save(update_fields=["removida_em"])
    Movimento.objects.create(solicitacao=s, acao=Movimento.Acao.DOCUMENTO, usuario=usuario,
                             texto=f"{documentos.TIPOS[tipo].titulo}: versão assinada removida.")
