"""Escritas do atendimento à imprensa (transação; autorização pelas policies).

- `criar` / `salvar`: os campos do pedido, das fontes e da resposta (a folha se grava
  sozinha). Um veículo ainda não cadastrado pode vir pelo nome ("outro veículo"): usa o de
  mesmo nome, sem diferença de maiúsculas, ou cria — como na referência.
- `registrar_andamento`: muda a situação com a anotação e deixa o `Andamento`.
- Cadastros de apoio (equipe e veículos): criar, renomear e excluir quando não usado.

A trilha de auditoria do banco registra cada gravação; o histórico da folha a lê.
"""

from __future__ import annotations

from datetime import date, time
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, Q

from . import dominio, policies
from .models import Andamento, Atendimento, Integrante, Veiculo

CAMPOS = ("data", "horario", "jornalista", "veiculo", "contato", "pedido", "responsavel",
          "deadline", "horario_resposta", "responsavel_resposta", "fonte", "inicio_pedido",
          "final_pedido", "resposta")
UMA_LINHA = ("jornalista", "contato")
VARIAS_LINHAS = ("pedido", "fonte", "inicio_pedido", "final_pedido", "resposta")


class AtendimentoInvalido(ValueError):
    """Os dados não atendem a uma regra; `campo` diz onde mostrar o erro."""

    def __init__(self, mensagem: str, campo: str | None = None) -> None:
        super().__init__(mensagem)
        self.campo = campo


def veiculo_por_nome(nome: str) -> Veiculo | None:
    nome = dominio.uma_linha(nome)[:150]
    if not nome:
        return None
    existente = Veiculo.objects.filter(nome__iexact=nome).first()
    if existente:
        return existente
    try:
        with transaction.atomic():
            return Veiculo.objects.create(nome=nome)
    except IntegrityError:  # criado agora por outra pessoa
        return Veiculo.objects.get(nome__iexact=nome)


def _aplicar(atendimento: Atendimento, dados: dict[str, Any]) -> None:
    for campo in CAMPOS:
        if campo not in dados:
            continue
        valor = dados[campo]
        if campo in UMA_LINHA:
            valor = dominio.uma_linha(valor)
        elif campo in VARIAS_LINHAS:
            valor = dominio.multilinha(valor)
        setattr(atendimento, campo, valor)
    novo = dados.get("veiculo_novo") or ""
    if novo.strip():
        atendimento.veiculo = veiculo_por_nome(novo)


def _conferir(atendimento: Atendimento) -> None:
    if not atendimento.jornalista:
        raise AtendimentoInvalido("Informe o jornalista.", "jornalista")
    if not atendimento.pedido:
        raise AtendimentoInvalido("Descreva o pedido.", "pedido")
    if not isinstance(atendimento.data, date):
        raise AtendimentoInvalido("Informe a data do pedido.", "data")
    if erro := dominio.conferir_deadline(atendimento.data, atendimento.deadline):
        raise AtendimentoInvalido(erro, "deadline")
    if (atendimento.situacao == dominio.ATENDIDO
            and not (atendimento.resposta or atendimento.andamento)):
        raise AtendimentoInvalido(
            "Registre a resposta enviada (ou o andamento): o atendimento está como atendido.",
            "resposta")


@transaction.atomic
def criar(usuario, dados: dict[str, Any]) -> Atendimento:
    if not policies.pode_criar(usuario):
        raise PermissionDenied
    atendimento = Atendimento(criado_por=usuario)
    _aplicar(atendimento, dados)
    _conferir(atendimento)
    atendimento.save()
    return atendimento


@transaction.atomic
def salvar(usuario, pk: int, dados: dict[str, Any]) -> Atendimento:
    if not policies.pode_editar(usuario):
        raise PermissionDenied
    atendimento = Atendimento.objects.select_for_update().get(pk=pk)
    _aplicar(atendimento, dados)
    _conferir(atendimento)
    atendimento.save()
    return atendimento


@transaction.atomic
def registrar_andamento(usuario, pk: int, nova: str, anotacao: str = "") -> Atendimento:
    """Muda a situação com a anotação de andamento (regras em `dominio.conferir_andamento`)."""
    if not policies.pode_editar(usuario):
        raise PermissionDenied
    atendimento = Atendimento.objects.select_for_update().get(pk=pk)
    anotacao = dominio.multilinha(anotacao)
    try:
        dominio.conferir_andamento(atendimento.situacao, nova, anotacao, atendimento.resposta,
                                   atendimento.andamento)
    except dominio.RegraViolada as exc:
        raise AtendimentoInvalido(str(exc), "nova_situacao") from exc
    anterior = atendimento.situacao
    atendimento.situacao = nova
    if anotacao:
        atendimento.andamento = anotacao
    atendimento.save(update_fields=["situacao", "andamento", "atualizado_em"])
    Andamento.objects.create(atendimento=atendimento, situacao_anterior=anterior,
                             situacao_nova=nova, anotacao=anotacao, usuario=usuario)
    return atendimento


def ultima_anotacao(atendimento: Atendimento) -> str:
    ultimo = atendimento.andamentos.order_by("-em", "-pk").first()
    return ultimo.anotacao if ultimo else atendimento.andamento


# ------------------------------------------------------------------ cadastros de apoio
TIPOS: dict[str, Any] = {"equipe": Integrante, "veiculos": Veiculo}
LIMITES = {"equipe": 100, "veiculos": 150}


def em_uso(tipo: str, registro: Any) -> int:
    if tipo == "equipe":
        return Atendimento.objects.filter(
            Q(responsavel=registro) | Q(responsavel_resposta=registro)).count()
    return Atendimento.objects.filter(veiculo=registro).count()


def usos_por_registro(tipo: str) -> dict[int, int]:
    """Quantos atendimentos usam cada registro (para a lista do cadastro, numa consulta)."""
    if tipo == "veiculos":
        return dict(Atendimento.objects.filter(veiculo__isnull=False).values_list("veiculo")
                    .annotate(n=Count("pk")).order_by())
    usos: dict[int, int] = {}
    for um, outro in Atendimento.objects.filter(
            Q(responsavel__isnull=False) | Q(responsavel_resposta__isnull=False)
    ).values_list("responsavel_id", "responsavel_resposta_id"):
        for pk in {um, outro} - {None}:
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
        raise AtendimentoInvalido("Informe o nome.", "nome")
    if len(nome) > limite:
        raise AtendimentoInvalido(f"Use no máximo {limite} caracteres.", "nome")
    repetido = modelo.objects.filter(nome__iexact=nome).exclude(pk=pk).exists()
    if repetido:
        raise AtendimentoInvalido(f"Já existe “{nome}” no cadastro.", "nome")
    registro = modelo.objects.select_for_update().get(pk=pk) if pk else modelo()
    registro.nome = nome
    try:
        with transaction.atomic():
            registro.save()
    except IntegrityError as exc:
        raise AtendimentoInvalido(f"Já existe “{nome}” no cadastro.", "nome") from exc
    return registro


@transaction.atomic
def excluir_cadastro(usuario, tipo: str, pk: int) -> str:
    if not policies.pode_gerir_cadastros(usuario):
        raise PermissionDenied
    registro = TIPOS[tipo].objects.select_for_update().get(pk=pk)
    usos = em_uso(tipo, registro)
    if usos:
        raise AtendimentoInvalido(
            f"“{registro.nome}” está em {usos} atendimento{'s' if usos > 1 else ''}: "
            "não dá para excluir.")
    nome = registro.nome
    registro.delete()
    return nome


def agora_sem_segundos(hora: time) -> time:
    return hora.replace(second=0, microsecond=0)
