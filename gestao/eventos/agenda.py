"""Fonte da Agenda: as solicitações de evento com data (paridade com a fonte "solicitacao"
da agenda da referência), só as que a pessoa vê; cancelada e não atendida entram como
encerradas (escondidas por padrão)."""

from __future__ import annotations

from datetime import date

from django.db.models import Q
from django.urls import reverse

from gestao.plataforma.agenda import Compromisso, Fonte, registrar_fonte

from . import dominio, policies


def _solicitacoes(usuario, inicio: date, fim: date) -> list[Compromisso]:
    saida = []
    consulta = (policies.solicitacoes_visiveis(usuario)
                .filter(data_inicio_evento__isnull=False, data_inicio_evento__lte=fim)
                .filter(Q(data_fim_evento__gte=inicio)
                        | Q(data_fim_evento__isnull=True, data_inicio_evento__gte=inicio))
                .exclude(status=dominio.RASCUNHO)
                .select_related("municipio", "tipo_evento", "motorista", "criado_por")
                .order_by("data_inicio_evento", "pk"))
    for s in consulta:
        if s.data_inicio_evento is None:  # filtrado acima
            continue
        tipo = s.tipo_evento.nome if s.tipo_evento else "Evento"
        local = s.municipio.nome if s.municipio else ""
        saida.append(Compromisso(
            fonte="solicitacao", chave=f"solicitacao-{s.pk}",
            titulo=(f"{tipo} · {local}" if local else tipo)
            + f" — {s.solicitante_nome or 'sem solicitante'}",
            inicio=s.data_inicio_evento, fim=s.data_fim_evento,
            situacao=s.get_status_display(), tom=dominio.TONS.get(s.status, "neutro"),
            encerrado=s.status in (dominio.CANCELADA, dominio.NAO_ATENDIDA),
            url=reverse("eventos:solicitacao", args=[s.pk]),
            meu=s.criado_por_id == getattr(usuario, "pk", None),
            pessoas=(s.motorista.nome,) if s.motorista else (),
            detalhes=(("Solicitante", s.solicitante_nome), ("Local", s.local_evento),
                      ("Endereço", s.endereco), ("Servidores", str(s.quantidade_servidores)),
                      ("Responsável", s.criado_por.nome), ("Status", s.get_status_display()))))
    return saida


def registrar() -> None:
    registrar_fonte(Fonte("solicitacao", "Solicitações de evento", policies.pode_criar,
                          _solicitacoes, ordem=15))
