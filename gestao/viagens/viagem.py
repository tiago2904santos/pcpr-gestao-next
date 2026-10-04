"""Viagem: o agrupador de roteiro, ofícios (com justificativa e termos), OS e plano
(paridade com `viagens_viagem` da referência; ficha em docs/migration/viagem.md).

Escritas aqui: criar (reaproveitando a viagem vazia esquecida), salvar os dados da etapa 1
(tipos → título, motivo, período, destinos, vínculos) e criar um documento já vinculado,
semeado com o que a viagem sabe. Cancelar/reativar em cascata, repetir, prontidão e
coerência chegam nos sub-módulos 8b–8d.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from gestao.cadastros.models import Municipio, TipoViagem

from . import policies
from .models import (
    Oficio,
    OrdemServico,
    PlanoTrabalho,
    Roteiro,
    TermoAutorizacao,
    Viagem,
    ViagemDestino,
)

MAX_DESTINOS = 30
ESQUECIDA = timedelta(minutes=30)
TIPOS_DE_DOCUMENTO = ("roteiros", "oficios", "planos", "ordens", "termos")


class ViagemInvalida(Exception):
    pass


def titulo_dos_tipos(nomes: list[str]) -> str:
    """O título nasce dos tipos (referência): "PCPR na Comunidade / Unidade Móvel"."""
    return " / ".join(n for n in nomes if n.strip())


def versao_de(viagem: Viagem) -> str:
    return viagem.atualizado_em.isoformat() if viagem.atualizado_em else ""


# ---------------------------------------------------------------- leitura
@dataclass
class Documentos:
    roteiros: list[Roteiro] = field(default_factory=list)
    oficios: list[Oficio] = field(default_factory=list)
    planos: list[PlanoTrabalho] = field(default_factory=list)
    ordens: list[OrdemServico] = field(default_factory=list)
    termos: list[TermoAutorizacao] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(len(getattr(self, t)) for t in TIPOS_DE_DOCUMENTO)


def documentos(viagem: Viagem) -> Documentos:
    """Os documentos da viagem. Roteiros e termos também contam quando chegam por um ofício
    dela (referência); os termos genéricos (sem ofício) vêm primeiro."""
    oficios = list(viagem.oficios.select_related("roteiro").order_by("ano", "numero"))
    ids = [o.pk for o in oficios]
    roteiros = list(Roteiro.objects.filter(Q(viagem=viagem) | Q(oficios__pk__in=ids))
                    .distinct().order_by("pk"))
    termos = list(TermoAutorizacao.objects.filter(Q(viagem=viagem) | Q(oficio_id__in=ids))
                  .distinct().order_by("oficio_id", "pk"))
    termos.sort(key=lambda t: (t.oficio_id is not None, t.pk))
    return Documentos(roteiros=roteiros, oficios=oficios,
                      planos=list(viagem.planos.order_by("ano", "numero")),
                      ordens=list(viagem.ordens.order_by("ano", "numero")), termos=termos)


def periodo_curto(inicio: date | None, fim: date | None) -> str:
    """"08/10 a 12/10/2026" ou "08/10/2026" (datas, sem hora)."""
    if not inicio:
        return ""
    fim = fim or inicio
    if fim == inicio:
        return f"{inicio:%d/%m/%Y}"
    return f"{inicio:%d/%m} a {fim:%d/%m/%Y}" if inicio.year == fim.year else (
        f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}")


def resumo_do_documento(doc) -> str:
    """Como o documento aparece para vincular: número, destino e período — como o operador
    o reconhece (referência)."""
    if isinstance(doc, Oficio):
        trechos = list(doc.trechos.all())
        destino = trechos[0].destino if trechos else None
        periodo = (periodo_curto(timezone.localtime(trechos[0].saida_em).date(),
                                 timezone.localtime(trechos[-1].chegada_em).date())
                   if trechos else "")
        partes = [str(destino) if destino else "", periodo]
    elif isinstance(doc, Roteiro):
        partes = [(doc.observacoes or "")[:60]]
    else:
        inicio = getattr(doc, "data_inicio", None)
        partes = [periodo_curto(inicio, getattr(doc, "data_fim", None))]
    extra = " · ".join(p for p in partes if p)
    return f"{doc} · {extra}" if extra else str(doc)


def candidatos(viagem: Viagem) -> dict[str, QuerySet]:
    """O que pode ser vinculado: da mesma unidade, desta viagem ou sem viagem, ativo."""
    def livres(qs):
        return qs.filter(unidade_id=viagem.unidade_id).filter(
            Q(viagem__isnull=True) | Q(viagem=viagem))
    oficios_dela = viagem.oficios.values("pk")
    return {
        "roteiros": livres(Roteiro.objects.exclude(situacao=Roteiro.Situacao.CANCELADO))
        .exclude(Q(viagem__isnull=True) & Q(oficios__pk__in=oficios_dela)).distinct()
        .order_by("-pk"),
        "oficios": livres(Oficio.objects.exclude(situacao=Oficio.Situacao.CANCELADO))
        .order_by("-ano", "-numero"),
        "planos": livres(PlanoTrabalho.objects.filter(cancelado=False)).order_by("-ano",
                                                                                 "-numero"),
        "ordens": livres(OrdemServico.objects.exclude(
            situacao=OrdemServico.Situacao.CANCELADA)).order_by("-ano", "-numero"),
        "termos": livres(TermoAutorizacao.objects.exclude(
            situacao=TermoAutorizacao.Situacao.CANCELADO))
        .exclude(Q(viagem__isnull=True) & Q(oficio_id__in=oficios_dela)).order_by("-pk"),
    }


def quando(viagem: Viagem, hoje: date | None = None) -> str:
    """"futura" (ou sem data), "atual" (começou) ou "cancelada" — as abas da lista."""
    if viagem.cancelada:
        return "cancelada"
    hoje = hoje or timezone.localdate()
    return "atual" if viagem.data_inicio and viagem.data_inicio <= hoje else "futura"


def dias_para(viagem: Viagem, hoje: date | None = None) -> str:
    """O selo de quando: "falta 1 dia", "faltam N dias", "em andamento", "realizada"."""
    hoje = hoje or timezone.localdate()
    inicio, fim = viagem.data_inicio, viagem.data_fim or viagem.data_inicio
    if inicio is None or viagem.cancelada:
        return ""
    if inicio > hoje:
        n = (inicio - hoje).days
        return "falta 1 dia" if n == 1 else f"faltam {n} dias"
    return "em andamento" if fim and fim >= hoje else "realizada"


# ---------------------------------------------------------------- escrita
def _vazia(viagem: Viagem) -> bool:
    return (not viagem.titulo and not viagem.motivo and not viagem.descricao
            and viagem.data_inicio is None and not viagem.destinos.exists()
            and not viagem.tipos.exists()
            and not any(getattr(viagem, t).exists() for t in TIPOS_DE_DOCUMENTO))


@transaction.atomic
def criar(usuario, *, data_inicio: date | None = None,
          data_fim: date | None = None) -> Viagem:
    """Nova viagem em rascunho. Reaproveita a vazia esquecida da unidade (> 30 min sem
    nada), como na referência — clicar em "Nova viagem" duas vezes não deixa lixo."""
    policies.exigir(policies.pode_criar_viagem(usuario),
                    "Seu usuário não está lotado em uma unidade ou não pode criar viagens.")
    unidade = policies.unidade_do_usuario(usuario)
    if unidade is None:
        raise ViagemInvalida("Seu usuário não está lotado em nenhuma unidade.")
    limite = timezone.now() - ESQUECIDA
    for antiga in (Viagem.objects.select_for_update()
                   .filter(unidade=unidade, situacao=Viagem.Situacao.RASCUNHO)
                   .filter(Q(criado_por=usuario) | Q(atualizado_em__lt=limite))
                   .order_by("pk")[:5]):
        if _vazia(antiga):
            antiga.data_inicio, antiga.data_fim = data_inicio, data_fim
            antiga.save(update_fields=["data_inicio", "data_fim", "atualizado_em"])
            return antiga
    return Viagem.objects.create(unidade=unidade, criado_por=usuario,
                                 data_inicio=data_inicio, data_fim=data_fim)


def _travar(usuario, pk: int, versao: str = "") -> Viagem:
    viagem = Viagem.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_editar_viagem(usuario, viagem),
                    "Esta viagem não pode ser alterada.")
    if versao and versao != versao_de(viagem):
        raise ViagemInvalida("Outra pessoa alterou esta viagem depois que você abriu a tela. "
                             "Recarregue para ver a versão atual.")
    return viagem


@transaction.atomic
def salvar_dados(usuario, pk: int, *, tipos: list[TipoViagem], motivo: str = "",
                 descricao: str = "", data_inicio: date | None = None,
                 data_fim: date | None = None, destinos: list[Municipio] | None = None,
                 vinculos: dict | None = None,
                 versao: str = "") -> Viagem:
    viagem = _travar(usuario, pk, versao)
    if data_inicio and data_fim and data_fim < data_inicio:
        raise ViagemInvalida("A data final não pode ser anterior à data inicial.")
    destinos = list(dict.fromkeys(destinos or []))
    if len(destinos) > MAX_DESTINOS:
        raise ViagemInvalida(f"No máximo {MAX_DESTINOS} destinos.")
    viagem.tipos.set(tipos)
    viagem.titulo = titulo_dos_tipos([t.nome for t in tipos])
    viagem.motivo, viagem.descricao = motivo.strip(), descricao.strip()
    viagem.data_inicio, viagem.data_fim = data_inicio, data_fim
    viagem.save()
    viagem.destinos.all().delete()
    ViagemDestino.objects.bulk_create(ViagemDestino(viagem=viagem, municipio=m, ordem=i)
                                      for i, m in enumerate(destinos))
    if vinculos is not None:
        _sincronizar(viagem, vinculos)
    _situacao_pelos_documentos(viagem)
    return viagem


def _situacao_pelos_documentos(viagem: Viagem) -> None:
    """Com documento, a viagem está em preparação; sem nenhum, rascunho (os demais estados
    vêm de ações próprias: gerar em lote, cancelar)."""
    if viagem.situacao not in (Viagem.Situacao.RASCUNHO, Viagem.Situacao.PREPARACAO):
        return
    tem = any(getattr(viagem, t).exists() for t in TIPOS_DE_DOCUMENTO)
    nova = Viagem.Situacao.PREPARACAO if tem else Viagem.Situacao.RASCUNHO
    if nova != viagem.situacao:
        Viagem.objects.filter(pk=viagem.pk).update(situacao=nova)
        viagem.situacao = nova


@transaction.atomic
def excluir_vazia(usuario, pk: int) -> None:
    """Só a viagem sem documentos se exclui por aqui (com documentos, no 8d)."""
    viagem = Viagem.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_excluir_viagem(usuario, viagem),
                    "Você não pode excluir esta viagem.")
    if any(getattr(viagem, t).exists() for t in TIPOS_DE_DOCUMENTO):
        raise ViagemInvalida("Só a viagem sem documentos se exclui por aqui.")
    viagem.delete()


def _sincronizar(viagem: Viagem, vinculos: dict) -> None:
    """Marca para vincular, desmarca para soltar (referência). Só o que é candidato, e só
    solta o que a tela mostrou (`(marcados, mostrados)`); uma lista simples solta tudo o que
    não estiver nela (uso interno)."""
    pode = candidatos(viagem)
    for tipo, valor in vinculos.items():
        if tipo not in TIPOS_DE_DOCUMENTO:
            continue
        escolhidos, mostrados = valor if isinstance(valor, tuple) else (valor, None)
        ids = {d.pk for d in escolhidos}
        permitidos = set(pode[tipo].filter(pk__in=ids).values_list("pk", flat=True))
        modelo = pode[tipo].model
        soltar = modelo.objects.filter(viagem=viagem).exclude(pk__in=permitidos)
        if mostrados is not None:
            soltar = soltar.filter(pk__in=mostrados)
        soltar.update(viagem=None)
        modelo.objects.filter(pk__in=permitidos).update(viagem=viagem)


# ---------------------------------------------------------------- documento novo vinculado
ROTULOS = {"roteiro": "roteiro", "oficio": "ofício", "termo": "termo de autorização",
           "ordem": "ordem de serviço", "plano": "plano de trabalho"}


@transaction.atomic
def novo_documento(usuario, pk: int, tipo: str):
    """Cria o documento em rascunho, já vinculado e semeado com período, destinos e motivo
    da viagem (referência: "semente de documentos"). Devolve o documento criado."""
    from . import ordens, planos, services, termos

    viagem = _travar(usuario, pk)
    doc: Any
    destinos = [d.municipio for d in viagem.destinos.select_related("municipio")]
    inicio, fim = viagem.data_inicio, viagem.data_fim or viagem.data_inicio
    if tipo == "roteiro":
        doc = services.salvar_roteiro(usuario, None, {"observacoes": viagem.motivo[:500]}, [])
    elif tipo == "oficio":
        doc = services.criar_rascunho(usuario)
        if viagem.motivo:
            Oficio.objects.filter(pk=doc.pk).update(motivo=viagem.motivo)
    elif tipo == "termo":
        if not destinos or not inicio or not viagem.titulo:
            raise ViagemInvalida("Informe o tipo, o período e o destino da viagem antes de "
                                 "criar o termo: o evento, as datas e o local nascem deles.")
        doc = termos.salvar(usuario, evento=viagem.titulo,
                            data_inicio=inicio, data_fim=fim if fim != inicio else None,
                            destinos=destinos)
    elif tipo == "ordem":
        doc, _ = ordens.salvar(usuario, destinos=destinos, data_inicio=inicio, data_fim=fim,
                               motivo=viagem.motivo)
    elif tipo == "plano":
        doc, _ = planos.salvar(usuario, data_inicio=inicio, data_fim=fim, destinos=destinos,
                               programa_outros="")
    else:
        raise ViagemInvalida("Documento desconhecido.")
    type(doc).objects.filter(pk=doc.pk).update(viagem=viagem)
    doc.viagem = viagem
    _situacao_pelos_documentos(viagem)
    return doc
