"""Fontes "oficios", "termos" e "ordens" dos conflitos de agenda (`plataforma.conflitos`):
ofícios não cancelados, de qualquer unidade, com a equipe, o motorista (da equipe ou de
fora, do cadastro) ou a viatura procurados, no período dos trechos (saída da sede à
chegada); termos de autorização e ordens de serviço com datas próprias, com o que
acrescentam aos ofícios vinculados (A2c).

E os atalhos da tela do ofício: os conflitos do ofício como texto (aviso, não bloqueio).
"""

from __future__ import annotations

from typing import Any

from django.db.models import Max, Min, Prefetch, Q, Value
from django.urls import reverse

from gestao.plataforma import conflitos as agenda_conflitos
from gestao.plataforma.conflitos import Conflito, Consulta, periodo_de_datas

from .models import Oficio, OrdemServico, TermoAutorizacao, Trecho, Viajante
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


def _sem_os_do_oficio(ids_oficios: list[int]) -> tuple[set[int], set[int]]:
    """Servidores (equipe e motorista de fora) e viaturas dos ofícios vinculados — o termo e
    a OS só acrescentam o que não está no ofício (senão o mesmo deslocamento acusaria duas
    vezes)."""
    if not ids_oficios:
        return set(), set()
    servidores = set(Viajante.objects.filter(oficio_id__in=ids_oficios)
                     .values_list("servidor_id", flat=True))
    externos = Oficio.objects.filter(pk__in=ids_oficios).values_list(
        "motorista_externo_servidor_id", "viatura_id")
    viaturas = set()
    for motorista, viatura in externos:
        if motorista:
            servidores.add(motorista)
        if viatura:
            viaturas.add(viatura)
    return servidores, viaturas


def _por_datas(qs, c: Consulta):
    primeiro, ultimo = c.datas()
    return (qs.filter(data_inicio__isnull=False, data_inicio__lte=ultimo)
            .filter(Q(data_fim__gte=primeiro) | Q(data_fim__isnull=True,
                                                    data_inicio__gte=primeiro)))


def _termos_no_periodo(c: Consulta):
    return (_por_datas(TermoAutorizacao.objects.exclude(
        situacao=TermoAutorizacao.Situacao.CANCELADO).exclude(pk__in=c.excluidos("termo")), c)
        .filter(Q(servidores__in=c.servidores) | Q(viatura_id__in=c.viaturas)))


def _ordens_no_periodo(c: Consulta):
    return (_por_datas(OrdemServico.objects.exclude(
        situacao=OrdemServico.Situacao.CANCELADA).exclude(pk__in=c.excluidos("ordem")), c)
        .filter(servidores__in=c.servidores))


def _termos_e_ordens(c: Consulta) -> list[Conflito]:
    """Termos e OS com datas próprias. Uma consulta só (UNION) acha os candidatos — no caso
    comum, sem nenhum, é tudo; os detalhes só vêm quando há o que mostrar."""
    if not (c.servidores or c.viaturas):
        return []
    termos = _termos_no_periodo(c).annotate(qual=Value("t")).values_list("pk", "qual").order_by()
    ordens = _ordens_no_periodo(c).annotate(qual=Value("o")).values_list("pk", "qual").order_by()
    candidatos = list(termos.union(ordens).order_by())
    ids_t = {pk for pk, qual in candidatos if qual == "t"}
    ids_o = {pk for pk, qual in candidatos if qual == "o"}
    return (_termos(c, ids_t) if ids_t else []) + (_ordens(c, ids_o) if ids_o else [])


def _termos(c: Consulta, ids: set[int]) -> list[Conflito]:
    """Termos de autorização com datas próprias: os servidores e a viatura deles."""
    termos = (TermoAutorizacao.objects.filter(pk__in=ids)
              .select_related("viatura").prefetch_related("servidores"))
    achados = []
    for t in termos:
        inicio, fim = periodo_de_datas(t.data_inicio, t.data_fim)
        if inicio is None or fim is None:
            continue
        no_oficio, viaturas_do_oficio = _sem_os_do_oficio([t.oficio_id] if t.oficio_id else [])
        documento = f"Termo de autorização #{t.pk}"
        base: dict[str, Any] = {
                "no_documento": f"no {documento}", "documento": documento, "inicio": inicio,
                "fim": fim, "dia_inteiro": True,
                "url": reverse("viagens:editar_termo", args=[t.pk]), "chave": ("termo", t.pk)}
        for s in t.servidores.all():
            if s.pk in c.servidores and s.pk not in no_oficio:
                achados.append(Conflito(tipo="servidor", recurso=s.nome, **base))
        if (t.viatura_id in c.viaturas and t.viatura is not None
                and t.viatura_id not in viaturas_do_oficio):
            achados.append(Conflito(tipo="viatura", recurso=f"Viatura {t.viatura.placa_formatada}",
                                    **base))
    return achados


def _ordens(c: Consulta, ids: set[int]) -> list[Conflito]:
    """Ordens de serviço com datas próprias: a equipe, fora quem já está nos ofícios dela."""
    ordens = OrdemServico.objects.filter(pk__in=ids).prefetch_related("servidores", "oficios")
    achados = []
    for o in ordens:
        inicio, fim = periodo_de_datas(o.data_inicio, o.data_fim)
        if inicio is None or fim is None:
            continue
        no_oficio, _ = _sem_os_do_oficio([x.pk for x in o.oficios.all()])
        documento = f"OS {o.numero_formatado}"
        base: dict[str, Any] = {
                "no_documento": f"na {documento}", "documento": documento, "inicio": inicio,
                "fim": fim, "dia_inteiro": True,
                "url": reverse("viagens:editar_ordem", args=[o.pk]), "chave": ("ordem", o.pk)}
        for s in o.servidores.all():
            if s.pk in c.servidores and s.pk not in no_oficio:
                achados.append(Conflito(tipo="servidor", recurso=s.nome, **base))
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
    agenda_conflitos.registrar_fonte("termos_e_ordens", _termos_e_ordens)
