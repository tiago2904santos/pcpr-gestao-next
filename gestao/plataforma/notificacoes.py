"""Notificações no sistema (o sino), paridade com `core/notificacoes.py` da referência.

Um aviso para N pessoas vira N linhas (`Notificacao`, uma por destinatário). `notificar`
tira repetidos e inativos, exclui quem fez a ação (`exceto`) e corta título e mensagem no
tamanho da coluna (um texto longo não derruba a operação que avisa). O e-mail, quando
ligado (`NOTIFICACOES_POR_EMAIL`), sai pela outbox depois do commit — nunca na requisição.

Quem avisa o quê é de cada módulo (a referência avisa na prestação de contas, nas
solicitações e no resumo do dia); aqui é só o mecanismo.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from . import outbox
from .models import Notificacao

TITULO_MAX = Notificacao._meta.get_field("titulo").max_length or 150
MENSAGEM_MAX = Notificacao._meta.get_field("mensagem").max_length or 255
LINK_MAX = Notificacao._meta.get_field("link").max_length or 255


def _cabe(texto: str, limite: int) -> str:
    texto = " ".join((texto or "").split())
    return texto if len(texto) <= limite else texto[:limite - 1].rstrip() + "…"


def usuarios_do_grupo(nome: str):
    return get_user_model().objects.filter(groups__name=nome, is_active=True).distinct()


@transaction.atomic
def notificar(usuarios: Iterable, titulo: str, mensagem: str = "", link: str = "", *,
              exceto=None) -> list[Notificacao]:
    vistos: dict[int, object] = {}
    for u in usuarios:
        if u is None or not getattr(u, "is_active", False):
            continue
        if exceto is not None and u.pk == getattr(exceto, "pk", None):
            continue
        vistos.setdefault(u.pk, u)
    if not vistos:
        return []
    titulo, mensagem = _cabe(titulo, TITULO_MAX), _cabe(mensagem, MENSAGEM_MAX)
    link = link if len(link) <= LINK_MAX else ""
    criadas = Notificacao.objects.bulk_create(
        [Notificacao(usuario_id=pk, titulo=titulo, mensagem=mensagem, link=link)
         for pk in vistos])
    if getattr(settings, "NOTIFICACOES_POR_EMAIL", False):
        enderecos = sorted({e for u in vistos.values() if (e := getattr(u, "email", ""))})
        if enderecos:
            outbox.publicar("plataforma.email.enviar",
                            {"para": enderecos, "assunto": titulo, "mensagem": mensagem,
                             "link": link},
                            chave=f"email-notificacao:{criadas[0].pk}")
    return criadas


def nao_lidas(usuario) -> int:
    if usuario is None or not usuario.is_authenticated:
        return 0
    return Notificacao.objects.filter(usuario=usuario, lida=False).count()


@outbox.assinante("plataforma.email.enviar")
def enviar_email(payload: dict) -> None:
    """Um e-mail para todos os destinatários do aviso. O backend vem do ambiente (console
    por padrão: nada sai da máquina sem configuração explícita de SMTP)."""
    from django.core.mail import send_mail

    corpo = payload.get("mensagem") or payload.get("assunto", "")
    if payload.get("link"):
        corpo += f"\n\nAcesse: {settings.URL_PUBLICA.rstrip('/')}{payload['link']}"
    send_mail(f"[{settings.INSTITUICAO['sigla']}] {payload.get('assunto', '')}", corpo,
              settings.DEFAULT_FROM_EMAIL, list(payload.get("para") or []))
