"""Solicitação da viagem: o e-mail do solicitante ou o ofício que pede o evento, anexado na
folha da viagem (1º passo da trilha). Mesmas regras dos anexos da prestação (`anexos.py`):
conferido pelo conteúdo, até 10 MB; aqui também o próprio e-mail (.eml do navegador ou .msg do
Outlook). Remover só marca — o arquivo e a trilha de auditoria ficam."""

from __future__ import annotations

import hashlib

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from . import policies
from .anexos import ASSINATURAS, TAMANHO_MAXIMO, TIPO_DE_CONTEUDO, extensao
from .models import AnexoViagem, Viagem

# O .eml é texto (cabeçalhos do e-mail); o .msg do Outlook é um arquivo OLE.
CABECALHOS_EML = (b"received:", b"return-path:", b"from:", b"date:", b"subject:", b"to:",
                  b"mime-version:", b"message-id:", b"delivered-to:", b"x-", b"dkim-signature:",
                  b"arc-", b"authentication-results:", b"content-type:")
ASSINATURA_MSG = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
TIPOS = {**TIPO_DE_CONTEUDO, ".eml": "message/rfc822", ".msg": "application/vnd.ms-outlook"}
# Abrem no visualizador (PDF e imagem); o e-mail baixa.
VISIVEIS = {".pdf", ".png", ".jpg", ".jpeg"}


class AnexoInvalido(Exception):
    pass


def validar(nome: str, tamanho: int, inicio: bytes) -> None:
    ext = extensao(nome)
    if ext not in TIPOS:
        raise AnexoInvalido("Envie o e-mail (.eml ou .msg), um PDF ou uma imagem (PNG ou JPG).")
    if tamanho > TAMANHO_MAXIMO:
        raise AnexoInvalido("O arquivo excede o limite de 10 MB.")
    if ext == ".eml":
        primeira = inicio.lstrip().lower()
        valido = any(primeira.startswith(c) for c in CABECALHOS_EML)
    elif ext == ".msg":
        valido = inicio.startswith(ASSINATURA_MSG)
    else:
        valido = any(inicio.startswith(a) for a in ASSINATURAS[ext])
    if not valido:
        raise AnexoInvalido("O conteúdo do arquivo não confere com o tipo informado.")


def ativos(viagem: Viagem):
    return viagem.anexos.filter(removido_em__isnull=True).select_related("enviado_por")


@transaction.atomic
def anexar(usuario, viagem_pk: int, arquivo, tipo: str) -> AnexoViagem:
    viagem = Viagem.objects.select_for_update().get(pk=viagem_pk)
    policies.exigir(policies.pode_editar_viagem(usuario, viagem),
                    "Esta viagem não pode ser alterada.")
    if tipo not in AnexoViagem.Tipo.values:
        raise AnexoInvalido("Escolha o que é o arquivo: e-mail, ofício ou outro documento.")
    if arquivo is None:
        raise AnexoInvalido("Escolha o arquivo.")
    conteudo = arquivo.read(TAMANHO_MAXIMO + 1)
    nome = (getattr(arquivo, "name", "") or "")[-255:]
    validar(nome, len(conteudo), conteudo[:512])
    anexo = AnexoViagem(viagem=viagem, tipo=tipo, nome_original=nome,
                        sha256=hashlib.sha256(conteudo).hexdigest(), tamanho=len(conteudo),
                        enviado_por=usuario)
    anexo.arquivo.save(f"solicitacao{extensao(nome)}", ContentFile(conteudo), save=False)
    anexo.save()
    return anexo


@transaction.atomic
def remover(usuario, anexo_pk: int) -> AnexoViagem:
    anexo = AnexoViagem.objects.select_for_update().select_related("viagem").get(pk=anexo_pk)
    policies.exigir(policies.pode_editar_viagem(usuario, anexo.viagem),
                    "Esta viagem não pode ser alterada.")
    if anexo.removido_em is None:
        anexo.removido_em = timezone.now()
        anexo.save(update_fields=["removido_em"])
    return anexo
