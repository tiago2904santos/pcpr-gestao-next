"""O link de assinatura da agenda (A2c): gerar (o token aparece uma vez — só o hash fica no
banco), trocar (o anterior deixa de valer), revogar e achar a pessoa pelo token. O link
também cai sozinho quando a senha muda (o selo guarda uma impressão da senha atual) e
quando a conta é desativada."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .models import AssinaturaAgenda

USO_A_CADA = timedelta(hours=1)  # "última busca" gravada no máximo de hora em hora


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def _selo(usuario) -> str:
    return _hash(f"assinatura-agenda:{usuario.password}")[:32]


def gerar(usuario) -> str:
    """Um token novo para a pessoa (o anterior deixa de valer). Devolve o token em claro."""
    token = secrets.token_urlsafe(32)
    AssinaturaAgenda.objects.update_or_create(
        usuario=usuario, defaults={"token_hash": _hash(token), "selo": _selo(usuario),
                                   "gerada_em": timezone.now(), "usada_em": None})
    return token


def revogar(usuario) -> bool:
    apagadas, _ = AssinaturaAgenda.objects.filter(usuario=usuario).delete()
    return bool(apagadas)


def da_pessoa(usuario) -> AssinaturaAgenda | None:
    a = AssinaturaAgenda.objects.filter(usuario=usuario).first()
    return a if a is not None and a.selo == _selo(usuario) else None


def dono(token: str):
    """A pessoa ativa dona do token, ou None (token desconhecido, malformado, de conta
    desativada ou de antes da última troca de senha — sem dizer qual)."""
    if not token or len(token) > 100:
        return None
    a = (AssinaturaAgenda.objects.select_related("usuario")
         .filter(token_hash=_hash(token), usuario__is_active=True).first())
    if a is None or a.selo != _selo(a.usuario):
        return None
    agora = timezone.now()
    AssinaturaAgenda.objects.filter(pk=a.pk).filter(
        Q(usada_em__isnull=True) | Q(usada_em__lt=agora - USO_A_CADA)).update(usada_em=agora)
    return a.usuario
