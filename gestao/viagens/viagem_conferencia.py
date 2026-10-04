"""Conferência da viagem (módulo 8b, paridade com `prontidao.py` e `coerencia.py` da
referência): o que falta para a viagem ficar pronta e os documentos que não batem com ela.

Prontidão: etapas na ordem da referência (dados, roteiro, ofícios, equipe, ordem, plano,
termos, assinaturas, protocolo), cada item com o link para onde se resolve. A "meta da DG"
(equipe designada) chega com o módulo de Solicitações.

Coerência: a viagem é a referência — período e destinos dela, equipe dos ofícios. "Aplicar
em todos" leva os dados aos documentos ainda sem via assinada (o assinado não se mexe).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from . import assinados, ordens, planos, policies, services, termos
from .models import (
    OrdemServico,
    OrdemServicoDestino,
    PlanoDestino,
    PlanoTrabalho,
    TermoAutorizacao,
    TermoDestino,
    Viagem,
)
from .viagem import documentos


@dataclass
class Item:
    mensagem: str
    link: str = ""


@dataclass
class Etapa:
    chave: str
    titulo: str
    itens: list[Item] = field(default_factory=list)

    @property
    def pronta(self) -> bool:
        return not self.itens


@dataclass
class Quadro:
    etapas: list[Etapa]

    @property
    def pendencias(self) -> int:
        return sum(len(e.itens) for e in self.etapas)

    @property
    def pronta(self) -> bool:
        return self.pendencias == 0

    @property
    def resolvidas(self) -> int:
        return sum(1 for e in self.etapas if e.pronta)


def _mais(primeira: str, resto: int) -> str:
    return f"{primeira} (e mais {resto})" if resto else primeira


def quadro(viagem: Viagem) -> Quadro:
    docs = documentos(viagem)
    folha = reverse("viagens:editar_viagem", args=[viagem.pk])
    etapas = {c: Etapa(c, t) for c, t in (
        ("dados", "Dados da viagem"), ("roteiro", "Roteiro"), ("oficios", "Ofícios"),
        ("equipe", "Equipe"), ("ordem", "Ordem de serviço"), ("plano", "Plano de trabalho"),
        ("termos", "Termos"), ("assinaturas", "Assinaturas"), ("protocolo", "Protocolo"))}

    # Dados
    if not viagem.tipos.exists():
        etapas["dados"].itens.append(Item("Informe o tipo da viagem.", f"{folha}#dados"))
    if not viagem.data_inicio:
        etapas["dados"].itens.append(Item("Informe o período da viagem.", f"{folha}#periodo"))
    if not viagem.destinos.exists():
        etapas["dados"].itens.append(Item("Informe o destino da viagem.", f"{folha}#periodo"))

    # Roteiro
    if not docs.roteiros:
        etapas["roteiro"].itens.append(Item(
            "Crie o roteiro da viagem (sede, saída, destinos e retorno).", f"{folha}#documentos"))
    for r in docs.roteiros:
        link = reverse("viagens:editar_roteiro", args=[r.pk])
        trechos = list(r.trechos.all())
        if not trechos:
            etapas["roteiro"].itens.append(Item(f"Roteiro #{r.pk}: informe os destinos.", link))
        elif not r.diarias_total:
            etapas["roteiro"].itens.append(Item(
                f"Roteiro #{r.pk}: as diárias ainda não foram calculadas.", link))

    # Ofícios
    if not docs.oficios:
        etapas["oficios"].itens.append(Item(
            "Nenhum ofício ainda: monte os ofícios com a equipe de cada um.",
            f"{folha}#documentos"))
    for o in docs.oficios:
        if o.situacao == o.Situacao.CANCELADO:
            continue
        link = reverse("viagens:editar", args=[o.pk])
        if o.situacao == o.Situacao.RASCUNHO:
            bloqueantes = services.verificar_prontidao(o).bloqueantes
            if bloqueantes:
                etapas["oficios"].itens.append(Item(_mais(
                    f"{o}: {bloqueantes[0].mensagem}", len(bloqueantes) - 1), link))
            else:
                etapas["oficios"].itens.append(Item(f"{o} em rascunho: revise e emita.", link))

    # Equipe: cadastros incompletos de quem viaja e da viatura.
    vistos: set[int] = set()
    for o in docs.oficios:
        for viajante in o.viajantes.select_related("servidor"):
            s = viajante.servidor
            if s is None or s.pk in vistos:
                continue
            vistos.add(s.pk)
            if s.faltando:
                etapas["equipe"].itens.append(Item(
                    f"Cadastro de {s.nome} sem {s.faltando_texto}.",
                    reverse("cadastros:servidores") + f"?editar={s.pk}"))
        viatura = o.viatura
        if viatura is not None and not viatura.completo:
            etapas["equipe"].itens.append(Item(
                f"Cadastro da viatura {viatura} incompleto ({viatura.faltando_texto}).",
                reverse("cadastros:viaturas") + f"?editar={viatura.pk}"))

    # Ordem de serviço
    ativas = [o for o in docs.ordens if not o.cancelada]
    if not ativas:
        etapas["ordem"].itens.append(Item("Crie a ordem de serviço.", f"{folha}#documentos"))
    for os_ in ativas:
        falta = ordens.faltando(os_)
        if falta:
            etapas["ordem"].itens.append(Item(f"{os_}: falta {', '.join(falta)}.",
                                              reverse("viagens:editar_ordem", args=[os_.pk])))

    # Plano de trabalho
    ativos = [p for p in docs.planos if not p.cancelado]
    if not ativos:
        etapas["plano"].itens.append(Item("Crie o plano de trabalho.", f"{folha}#documentos"))
    for p in ativos:
        pend = planos.pendencias(p)
        if pend:
            etapas["plano"].itens.append(Item(_mais(f"{p}: {pend[0].mensagem}", len(pend) - 1),
                                              reverse("viagens:editar_plano", args=[p.pk])))

    # Termos: cada servidor dos ofícios (fora da unidade emissora) com termo.
    if not docs.oficios:
        etapas["termos"].itens.append(Item(
            "Os termos saem com os ofícios: monte os ofícios primeiro.", f"{folha}#documentos"))
    cobertos: dict[int, set[int]] = {}
    for t in docs.termos:
        if t.cancelado:
            continue
        ef = termos.efetivo(t)
        cobertos.setdefault(t.oficio_id or 0, set()).update(s.pk for s in ef.servidores)
    for o in docs.oficios:
        if o.situacao == o.Situacao.CANCELADO:
            continue
        faltam = [v.servidor.nome for v in o.viajantes.select_related("servidor")
                  if v.servidor and v.servidor.unidade_id != o.unidade_id
                  and v.servidor.pk not in cobertos.get(o.pk, set())
                  and v.servidor.pk not in cobertos.get(0, set())]
        if faltam:
            etapas["termos"].itens.append(Item(f"{o}: sem termo para {', '.join(faltam)}.",
                                               f"{folha}#documentos"))

    # Assinaturas: o que já saiu e ainda não voltou assinado.
    for o in docs.oficios:
        if o.situacao == o.Situacao.EMITIDO and not assinados.vigentes_do(o).get(("oficio", "")):
            etapas["assinaturas"].itens.append(Item(
                f"{o}: falta anexar a versão assinada.",
                f"{reverse('viagens:oficios')}?resumo={o.pk}"))
    for os_ in ativas:
        if os_.documento_gerado_em and not assinados.vigentes_do(os_).get(("ordem", "")):
            etapas["assinaturas"].itens.append(Item(
                f"{os_}: falta anexar a versão assinada.",
                reverse("viagens:editar_ordem", args=[os_.pk]) + "#via-assinada"))

    # Protocolo
    if not docs.oficios:
        etapas["protocolo"].itens.append(Item(
            "O protocolo é aberto para cada ofício: monte os ofícios primeiro.",
            f"{folha}#documentos"))
    for o in docs.oficios:
        if o.situacao != o.Situacao.CANCELADO and not (o.protocolo or "").strip():
            etapas["protocolo"].itens.append(Item(f"{o}: sem protocolo.",
                                                  reverse("viagens:editar", args=[o.pk])))
    return Quadro(list(etapas.values()))


# ---------------------------------------------------------------- coerência
@dataclass
class Diferenca:
    chave: str  # "ordem-12:periodo"
    documento: str
    campo: str
    atual: str
    esperado: str
    aplicavel: bool = True
    link: str = ""


def _periodo(inicio: date | None, fim: date | None) -> str:
    if not inicio:
        return "sem período"
    fim = fim or inicio
    return (f"{inicio:%d/%m/%Y}" if fim == inicio else f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}")


def _cidades(municipios) -> str:
    nomes = [str(m) for m in municipios]
    return ", ".join(nomes) if nomes else "sem destino"


def _equipe_dos_oficios(docs) -> list:
    pessoas: dict[int, object] = {}
    for o in docs.oficios:
        if o.situacao == o.Situacao.CANCELADO:
            continue
        for v in o.viajantes.select_related("servidor"):
            if v.servidor_id:
                pessoas.setdefault(v.servidor_id, v.servidor)
    return list(pessoas.values())


def coerencia(viagem: Viagem) -> list[Diferenca]:
    docs = documentos(viagem)
    inicio, fim = viagem.data_inicio, viagem.data_fim or viagem.data_inicio
    destinos = [d.municipio for d in viagem.destinos.select_related("municipio")]
    equipe = _equipe_dos_oficios(docs)
    saida: list[Diferenca] = []
    esperado_periodo, esperado_destinos = _periodo(inicio, fim), set(destinos)
    for o in docs.ordens:
        if o.cancelada:
            continue
        link = reverse("viagens:editar_ordem", args=[o.pk])
        if inicio and (o.data_inicio, o.data_fim or o.data_inicio) != (inicio, fim):
            saida.append(Diferenca(f"ordem-{o.pk}:periodo", str(o), "período",
                                   _periodo(o.data_inicio, o.data_fim), esperado_periodo,
                                   link=link))
        atuais = [d.municipio for d in o.destinos.select_related("municipio")]
        if destinos and set(atuais) != esperado_destinos:
            saida.append(Diferenca(f"ordem-{o.pk}:destinos", str(o), "destinos",
                                   _cidades(atuais), _cidades(destinos), link=link))
        servidores = list(o.servidores.all())
        if equipe and {s.pk for s in servidores} != {s.pk for s in equipe}:
            saida.append(Diferenca(f"ordem-{o.pk}:equipe", str(o), "equipe",
                                   ", ".join(s.nome for s in servidores) or "sem equipe",
                                   ", ".join(s.nome for s in equipe), link=link))
    for p in docs.planos:
        if p.cancelado or p.eventos.exists():  # plano de vários eventos: fica de fora
            continue
        link = reverse("viagens:editar_plano", args=[p.pk])
        if inicio and (p.data_inicio, p.data_fim or p.data_inicio) != (inicio, fim):
            saida.append(Diferenca(f"plano-{p.pk}:periodo", str(p), "período",
                                   _periodo(p.data_inicio, p.data_fim), esperado_periodo,
                                   link=link))
        atuais = [d.municipio for d in p.destinos.select_related("municipio")]
        if destinos and set(atuais) != esperado_destinos:
            saida.append(Diferenca(f"plano-{p.pk}:destinos", str(p), "destinos",
                                   _cidades(atuais), _cidades(destinos), link=link))
    for t in docs.termos:
        if t.cancelado:
            continue
        link = reverse("viagens:editar_termo", args=[t.pk])
        if inicio and t.data_inicio and (t.data_inicio, t.data_fim or t.data_inicio) != (
                inicio, fim):
            saida.append(Diferenca(f"termo-{t.pk}:periodo", str(t), "período",
                                   _periodo(t.data_inicio, t.data_fim), esperado_periodo,
                                   link=link))
        atuais = [d.municipio for d in t.destinos.select_related("municipio")]
        if destinos and atuais and set(atuais) != esperado_destinos:
            saida.append(Diferenca(f"termo-{t.pk}:destinos", str(t), "destinos",
                                   _cidades(atuais), _cidades(destinos), link=link))
        oficio = t.oficio
        if (oficio is not None and t.viatura_id and oficio.viatura_id
                and t.viatura_id != oficio.viatura_id):
            saida.append(Diferenca(f"termo-{t.pk}:viatura", str(t), "viatura", str(t.viatura),
                                   str(oficio.viatura), link=link))
    for r in docs.roteiros:
        trechos = list(r.trechos.order_by("ordem"))
        if not trechos or not inicio:
            continue
        link = reverse("viagens:editar_roteiro", args=[r.pk])
        ida = timezone.localtime(trechos[0].saida_em).date()
        volta = timezone.localtime(trechos[-1].chegada_em or trechos[-1].saida_em).date()
        if ida > inicio:
            saida.append(Diferenca(f"roteiro-{r.pk}:saida", f"Roteiro #{r.pk}", "saída",
                                   f"{ida:%d/%m/%Y}", f"até {inicio:%d/%m/%Y}",
                                   aplicavel=False, link=link))
        if fim and volta < fim:
            saida.append(Diferenca(f"roteiro-{r.pk}:volta", f"Roteiro #{r.pk}", "volta",
                                   f"{volta:%d/%m/%Y}", f"a partir de {fim:%d/%m/%Y}",
                                   aplicavel=False, link=link))
    return saida


@dataclass
class Aplicacao:
    atualizados: list[str] = field(default_factory=list)
    pulados: list[tuple[str, str]] = field(default_factory=list)  # (documento, campo)


@transaction.atomic
def aplicar(usuario, viagem_pk: int, chaves: list[str] | None = None) -> Aplicacao:
    """Leva período, destinos e equipe da viagem aos documentos sem via assinada. Com
    `chaves`, só aquelas diferenças."""
    viagem = Viagem.objects.select_for_update().get(pk=viagem_pk)
    policies.exigir(policies.pode_editar_viagem(usuario, viagem),
                    "Reative a viagem antes de corrigir os documentos.")
    docs = documentos(viagem)
    inicio, fim = viagem.data_inicio, viagem.data_fim or viagem.data_inicio
    destinos = [d.municipio for d in viagem.destinos.select_related("municipio")]
    equipe = _equipe_dos_oficios(docs)
    resultado = Aplicacao()
    feitos: set[str] = set()
    for d in coerencia(viagem):
        if not d.aplicavel or (chaves is not None and d.chave not in chaves):
            continue
        tipo, resto = d.chave.split("-", 1)
        pk = int(resto.split(":")[0])
        if _assinado(tipo, pk):
            resultado.pulados.append((d.documento, d.campo))
            continue
        if tipo == "ordem":
            o = OrdemServico.objects.get(pk=pk)
            if d.campo == "período":
                OrdemServico.objects.filter(pk=pk).update(data_inicio=inicio, data_fim=fim)
            elif d.campo == "destinos":
                o.destinos.all().delete()
                OrdemServicoDestino.objects.bulk_create(
                    OrdemServicoDestino(ordem=o, municipio=m, posicao=i)
                    for i, m in enumerate(destinos))
            elif d.campo == "equipe":
                o.servidores.set(equipe)
                o.oficios.add(*[x for x in docs.oficios
                                if x.situacao != x.Situacao.CANCELADO])
            OrdemServico.objects.filter(pk=pk).update(atualizado_em=timezone.now())
        elif tipo == "plano":
            p = PlanoTrabalho.objects.get(pk=pk)
            if d.campo == "período":
                p.data_inicio, p.data_fim = inicio, fim
                p.save(update_fields=["data_inicio", "data_fim", "atualizado_em"])
            elif d.campo == "destinos":
                p.destinos.all().delete()
                PlanoDestino.objects.bulk_create(PlanoDestino(plano=p, municipio=m, posicao=i)
                                                 for i, m in enumerate(destinos))
            planos._refazer_e_gravar(PlanoTrabalho.objects.get(pk=pk))
        elif tipo == "termo":
            t = TermoAutorizacao.objects.get(pk=pk)
            if d.campo == "período":
                TermoAutorizacao.objects.filter(pk=pk).update(
                    data_inicio=inicio, data_fim=fim if fim != inicio else None,
                    atualizado_em=timezone.now())
            elif d.campo == "destinos":
                t.destinos.all().delete()
                TermoDestino.objects.bulk_create(TermoDestino(termo=t, municipio=m, ordem=i)
                                                 for i, m in enumerate(destinos))
                TermoAutorizacao.objects.filter(pk=pk).update(atualizado_em=timezone.now())
            elif d.campo == "viatura" and t.oficio is not None:
                TermoAutorizacao.objects.filter(pk=pk).update(
                    viatura_id=t.oficio.viatura_id, atualizado_em=timezone.now())
        if d.documento not in feitos:
            feitos.add(d.documento)
            resultado.atualizados.append(d.documento)
    return resultado


def _assinado(tipo: str, pk: int) -> bool:
    from .models import ViaAssinada
    campo = {"ordem": "ordem_id", "termo": "termo_id"}.get(tipo)
    if campo is None:  # plano não recebe via assinada
        return False
    return ViaAssinada.objects.filter(**{campo: pk}, revogada_em__isnull=True).exists()
