"""Textos prontos (motivo, justificativa, trechos do ofício): escrita e escolha.

Paridade com os catálogos de motivo e de modelo de justificativa da referência: nome, texto,
ordem, ativo e **um padrão por tipo** (o que já vem escrito quando o campo nasce vazio).
Toda gravação passa por aqui; a auditoria é do banco (trigger).
"""

from __future__ import annotations

from django.db import IntegrityError, transaction

from . import policies
from .models import ModeloTexto


class TextoInvalido(Exception):
    """Erro com mensagem pronta para o usuário."""


TIPOS_EDITAVEIS = [ModeloTexto.Tipo.MOTIVO, ModeloTexto.Tipo.JUSTIFICATIVA,
                   ModeloTexto.Tipo.OFICIO]


def opcoes(tipo: str) -> list[ModeloTexto]:
    """O que aparece na escolha "Texto pronto": só os ativos, na ordem combinada."""
    return list(ModeloTexto.objects.filter(tipo=tipo, ativo=True))


def padrao(tipo: str) -> ModeloTexto | None:
    return ModeloTexto.objects.filter(tipo=tipo, ativo=True, padrao=True).first()


def _normalizar(nome: str, texto: str) -> tuple[str, str]:
    nome = " ".join((nome or "").split())[:120]
    texto = (texto or "").strip()[:4000]
    if not nome:
        raise TextoInvalido("Dê um nome curto ao texto pronto, ex.: “Apoio da Unidade Móvel”.")
    if not texto:
        raise TextoInvalido("Escreva o texto que será inserido no campo.")
    return nome, texto


@transaction.atomic
def salvar(usuario, *, tipo: str, nome: str, texto: str, ordem: int | None = None,
           pk: int | None = None) -> ModeloTexto:
    """Cria (sem `pk`) ou altera um texto pronto."""
    policies.exigir(policies.pode_gerir_textos(usuario),
                    "Você não pode criar nem alterar textos prontos.")
    if tipo not in TIPOS_EDITAVEIS:
        raise TextoInvalido("Tipo de texto desconhecido.")
    nome, texto = _normalizar(nome, texto)
    duplicado = ModeloTexto.objects.filter(tipo=tipo, nome__iexact=nome, ativo=True)
    if pk:
        duplicado = duplicado.exclude(pk=pk)
    if duplicado.exists():
        raise TextoInvalido(f"Já existe um texto pronto chamado “{nome}”. Use outro nome.")
    if pk:
        modelo = ModeloTexto.objects.select_for_update().get(pk=pk)
        policies.exigir(policies.pode_alterar_texto(usuario, modelo),
                        "Este texto é o padrão ou vem com o sistema: só o gestor o altera.")
        if modelo.tipo != tipo and modelo.padrao:
            raise TextoInvalido("Este texto é o padrão do tipo atual; defina outro padrão "
                                "antes de mudar o tipo.")
        modelo.tipo, modelo.nome, modelo.texto = tipo, nome, texto
        if ordem is not None:
            modelo.ordem = ordem
        modelo.save()
        return modelo
    return ModeloTexto.objects.create(tipo=tipo, nome=nome, texto=texto,
                                      ordem=100 if ordem is None else ordem)


@transaction.atomic
def definir_padrao(usuario, pk: int) -> ModeloTexto:
    """Este passa a ser o padrão do tipo; o anterior deixa de ser (um só por tipo)."""
    policies.exigir(policies.pode_definir_padrao(usuario),
                    "Só o gestor escolhe o texto padrão (vale para todas as unidades).")
    modelo = ModeloTexto.objects.select_for_update().get(pk=pk)
    if not modelo.ativo:
        raise TextoInvalido("Reative o texto antes de torná-lo padrão.")
    ModeloTexto.objects.filter(tipo=modelo.tipo, padrao=True).exclude(pk=pk).update(padrao=False)
    modelo.padrao = True
    modelo.save(update_fields=["padrao", "atualizado_em"])
    return modelo


@transaction.atomic
def deixar_de_ser_padrao(usuario, pk: int) -> ModeloTexto:
    policies.exigir(policies.pode_definir_padrao(usuario),
                    "Só o gestor escolhe o texto padrão (vale para todas as unidades).")
    modelo = ModeloTexto.objects.select_for_update().get(pk=pk)
    modelo.padrao = False
    modelo.save(update_fields=["padrao", "atualizado_em"])
    return modelo


@transaction.atomic
def alternar_ativo(usuario, pk: int) -> ModeloTexto:
    """Desativar tira o texto da escolha sem apagar (ofícios antigos continuam apontando)."""
    modelo = ModeloTexto.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_alterar_texto(usuario, modelo),
                    "Este texto é o padrão ou vem com o sistema: só o gestor o desativa.")
    modelo.ativo = not modelo.ativo
    if not modelo.ativo:
        modelo.padrao = False  # inativo não pode ser o padrão (o banco também recusa)
    modelo.save(update_fields=["ativo", "padrao", "atualizado_em"])
    return modelo


@transaction.atomic
def desativar(usuario, pk: int) -> ModeloTexto:
    """Tira da escolha de forma idempotente (dois cliques não reativam). Os textos que vêm
    com o sistema não saem por aqui — é o "remover" do editor de documento."""
    modelo = ModeloTexto.objects.select_for_update().get(pk=pk)
    if modelo.padrao_sistema:
        raise TextoInvalido("Este texto vem com o sistema e não pode ser removido.")
    policies.exigir(policies.pode_alterar_texto(usuario, modelo),
                    "Este texto é o padrão: só o gestor o remove.")
    if modelo.ativo:
        modelo.ativo, modelo.padrao = False, False
        modelo.save(update_fields=["ativo", "padrao", "atualizado_em"])
    return modelo


@transaction.atomic
def excluir(usuario, pk: int) -> str:
    modelo = ModeloTexto.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_excluir_texto(usuario, modelo),
                    "Este texto não pode ser excluído por você. Desative-o para tirá-lo da lista.")
    nome = modelo.nome
    try:
        with transaction.atomic():
            modelo.delete()
    except IntegrityError:
        raise TextoInvalido(f"“{nome}” já foi usado em documentos; desative-o em vez de "
                            "excluir.") from None
    return nome
