"""Link de acesso pessoal sem login (LinkAcesso): o link de km na véspera, os documentos do
servidor, a "Minha situação" — o que vai por WhatsApp para uma pessoa abrir no celular.

Segurança (mesmo padrão do link do fornecedor do Coffee Break, ADR 0047):
- o token (`secrets.token_urlsafe(32)`) só existe na mensagem; o banco guarda o SHA-256;
- escopo e recurso fixos: o link de km de um diário não abre outro diário nem outra página;
- validade curta, revogação individual e em massa (roteiro de incidente), e o link novo do
  mesmo escopo/recurso/pessoa revoga o anterior;
- desconhecido, vencido, revogado, de contato revogado ou de outro escopo dão a mesma
  resposta (nada de dizer qual foi);
- o token nunca vai para log (filtro `MascararSegredos` cobre `/p/`) nem para a trilha.

Cada contexto registra a página do seu escopo (`ganchos_link.registrar_pagina`), e a
automação só valida o link e chama a página com o `LinkAcesso` já conferido.
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone

from . import policies
from .models import LinkAcesso

TAMANHO_MINIMO, TAMANHO_MAXIMO = 32, 128
VALIDADE_PADRAO: dict[str, timedelta] = {
    LinkAcesso.Escopo.KM: timedelta(days=4),
    LinkAcesso.Escopo.DOCUMENTOS: timedelta(days=15),
    LinkAcesso.Escopo.ASSINATURA: timedelta(days=10),
    LinkAcesso.Escopo.RELATO: timedelta(days=7),
    LinkAcesso.Escopo.SITUACAO: timedelta(days=2),
}
USO_A_CADA = timedelta(minutes=5)  # não grava "usado em" a cada requisição


class LinkInvalido(Exception):
    pass


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def origem(ip: str) -> str:
    """O IP em hash com a SECRET_KEY: basta para limitar tentativas, não identifica."""
    return hashlib.sha256(f"{settings.SECRET_KEY}:link:{ip or ''}".encode()).hexdigest()[:32]


@dataclass(frozen=True)
class PaginaDeLink:
    escopo: str
    rotulo: str                                         # "Lançar a quilometragem"
    view: Callable                                      # (request, link) -> HttpResponse


_PAGINAS: dict[str, PaginaDeLink] = {}


def registrar_pagina(pagina: PaginaDeLink) -> None:
    _PAGINAS[pagina.escopo] = pagina


def pagina(escopo: str) -> PaginaDeLink | None:
    return _PAGINAS.get(escopo)


def criar(*, escopo: str, recurso: str, servidor_id: int, criado_por=None,
          validade: timedelta | None = None, contato_id: int | None = None,
          comunicacao_id: int | None = None, revogar_anteriores: bool = True
          ) -> tuple[LinkAcesso, str]:
    """Um link novo (o anterior do mesmo escopo/recurso/pessoa deixa de valer). Chamar na
    transação de quem vai mandar a mensagem: se ela desfizer, o link também some. Devolve o
    link e o token em claro — só para montar a mensagem, nunca para guardar."""
    if escopo not in LinkAcesso.Escopo.values:
        raise LinkInvalido("Escopo de link desconhecido.")
    agora = timezone.now()
    if revogar_anteriores:
        with connection.cursor() as cursor:  # dois envios simultâneos não deixam 2 vigentes
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [int.from_bytes(
                hashlib.sha256(f"link:{escopo}:{recurso}:{servidor_id}".encode()).digest()[:8],
                "big", signed=True)])
        LinkAcesso.objects.filter(escopo=escopo, recurso=recurso, servidor_id=servidor_id,
                                  revogado_em__isnull=True).update(
            revogado_em=agora, motivo_revogacao=LinkAcesso.Motivo.LINK_NOVO)
    token = secrets.token_urlsafe(32)
    link = LinkAcesso.objects.create(
        escopo=escopo, recurso=recurso[:80], servidor_id=servidor_id, contato_id=contato_id,
        comunicacao_id=comunicacao_id, token_hash=_hash(token),
        origem=LinkAcesso.Origem.MANUAL if getattr(criado_por, "pk", None)
        else LinkAcesso.Origem.AUTOMATICA,
        criado_por=criado_por if getattr(criado_por, "pk", None) else None,
        expira_em=agora + (validade or VALIDADE_PADRAO.get(escopo, timedelta(days=2))))
    return link, token


def url_publica(token: str) -> str:
    return settings.URL_PUBLICA.rstrip("/") + reverse("link_acesso:abrir", args=[token])


def do_token(token: str, escopo: str | None = None) -> LinkAcesso | None:
    """O link vigente do token, ou None — sem dizer se não existe, venceu ou foi revogado."""
    if not token or not TAMANHO_MINIMO <= len(token) <= TAMANHO_MAXIMO:
        return None
    link = (LinkAcesso.objects.select_related("servidor", "contato")
            .filter(token_hash=_hash(token)).first())
    if link is None or link.revogado_em or link.expira_em <= timezone.now():
        return None
    if escopo is not None and link.escopo != escopo:
        return None
    if link.contato_id and link.contato is not None and link.contato.revogado_em:
        return None  # a pessoa saiu (SAIR): os links dela param junto
    if not link.servidor.ativo:
        return None
    return link


def registrar_uso(link: LinkAcesso, *, lancamento: bool = False) -> None:
    agora = timezone.now()
    campos: dict = {}
    if link.exibido_em is None:
        campos["exibido_em"] = agora
    if link.usado_em is None or agora - link.usado_em > USO_A_CADA:
        campos["usado_em"] = agora
    if lancamento:
        campos["ultimo_lancamento_em"] = agora
        if link.primeiro_lancamento_em is None:
            campos["primeiro_lancamento_em"] = agora
    if campos:
        LinkAcesso.objects.filter(pk=link.pk).update(**campos)
        for chave, valor in campos.items():
            setattr(link, chave, valor)


@transaction.atomic
def revogar(usuario, pk: int, motivo: str = LinkAcesso.Motivo.MANUAL) -> LinkAcesso:
    link = LinkAcesso.objects.select_for_update(of=("self",)).select_related(
        "servidor").get(pk=pk)
    if not policies.pode_cuidar_do_contato(usuario, link.servidor):
        raise LinkAcesso.DoesNotExist  # fora do escopo: 404, como o resto
    if link.revogado_em:
        raise LinkInvalido("Este link já estava revogado.")
    link.revogado_em, link.motivo_revogacao = timezone.now(), motivo
    link.revogado_por = usuario
    link.save(update_fields=["revogado_em", "motivo_revogacao", "revogado_por"])
    return link


@transaction.atomic
def revogar_do_recurso(recurso: str, motivo: str, escopo: str | None = None) -> int:
    """O assunto mudou (ofício cancelado, responsável trocado): os links dele caem."""
    qs = LinkAcesso.objects.filter(recurso=recurso, revogado_em__isnull=True)
    if escopo:
        qs = qs.filter(escopo=escopo)
    return qs.update(revogado_em=timezone.now(), motivo_revogacao=motivo)


@transaction.atomic
def revogar_em_massa(usuario, *, desde, ate=None, motivo: str = LinkAcesso.Motivo.VAZAMENTO
                     ) -> int:
    """Roteiro de incidente: todos os links emitidos no período deixam de valer."""
    policies.exigir(policies.pode_administrar(usuario),
                    "Só quem administra a automação revoga links em massa.")
    qs = LinkAcesso.objects.filter(revogado_em__isnull=True, criado_em__gte=desde)
    if ate is not None:
        qs = qs.filter(criado_em__lte=ate)
    return qs.update(revogado_em=timezone.now(), motivo_revogacao=motivo, revogado_por=usuario)
