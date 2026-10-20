"""Ferramentas tipadas de Viagens para a automação (ADR 0020), registradas no `ready`.

Só leitura e preparação: nada aqui escolhe equipe, motorista ou viatura, lança km, calcula
diária, emite, cancela, assina ou finaliza — essas ações não existem como ferramenta. A policy
é a do contexto, aplicada ao usuário efetivo (dono do token pessoal ou quem delegou).
"""

from __future__ import annotations

from django.db import transaction

from gestao.automacao import ferramentas
from gestao.automacao.ferramentas import Campo, Ferramenta, FerramentaRecusada

from . import policies
from .models import Oficio, PrestacaoServidor


def _ps(entrada: dict) -> PrestacaoServidor | None:
    return (PrestacaoServidor.objects.select_related("prestacao__oficio", "servidor")
            .filter(pk=entrada["ps"], removida_em__isnull=True).first())


def _unidade(entrada: dict) -> int | None:
    ps = _ps(entrada)
    return ps.prestacao.oficio.unidade_id if ps else None


def _pode_ver_ps(usuario, entrada: dict) -> bool:
    ps = _ps(entrada)
    return ps is not None and policies.pode_ver_prestacao(usuario, ps)


def _pode_editar_ps(usuario, entrada: dict) -> bool:
    ps = _ps(entrada)
    return ps is not None and policies.pode_editar_prestacao(usuario, ps)


def _situacao(usuario, entrada: dict) -> dict:
    from . import prestacao

    ps = _ps(entrada)
    if ps is None:
        raise FerramentaRecusada("Prestação inexistente.")
    oficio = ps.prestacao.oficio
    return {"oficio": oficio.numero_formatado, "liberacao": ps.data_liberacao_diarias and
            ps.data_liberacao_diarias.isoformat(),
            "prazo_saque": ps.prazo_limite_saque and ps.prazo_limite_saque.isoformat(),
            "finalizada": ps.finalizada, "pendencias": prestacao.pendencias(ps),
            "fonte": f"viagens.prestacaoservidor:{ps.pk}"}


def _oficio(entrada: dict) -> Oficio | None:
    return Oficio.objects.filter(pk=entrada["oficio"]).first()


def _pode_ver_oficio(usuario, entrada: dict) -> bool:
    oficio = _oficio(entrada)
    return oficio is not None and policies.pode_ver(usuario, oficio)


def _resumo(usuario, entrada: dict) -> dict:
    oficio = _oficio(entrada)
    if oficio is None:
        raise FerramentaRecusada("Ofício inexistente.")
    trechos = list(oficio.trechos.select_related("destino").order_by("ordem"))
    return {"oficio": oficio.numero_formatado, "situacao": oficio.get_situacao_display(),
            "destinos": sorted({str(t.destino) for t in trechos if t.destino_id}),
            "saida": trechos[0].saida_em.isoformat() if trechos and trechos[0].saida_em else None,
            "equipe": oficio.viajantes.count(), "fonte": f"viagens.oficio:{oficio.pk}"}


@transaction.atomic
def _lembrar(usuario, entrada: dict) -> dict:
    """Agenda já o lembrete de comprovante pelo WhatsApp (revalidado na saída)."""
    from django.utils import timezone

    from gestao.automacao import comunicacoes as automacao

    from . import comunicacoes

    ps = _ps(entrada)
    if ps is None:
        raise FerramentaRecusada("Prestação inexistente.")
    if not ps.data_liberacao_diarias or ps.finalizada:
        raise FerramentaRecusada("Só para prestação com diárias liberadas e em aberto.")
    c = automacao.agendar(
        tipo=comunicacoes.LEMBRETE, servidor_id=ps.servidor_id,
        recurso=f"{comunicacoes.RECURSO}:{ps.pk}",
        chave=f"{comunicacoes.LEMBRETE}:{ps.pk}:{comunicacoes.versao(ps)}:manual:"
              f"{timezone.localdate()}",
        unidade_id=ps.prestacao.oficio.unidade_id, criada_por=usuario, contexto={"ps": ps.pk},
        versao=comunicacoes.versao(ps))
    if c is None:
        raise FerramentaRecusada("As automações estão desligadas.")
    return {"comunicacao": c.pk, "situacao": c.situacao}


def registrar() -> None:
    ferramentas.registrar(Ferramenta(
        nome="prestacao.situacao", risco=ferramentas.LEITURA,
        descricao="Situação da prestação de um servidor: datas, pendências e se está finalizada.",
        entrada={"ps": Campo("inteiro")}, executar=_situacao, permitido=_pode_ver_ps,
        recurso=lambda e: f"viagens.prestacaoservidor:{e['ps']}",
        saida={"pendencias": "lista de textos", "finalizada": "booleano"}))
    ferramentas.registrar(Ferramenta(
        nome="viagens.resumo", risco=ferramentas.LEITURA,
        descricao="Resumo de um ofício: número, situação, destinos, saída e tamanho da equipe.",
        entrada={"oficio": Campo("inteiro")}, executar=_resumo, permitido=_pode_ver_oficio,
        recurso=lambda e: f"viagens.oficio:{e['oficio']}"))
    ferramentas.registrar(Ferramenta(
        nome="prestacao.lembrar_comprovante", risco=ferramentas.PREPARACAO,
        descricao="Agenda agora o lembrete de comprovante pelo WhatsApp (revalidado na saída).",
        entrada={"ps": Campo("inteiro")}, executar=_lembrar, permitido=_pode_editar_ps,
        recurso=lambda e: f"viagens.prestacaoservidor:{e['ps']}",
        unidade=_unidade,
        resumo=lambda e: f"Lembrar o comprovante da prestação #{e['ps']} pelo WhatsApp"))
