"""Fonte "solicitacoes" dos conflitos de agenda (`plataforma.conflitos`, paridade com a
fonte da referência): solicitações em andamento (enviadas, devolvidas, deferidas) com o
motorista ou a unidade móvel procurados na mesma data; e o pedido repetido (outra
solicitação para o mesmo município no mesmo período). Solicitação só tem data: ocupa o
dia inteiro."""

from __future__ import annotations

from typing import Any

from django.db.models import Q
from django.urls import reverse

from gestao.plataforma import conflitos as agenda_conflitos
from gestao.plataforma.conflitos import Conflito, Consulta, periodo_de_datas

from . import dominio
from .models import Solicitacao

ATIVAS = (dominio.AGUARDANDO, dominio.DEVOLVIDA, dominio.DEFERIDA, dominio.ATENDIDA)


def _base(s: Solicitacao) -> dict[str, Any]:
    inicio, fim = periodo_de_datas(s.data_inicio_evento, s.data_fim_evento)
    return {"no_documento": f"na Solicitação #{s.pk}", "documento": f"Solicitação #{s.pk}",
            "inicio": inicio, "fim": fim,
            "local": f"{s.municipio.nome}/{s.municipio.uf}" if s.municipio else "",
            "url": reverse("eventos:solicitacao", args=[s.pk]), "chave": ("solicitacao", s.pk),
            "dia_inteiro": True}


def _solicitacoes(c: Consulta) -> list[Conflito]:
    pedido = c.pedido == "solicitacao" and c.municipios
    if not (c.servidores or c.unidades_moveis or pedido):
        return []
    primeiro, ultimo = c.datas()
    por_recurso = (Q(motorista_id__in=c.servidores)
                   | Q(unidade_movel=True, unidade_movel_designada_id__in=c.unidades_moveis))
    if pedido:
        por_recurso |= Q(municipio_id__in=c.municipios)
    consulta = (Solicitacao.objects.filter(status__in=ATIVAS)
                .exclude(pk__in=c.excluidos("solicitacao"))
                .filter(data_inicio_evento__lte=ultimo)
                .filter(Q(data_fim_evento__gte=primeiro)
                        | Q(data_fim_evento__isnull=True, data_inicio_evento__gte=primeiro))
                .filter(por_recurso)
                .select_related("municipio", "motorista", "unidade_movel_designada"))
    achados = []
    for s in consulta:
        base = _base(s)
        if s.motorista_id in c.servidores and s.motorista is not None:
            achados.append(Conflito(tipo="servidor", recurso=s.motorista.nome,
                                    papel=" como motorista", **base))
        um = s.unidade_movel_designada
        if s.unidade_movel and um is not None and um.pk in c.unidades_moveis:
            achados.append(Conflito(tipo="unidade_movel", recurso=um.nome, **base))
        if pedido and s.municipio_id in c.municipios:
            achados.append(Conflito(tipo="pedido", recurso="", **base))
    return achados


def consulta_da_solicitacao(s: Solicitacao) -> Consulta | None:
    inicio, fim = periodo_de_datas(s.data_inicio_evento, s.data_fim_evento)
    return agenda_conflitos.consulta(
        inicio, fim, servidores=[s.motorista_id],
        unidades_moveis=[s.unidade_movel_designada_id] if s.unidade_movel else [],
        municipios=[s.municipio_id], pedido="solicitacao", excluir={"solicitacao": {s.pk}})


def avisos_da_solicitacao(s: Solicitacao) -> list[Conflito]:
    return agenda_conflitos.conflitos(consulta_da_solicitacao(s))


def registrar() -> None:
    agenda_conflitos.registrar_fonte("solicitacoes", _solicitacoes)
