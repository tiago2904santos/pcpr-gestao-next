"""Delegação emitida pelo PCPR no momento da ação humana (nunca um cabeçalho livre em que o
chamador escolhe quem representa — o *confused deputy* do rascunho 2 do contrato).

A pessoa age numa tela (ex.: "Pedir rascunho do RT") e o PCPR emite uma delegação: usuário,
ferramentas, recurso, validade ≤ 15 min, uso único, para UMA credencial. A automação manda o
id opaco em `X-PCPR-Delegacao`; a API confere tudo e consome.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .. import policies
from ..models_api import CredencialIntegracao, Delegacao

VALIDADE_MAXIMA = timedelta(minutes=15)


class DelegacaoNegada(Exception):
    pass


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _administrativo(usuario) -> bool:
    """Delegar quem administra ou vê todas as unidades para um token de serviço: não."""
    return bool(usuario.is_superuser or policies.pode_administrar(usuario)
                or policies.ve_todas_unidades(usuario))


@transaction.atomic
def emitir(usuario, credencial: CredencialIntegracao, *, ferramentas: list[str], recurso: str,
           motivo: str, minutos: int = 10) -> tuple[Delegacao, str]:
    if credencial.tipo == CredencialIntegracao.Tipo.PESSOAL:
        raise DelegacaoNegada("Token pessoal não usa delegação: ele já age como o dono.")
    if credencial.revogada_em or credencial.expira_em <= timezone.now():
        raise DelegacaoNegada("Credencial vencida ou revogada.")
    if not recurso:
        raise DelegacaoNegada("A delegação é sempre para um recurso definido.")
    if _administrativo(usuario):
        raise DelegacaoNegada("Delegação de perfil administrativo para automação é recusada.")
    fora = [f for f in ferramentas if f not in (credencial.ferramentas or [])]
    if fora:
        raise DelegacaoNegada(f"A credencial não pode usar: {', '.join(fora)}.")
    token = "dlg_" + secrets.token_urlsafe(24)
    validade = min(timedelta(minutes=max(1, minutos)), VALIDADE_MAXIMA)
    d = Delegacao.objects.create(token_hash=_hash(token), usuario=usuario, credencial=credencial,
                                 ferramentas=list(ferramentas), recurso=recurso[:80],
                                 motivo=motivo[:200], expira_em=timezone.now() + validade)
    return d, token


def consumir(token: str | None, credencial: CredencialIntegracao, ferramenta: str,
             recurso: str) -> Delegacao:
    """Dentro da transação da execução: confere e marca como usada (uso único)."""
    if not token or not token.startswith("dlg_") or len(token) > 80:
        raise DelegacaoNegada("Delegação ausente: esta credencial só age com delegação.")
    d = (Delegacao.objects.select_for_update(of=("self",)).select_related("usuario")
         .filter(token_hash=_hash(token)).first())
    if d is None or d.credencial_id != credencial.pk:
        raise DelegacaoNegada("Delegação desconhecida ou emitida para outra credencial.")
    if d.usada_em is not None:
        raise DelegacaoNegada("Delegação já usada.")
    if d.expira_em <= timezone.now():
        raise DelegacaoNegada("Delegação vencida.")
    if ferramenta not in d.ferramentas:
        raise DelegacaoNegada("Ferramenta fora da delegação.")
    if d.recurso and recurso != d.recurso:
        raise DelegacaoNegada("A delegação é de outro recurso.")
    if not d.usuario.is_active or _administrativo(d.usuario):
        raise DelegacaoNegada("O usuário da delegação não pode ser representado.")
    d.usada_em = timezone.now()
    d.save(update_fields=["usada_em"])
    return d
