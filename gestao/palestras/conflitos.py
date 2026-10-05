"""Fonte "palestras" dos conflitos de agenda (`plataforma.conflitos`): palestras não
canceladas na mesma data com o palestrante procurado; o servidor de uma viagem que também é
palestrante (palestrante ligado ao cadastro); e o pedido repetido (mesmo município e data).
Palestra só tem data: ocupa o dia inteiro.

O ampliador faz o palestrante ligado a um servidor ocupar a pessoa — é o que cruza a
palestra com o ofício.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from django.db.models import Prefetch, Q
from django.urls import reverse

from gestao.plataforma import conflitos as agenda_conflitos
from gestao.plataforma.conflitos import Conflito, Consulta, periodo_de_datas

from .models import Palestra, Palestrante


def _ampliar(c: Consulta) -> Consulta:
    if not c.palestrantes:
        return c
    vinculados = Palestrante.objects.filter(pk__in=c.palestrantes, servidor__isnull=False)
    extra = frozenset(int(x) for x in vinculados.values_list("servidor_id", flat=True))
    return replace(c, servidores=c.servidores | extra) if extra else c


def _rotulo(p: Palestra) -> str:
    return f"{p.get_evento_display()} #{p.pk}"


def _base(p: Palestra) -> dict[str, Any]:
    inicio, fim = periodo_de_datas(p.data_inicio_evento, p.data_fim_evento)
    return {"no_documento": f"na {_rotulo(p)}", "documento": _rotulo(p), "inicio": inicio,
            "fim": fim, "local": f"{p.municipio.nome}/{p.municipio.uf}" if p.municipio else "",
            "url": reverse("palestras:palestra", args=[p.pk]), "chave": ("palestra", p.pk),
            "dia_inteiro": True}


def _palestras(c: Consulta) -> list[Conflito]:
    primeiro, ultimo = c.datas()
    ativas = (Palestra.objects.exclude(status=Palestra.Status.CANCELADA)
              .exclude(pk__in=c.excluidos("palestra"))
              .filter(data_inicio_evento__lte=ultimo)
              .filter(Q(data_fim_evento__gte=primeiro)
                      | Q(data_fim_evento__isnull=True, data_inicio_evento__gte=primeiro))
              .select_related("municipio"))
    achados: list[Conflito] = []
    if c.palestrantes:
        procurados = Palestrante.objects.filter(pk__in=c.palestrantes)
        for p in ativas.filter(palestrantes__in=c.palestrantes).distinct().prefetch_related(
                Prefetch("palestrantes", queryset=procurados, to_attr="procurados")):
            for x in getattr(p, "procurados", []):
                achados.append(Conflito(tipo="palestrante", recurso=x.nome, **_base(p)))
    if c.servidores:
        # Uma consulta só quando não há nada (o caso comum, na folha do ofício): as palestras
        # com palestrante ligado a algum dos servidores; os nomes vêm só se houver.
        vinculados = (Palestrante.objects.filter(servidor_id__in=c.servidores)
                      .exclude(pk__in=c.palestrantes).select_related("servidor"))
        com_servidor = (ativas.filter(palestrantes__servidor_id__in=c.servidores)
                        .exclude(palestrantes__pk__in=c.palestrantes).distinct()
                        .prefetch_related(Prefetch("palestrantes", queryset=vinculados,
                                                   to_attr="vinculados")))
        for q in com_servidor:
            for x in getattr(q, "vinculados", []):
                if x.servidor is not None:
                    achados.append(Conflito(tipo="servidor", recurso=x.servidor.nome,
                                            papel=" como palestrante", **_base(q)))
    if c.pedido == "palestra" and c.municipios:
        for r in ativas.filter(municipio_id__in=c.municipios):
            achados.append(Conflito(tipo="pedido", recurso="", **_base(r)))
    return achados


def consulta_da_palestra(p: Palestra) -> Consulta | None:
    inicio, fim = periodo_de_datas(p.data_inicio_evento, p.data_fim_evento)
    return agenda_conflitos.consulta(
        inicio, fim, palestrantes=[x.pk for x in p.palestrantes.all()],
        municipios=[p.municipio_id], pedido="palestra", excluir={"palestra": {p.pk}})


def avisos_da_palestra(p: Palestra) -> list[agenda_conflitos.Conflito]:
    return agenda_conflitos.conflitos(consulta_da_palestra(p))


def registrar() -> None:
    agenda_conflitos.registrar_fonte("palestras", _palestras)
    agenda_conflitos.registrar_ampliador(_ampliar)
