"""Escritas do controle de publicações (transação; autorização pelas policies).

- `criar` / `salvar`: os campos da pauta (a folha se grava sozinha). A unidade ainda não
  cadastrada pode vir pelo nome ("outra unidade"): usa a de mesmo nome, sem diferença de
  maiúsculas, ou cria — como na referência; sem unidade nenhuma, a pauta não é aceita.
- `registrar_andamento`: muda o status com a anotação e deixa o `Andamento`; publicar sem
  data usa o agora.
- Cadastros de apoio (equipe e unidades): criar, renomear e excluir quando não usado.

A trilha de auditoria do banco registra cada gravação; o histórico da folha a lê.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from . import dominio, policies
from .models import Andamento, Integrante, Publicacao, UnidadeResponsavel

CAMPOS = ("data", "jornalista", "unidade", "fonte", "inicio_pauta", "titulo",
          "colocada_edicao", "data_publicacao", "horario_publicacao", "revisao",
          "galeria_fotos", "bitly_grupos", "enviado_sesp", "publicado_aen", "link_site",
          "link_aen")
UMA_LINHA = ("titulo", "fonte")

PautaInvalida = dominio.RegraViolada


def unidade_por_nome(nome: str) -> UnidadeResponsavel | None:
    nome = dominio.uma_linha(nome)[:150]
    if not nome:
        return None
    existente = UnidadeResponsavel.objects.filter(nome__iexact=nome).first()
    if existente:
        return existente
    try:
        with transaction.atomic():
            return UnidadeResponsavel.objects.create(nome=nome)
    except IntegrityError:  # criada agora por outra pessoa
        return UnidadeResponsavel.objects.get(nome__iexact=nome)


def _aplicar(pauta: Publicacao, dados: dict[str, Any]) -> None:
    for campo in CAMPOS:
        if campo in dados:
            valor = dados[campo]
            setattr(pauta, campo, dominio.uma_linha(valor) if campo in UMA_LINHA else valor)
    nova = dados.get("unidade_nova") or ""
    if nova.strip():
        pauta.unidade = unidade_por_nome(nova)


def _conferir(pauta: Publicacao) -> None:
    if not pauta.titulo:
        raise PautaInvalida("Informe o título da pauta.", "titulo")
    if not pauta.jornalista_id:
        raise PautaInvalida("Escolha o jornalista responsável.", "jornalista")
    if not pauta.unidade_id:
        raise PautaInvalida(dominio.MSG_UNIDADE, "unidade")
    dominio.conferir_datas(pauta.status, pauta.data, pauta.data_publicacao)


@transaction.atomic
def criar(usuario, dados: dict[str, Any]) -> Publicacao:
    if not policies.pode_criar(usuario):
        raise PermissionDenied
    pauta = Publicacao(criado_por=usuario)
    _aplicar(pauta, dados)
    _conferir(pauta)
    pauta.save()
    return pauta


@transaction.atomic
def salvar(usuario, pk: int, dados: dict[str, Any]) -> Publicacao:
    if not policies.pode_editar(usuario):
        raise PermissionDenied
    pauta = Publicacao.objects.select_for_update().get(pk=pk)
    _aplicar(pauta, dados)
    _conferir(pauta)
    pauta.save()
    return pauta


# O que se copia ao duplicar: a pauta (de hoje) — a publicação é de cada uma.
CAMPOS_DUPLICADOS = ("jornalista", "unidade", "fonte", "inicio_pauta", "titulo")


@transaction.atomic
def duplicar(usuario, pk: int) -> Publicacao:
    """Uma pauta nova, de hoje, com o mesmo título, jornalista, unidade e fonte — sem a
    publicação (datas, links, envios), o andamento e o histórico."""
    if not policies.pode_criar(usuario):
        raise PermissionDenied
    origem = Publicacao.objects.get(pk=pk)
    dados = {c: getattr(origem, c) for c in CAMPOS_DUPLICADOS}
    dados["data"] = timezone.localdate()
    return criar(usuario, dados)


@transaction.atomic
def registrar_andamento(usuario, pk: int, novo: str, anotacao: str = "") -> Publicacao:
    if not policies.pode_editar(usuario):
        raise PermissionDenied
    pauta = Publicacao.objects.select_for_update().get(pk=pk)
    dominio.conferir_novo_status(pauta.status, novo)
    anotacao = (anotacao or "").strip()
    anterior = pauta.status
    pauta.status = novo
    campos = ["status", "andamento", "atualizado_em"]
    if anotacao:
        pauta.andamento = anotacao
    if novo == dominio.PUBLICADA and not pauta.data_publicacao:
        pauta.data_publicacao, pauta.horario_publicacao = dominio.publicacao_automatica(
            pauta.data, pauta.data_publicacao, pauta.horario_publicacao,
            timezone.localtime())
        campos += ["data_publicacao", "horario_publicacao"]
    pauta.save(update_fields=campos)
    Andamento.objects.create(publicacao=pauta, status_anterior=anterior, status_novo=novo,
                             anotacao=anotacao, usuario=usuario)
    return pauta


def ultima_anotacao(pauta: Publicacao) -> str:
    ultimo = pauta.andamentos.order_by("-em", "-pk").first()
    return ultimo.anotacao if ultimo else pauta.andamento


# ------------------------------------------------------------------ cadastros de apoio
TIPOS: dict[str, Any] = {"equipe": Integrante, "unidades": UnidadeResponsavel}
LIMITES = {"equipe": 100, "unidades": 150}


def em_uso(tipo: str, registro: Any) -> int:
    if tipo == "equipe":
        return Publicacao.objects.filter(Q(jornalista=registro) | Q(revisao=registro)
                                         | Q(galeria_fotos=registro)).count()
    return Publicacao.objects.filter(unidade=registro).count()


def usos_por_registro(tipo: str) -> dict[int, int]:
    """Quantas pautas usam cada registro (para a lista do cadastro, numa consulta)."""
    if tipo == "unidades":
        return dict(Publicacao.objects.filter(unidade__isnull=False).values_list("unidade")
                    .annotate(n=Count("pk")).order_by())
    usos: dict[int, int] = {}
    for trio in Publicacao.objects.values_list("jornalista_id", "revisao_id",
                                               "galeria_fotos_id"):
        for pk in set(trio) - {None}:
            usos[pk] = usos.get(pk, 0) + 1
    return usos


@transaction.atomic
def salvar_cadastro(usuario, tipo: str, nome: str, pk: int | None = None):
    if not policies.pode_gerir_cadastros(usuario):
        raise PermissionDenied
    modelo = TIPOS[tipo]
    limite = LIMITES[tipo]
    nome = dominio.uma_linha(nome)
    if not nome:
        raise PautaInvalida("Informe o nome.", "nome")
    if len(nome) > limite:
        raise PautaInvalida(f"Use no máximo {limite} caracteres.", "nome")
    if modelo.objects.filter(nome__iexact=nome).exclude(pk=pk).exists():
        raise PautaInvalida(f"Já existe “{nome}” no cadastro.", "nome")
    registro = modelo.objects.select_for_update().get(pk=pk) if pk else modelo()
    registro.nome = nome
    try:
        with transaction.atomic():
            registro.save()
    except IntegrityError as exc:
        raise PautaInvalida(f"Já existe “{nome}” no cadastro.", "nome") from exc
    return registro


@transaction.atomic
def excluir_cadastro(usuario, tipo: str, pk: int) -> str:
    if not policies.pode_gerir_cadastros(usuario):
        raise PermissionDenied
    registro = TIPOS[tipo].objects.select_for_update().get(pk=pk)
    usos = em_uso(tipo, registro)
    if usos:
        raise PautaInvalida(f"“{registro.nome}” está em {usos} pauta{'s' if usos > 1 else ''}: "
                            "não dá para excluir.")
    nome = registro.nome
    registro.delete()
    return nome
