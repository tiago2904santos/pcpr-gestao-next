"""Credenciais por integração: transporte (n8n), IA e pessoal — cada uma com escopos mínimos,
ambiente fixo, validade, rotação, revogação e modo emergência. Guardadas só como hash.

Formato do token: `pcpr_<ambiente>_<aleatório>`. O ambiente no próprio token faz o de
produção não valer em teste/preview e vice-versa (401), mesmo que alguém copie o valor.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from gestao.plataforma import ambiente

from .. import policies
from ..models_api import CredencialIntegracao

T = CredencialIntegracao.Tipo

ESCOPOS_TRANSPORTE = (
    "estado:ler", "comunicacoes:ler", "comunicacoes:reservar", "comunicacoes:resultado",
    "comunicacoes:entrega", "recebimentos:criar", "recebimentos:ler", "entradas:criar",
    "assistente:mensagens", "excecoes:criar")
#: O padrão do transporte deixa de fora a entrada V1 de arquivos (o remetente seria o que o
#: n8n diz); quem precisar escolhe o escopo `recebimentos:criar` explicitamente.
PADRAO_TRANSPORTE = tuple(e for e in ESCOPOS_TRANSPORTE if e != "recebimentos:criar")
ESCOPOS_IA = ("estado:ler", "ferramentas:executar")
ESCOPOS_PESSOAL = ("estado:ler", "ferramentas:executar")
ESCOPOS_POR_TIPO: dict[str, tuple[str, ...]] = {
    T.TRANSPORTE: ESCOPOS_TRANSPORTE, T.IA: ESCOPOS_IA, T.PESSOAL: ESCOPOS_PESSOAL}
VALIDADE_MAXIMA: dict[str, int] = {T.TRANSPORTE: 180, T.IA: 90, T.PESSOAL: 30}  # dias
CARENCIA_DA_ROTACAO = timedelta(hours=24)


class CredencialInvalida(Exception):
    pass


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def codigo_do_ambiente() -> str:
    return {"production": "prod", "staging": "stg", "preview": "prev", "lab": "lab",
            "dev": "dev", "test": "test"}.get(ambiente.atual(), "dev")


@transaction.atomic
def emitir(usuario, *, nome: str, tipo: str, escopos: list[str] | None = None,
           dias: int = 30, ferramentas: list[str] | None = None, dono=None,
           substitui: CredencialIntegracao | None = None) -> tuple[CredencialIntegracao, str]:
    """Nova credencial; devolve o token em claro uma única vez."""
    if tipo == T.PESSOAL:
        dono = dono or usuario
        policies.exigir(dono.pk == usuario.pk or policies.pode_administrar(usuario),
                        "Token pessoal só para si mesmo.")
        policies.exigir(policies.pode_ver(dono), "Sem acesso à automação.")
    else:
        policies.exigir(policies.pode_administrar(usuario),
                        "Só quem administra a automação emite credenciais de serviço.")
        dono = None
    if tipo not in T.values:
        raise CredencialInvalida("Tipo de credencial inválido.")
    permitidos = ESCOPOS_POR_TIPO[tipo]
    escopos = list(escopos or (PADRAO_TRANSPORTE if tipo == T.TRANSPORTE else permitidos))
    if any(e not in permitidos for e in escopos):
        raise CredencialInvalida("Escopo fora do que este tipo de credencial pode ter.")
    if tipo == T.TRANSPORTE and ferramentas:
        raise CredencialInvalida("O token de transporte não executa ferramentas.")
    dias = max(1, min(int(dias), VALIDADE_MAXIMA[tipo]))
    token = f"pcpr_{codigo_do_ambiente()}_{secrets.token_urlsafe(32)}"
    credencial = CredencialIntegracao.objects.create(
        nome=nome.strip()[:80] or tipo, tipo=tipo, prefixo=token[:18],
        token_hash=_hash(token), ambiente=codigo_do_ambiente(), escopos=escopos,
        ferramentas=list(ferramentas or []), usuario=dono, criada_por=usuario,
        expira_em=timezone.now() + timedelta(days=dias), substitui=substitui)
    return credencial, token


@transaction.atomic
def rotacionar(usuario, pk: int) -> tuple[CredencialIntegracao, str]:
    """Credencial nova com os mesmos escopos; a antiga vale mais 24 h (troca sem parada)."""
    antiga = CredencialIntegracao.objects.select_for_update().get(pk=pk)
    if antiga.tipo == T.PESSOAL:
        # Rotacionar devolve um token que age como o dono: só o próprio dono pode.
        policies.exigir(antiga.usuario_id == usuario.pk,
                        "Token pessoal só é rotacionado pelo próprio dono.")
    _exigir_gestao(usuario, antiga)
    if antiga.revogada_em:
        raise CredencialInvalida("Credencial revogada não se rotaciona: emita uma nova.")
    nova, token = emitir(usuario, nome=antiga.nome, tipo=antiga.tipo, escopos=antiga.escopos,
                         ferramentas=antiga.ferramentas, dono=antiga.usuario,
                         dias=VALIDADE_MAXIMA[antiga.tipo], substitui=antiga)
    limite = timezone.now() + CARENCIA_DA_ROTACAO
    if antiga.expira_em > limite:
        antiga.expira_em = limite
        antiga.save(update_fields=["expira_em"])
    return nova, token


def _exigir_gestao(usuario, credencial: CredencialIntegracao) -> None:
    if credencial.tipo == T.PESSOAL and credencial.usuario_id == usuario.pk:
        return
    policies.exigir(policies.pode_administrar(usuario),
                    "Só quem administra a automação mexe nesta credencial.")


@transaction.atomic
def revogar(usuario, pk: int) -> CredencialIntegracao:
    c = CredencialIntegracao.objects.select_for_update().get(pk=pk)
    _exigir_gestao(usuario, c)
    if not c.revogada_em:
        c.revogada_em, c.revogada_por = timezone.now(), usuario
        c.save(update_fields=["revogada_em", "revogada_por"])
    return c


@transaction.atomic
def emergencia(usuario, pk: int, ligar: bool = True) -> CredencialIntegracao:
    """Em emergência a credencial leva 401 em tudo, inclusive leitura."""
    c = CredencialIntegracao.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_administrar(usuario))
    c.emergencia = ligar
    c.save(update_fields=["emergencia"])
    return c


def autenticar(cabecalho: str | None) -> CredencialIntegracao | None:
    """`Authorization: Bearer pcpr_<amb>_…` → credencial vigente deste ambiente, ou None."""
    if not cabecalho or not cabecalho.startswith("Bearer "):
        return None
    token = cabecalho[7:].strip()
    if not token.startswith(f"pcpr_{codigo_do_ambiente()}_") or len(token) > 200:
        return None
    c = (CredencialIntegracao.objects.select_related("usuario")
         .filter(token_hash=_hash(token)).first())
    agora = timezone.now()
    if (c is None or c.revogada_em or c.emergencia or c.expira_em <= agora
            or c.ambiente != codigo_do_ambiente()):
        return None
    if c.tipo == T.PESSOAL and (c.usuario is None or not policies.pode_ver(c.usuario)):
        return None
    if c.ultimo_uso_em is None or agora - c.ultimo_uso_em > timedelta(minutes=5):
        CredencialIntegracao.objects.filter(pk=c.pk).update(ultimo_uso_em=agora)
    return c
