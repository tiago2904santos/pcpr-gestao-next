"""Pagamento conjunto (CB3b; paridade com `coffee_break/services.py` §4.2 da especificação):
várias OS do mesmo lote num só ofício e num só protocolo. Uma é a principal; as outras
apontam para ela. Os campos do pagamento são espelhados em todas (os posteriores à nota só
nas que já têm nota), cada cópia com o seu histórico; protocolo e atesto só entram quando
todas as OS do grupo têm a nota. Cancelar ou excluir a principal passa o papel à próxima."""

from __future__ import annotations

from datetime import date

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q

from . import policies
from .models import Movimento, Solicitacao
from .pedidos import PedidoInvalido

MSG_CANDIDATAS = ("Só entram OS do mesmo lote, sem protocolo de pagamento e fora de outro "
                  "pagamento conjunto.")
# Espelhados em todas as OS do pagamento; os da 2ª tupla só nas que já têm nota.
DO_OFICIO = ("numero_oficio", "data_oficio", "protocolo_pcpr")
DEPOIS_DA_NOTA = ("protocolo_pagamento", "atesto_em", "ordem_bancaria_em", "envio_empresa_em")
ROTULOS = {"numero_oficio": "nº do ofício", "data_oficio": "data do ofício",
           "protocolo_pcpr": "PCPR protocolo n.º", "protocolo_pagamento": "protocolo de pagamento",
           "atesto_em": "atesto e envio ao GAF", "ordem_bancaria_em": "ordem bancária",
           "envio_empresa_em": "envio à empresa"}


def principal_de(s: Solicitacao) -> Solicitacao:
    return s.pagamento_com if s.pagamento_com is not None else s


def membros(s: Solicitacao) -> list[Solicitacao]:
    """A principal e as que apontam para ela (não canceladas), pela ordem do número."""
    p = principal_de(s)
    grupo = [p, *Solicitacao.objects.filter(pagamento_com=p, cancelada=False)]
    return sorted(grupo, key=lambda x: (x.numero or "", x.pk))


def em_grupo(s: Solicitacao) -> bool:
    return bool(s.pagamento_com_id) or s.conjuntas.filter(cancelada=False).exists()


def candidatas(s: Solicitacao):
    """As OS que podem entrar no pagamento desta: mesmo lote, não canceladas, não concluídas,
    sem protocolo de pagamento e fora de outro grupo."""
    p = principal_de(s)
    return (Solicitacao.objects.filter(lote_id=s.lote_id, cancelada=False,
                                       envio_empresa_em__isnull=True, protocolo_pagamento="")
            .filter(Q(pagamento_com__isnull=True) | Q(pagamento_com=p))
            .exclude(pk=p.pk).exclude(conjuntas__cancelada=False)  # principal de outro grupo
            .order_by("numero", "pk").distinct())


def _mover(s: Solicitacao, usuario, texto: str) -> None:
    Movimento.objects.create(solicitacao=s, acao=Movimento.Acao.CONJUNTO, texto=texto,
                             usuario=usuario)


def _fmt(valor) -> str:
    return f"{valor:%d/%m/%Y}" if isinstance(valor, date) else str(valor or "—")


@transaction.atomic
def definir(usuario, pk: int, ids: list[int]) -> list[Solicitacao]:
    """Monta o pagamento com esta OS (a principal) e as escolhidas; desmarcar tira."""
    if not policies.pode_acessar(usuario):
        raise PermissionDenied
    s = Solicitacao.objects.select_for_update().get(pk=pk)
    p = principal_de(s)
    if p.bloqueada or p.protocolo_pagamento:
        raise PedidoInvalido(MSG_CANDIDATAS)
    validas = {c.pk for c in candidatas(p)}
    atuais = {x.pk for x in Solicitacao.objects.filter(pagamento_com=p, cancelada=False)}
    pedidas = {i for i in ids if i != p.pk}
    if pedidas - validas - atuais:
        raise PedidoInvalido(MSG_CANDIDATAS)
    for sai in Solicitacao.objects.select_for_update().filter(pk__in=atuais - pedidas):
        sai.pagamento_com = None
        sai.save(update_fields=["pagamento_com", "atualizado_em"])
        _mover(sai, usuario, f"Saiu do pagamento conjunto com a {p}.")
        _mover(p, usuario, f"A {sai} saiu do pagamento conjunto.")
    for entra in Solicitacao.objects.select_for_update().filter(pk__in=pedidas - atuais):
        entra.pagamento_com = p
        for campo in DO_OFICIO:
            setattr(entra, campo, getattr(p, campo))
        entra.save()
        _mover(entra, usuario, f"Entrou no pagamento conjunto com a {p}: um só ofício e um só "
                               "protocolo.")
        _mover(p, usuario, f"A {entra} entrou no pagamento conjunto.")
    return membros(p)


def conferir_notas(s: Solicitacao, campo: str) -> None:
    """Protocolo de pagamento e atesto só quando todas as OS do grupo têm a nota."""
    if campo not in ("protocolo_pagamento", "atesto_em") or not em_grupo(s):
        return
    sem = [str(x) for x in membros(s) if x.pk != s.pk and not x.nota_fiscal]
    if sem:
        raise PedidoInvalido(f"No pagamento conjunto, o {ROTULOS[campo]} só entra quando todas "
                             f"as OS têm a nota fiscal: falta a nota da {', '.join(sem)}.",
                             campo)


def espelhar(s: Solicitacao, usuario, campos: list[str]) -> None:
    """Copia os campos do pagamento desta OS para as outras do grupo, com histórico."""
    if not em_grupo(s):
        return
    for outra in membros(s):
        if outra.pk == s.pk:
            continue
        mudou = []
        for campo in campos:
            if campo not in DO_OFICIO + DEPOIS_DA_NOTA:
                continue
            if campo in DEPOIS_DA_NOTA and not outra.nota_fiscal:
                continue
            valor = getattr(s, campo)
            if getattr(outra, campo) != valor:
                setattr(outra, campo, valor)
                mudou.append(campo)
        if mudou:
            Solicitacao.objects.filter(pk=outra.pk).update(
                **{c: getattr(outra, c) for c in mudou})
            for campo in mudou:
                _mover(outra, usuario, f"Copiado da {s} (pagamento conjunto) — "
                                       f"{ROTULOS[campo]}: {_fmt(getattr(s, campo))}.")


def ao_sair(s: Solicitacao, usuario, como: str) -> None:
    """A OS foi cancelada ou vai ser excluída: sai do grupo; sendo a principal, a próxima
    pelo número assume."""
    if s.pagamento_com_id:
        p = s.pagamento_com
        Solicitacao.objects.filter(pk=s.pk).update(pagamento_com=None)
        if p is not None:
            _mover(p, usuario, f"A {s} foi {como} e saiu do pagamento conjunto.")
        return
    ficam = list(Solicitacao.objects.filter(pagamento_com=s, cancelada=False)
                 .order_by("numero", "pk"))
    if not ficam:
        return
    nova = ficam[0]
    Solicitacao.objects.filter(pk=nova.pk).update(pagamento_com=None)
    Solicitacao.objects.filter(pk__in=[x.pk for x in ficam[1:]]).update(pagamento_com=nova)
    for x in ficam:
        _mover(x, usuario, f"A {s} foi {como} e saiu do pagamento conjunto.")
