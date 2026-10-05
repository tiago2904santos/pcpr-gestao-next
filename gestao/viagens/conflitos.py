"""Fonte "oficios" dos conflitos de agenda (`plataforma.conflitos`): ofícios não
cancelados, de qualquer unidade, com a equipe, o motorista (da equipe ou de fora, do
cadastro) ou a viatura procurados, no período dos trechos (saída da sede à chegada).

E os atalhos da tela do ofício: os conflitos do ofício como texto (aviso, não bloqueio).
"""

from __future__ import annotations

from django.db.models import Max, Min, Prefetch, Q
from django.urls import reverse

from gestao.plataforma import conflitos as agenda_conflitos
from gestao.plataforma.conflitos import Conflito, Consulta

from .models import Oficio, Trecho, Viajante
from .queries import trechos_de, viajantes_de


def _oficios(c: Consulta) -> list[Conflito]:
    if not (c.servidores or c.viaturas):
        return []
    por_recurso = Q(viatura_id__in=c.viaturas) | Q(motorista_externo_servidor_id__in=c.servidores)
    if c.servidores:
        por_recurso |= Q(pk__in=Viajante.objects.filter(servidor_id__in=c.servidores)
                         .values("oficio_id"))
    oficios = (Oficio.objects.exclude(situacao=Oficio.Situacao.CANCELADO)
               .exclude(pk__in=c.excluidos("oficio")).filter(por_recurso)
               .annotate(_ini=Min("trechos__saida_em"), _fim=Max("trechos__chegada_em"))
               .filter(_ini__lt=c.fim, _fim__gt=c.inicio)
               .select_related("viatura", "motorista_externo_servidor")
               .prefetch_related(
                   Prefetch("viajantes", queryset=Viajante.objects.select_related("servidor")),
                   Prefetch("trechos", queryset=Trecho.objects.select_related("destino"))))
    achados = []
    for o in oficios:
        documento = f"Ofício {o.numero_formatado}"
        destinos = list(dict.fromkeys(t.destino.nome for t in o.trechos.all() if t.destino_id))
        base = {"no_documento": f"no {documento}", "documento": documento, "inicio": o._ini,
                "fim": max(o._ini, o._fim), "local": ", ".join(destinos[:3]),
                "url": (reverse("viagens:editar", args=[o.pk]) if o.editavel
                        else f"{reverse('viagens:oficios')}?q={o.numero_formatado}"),
                "chave": ("oficio", o.pk)}
        for v in o.viajantes.all():
            if v.servidor_id in c.servidores:
                achados.append(Conflito(tipo="servidor", recurso=v.servidor.nome,
                                        papel=" como motorista" if v.motorista else "", **base))
        externo = o.motorista_externo_servidor
        if externo is not None and externo.pk in c.servidores:
            achados.append(Conflito(tipo="servidor", recurso=externo.nome,
                                    papel=" como motorista", **base))
        if o.viatura_id in c.viaturas and o.viatura is not None:
            achados.append(Conflito(tipo="viatura",
                                    recurso=f"Viatura {o.viatura.placa_formatada}", **base))
    return achados


def consulta_do_oficio(oficio: Oficio) -> Consulta | None:
    trechos = trechos_de(oficio)
    if not trechos:
        return None
    servidores: list[int | None] = [v.servidor_id for v in viajantes_de(oficio)]
    servidores.append(oficio.motorista_externo_servidor_id)
    return agenda_conflitos.consulta(trechos[0].saida_em, trechos[-1].chegada_em,
                                     servidores=servidores, viaturas=[oficio.viatura_id],
                                     excluir={"oficio": {oficio.pk}})


def avisos_do_oficio(oficio: Oficio) -> list[str]:
    """Os conflitos do ofício como frases (equipe, motorista, viatura; ofícios e palestras)."""
    return [c.mensagem for c in agenda_conflitos.conflitos(consulta_do_oficio(oficio))]


def registrar() -> None:
    agenda_conflitos.registrar_fonte("oficios", _oficios)
