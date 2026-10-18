"""Porta de leitura e reconciliação da fonte dedicada com espelho local.

Uma futura integração entrega IDs externos e valores a `atualizar_da_fonte`; nunca
devolve IDs remotos para formulários nem escreve configurações locais da unidade.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q

from . import policies
from .dominio_catalogo import ConflitoDeCadastro, normalizar_da_origem, reconciliar
from .models import AtividadePlano, Cargo, Servidor, Unidade, Viatura, VinculoFonteCadastro

MODELOS: dict[str, type[models.Model]] = {
    "servidor": Servidor, "viatura": Viatura, "unidade": Unidade,
    "cargo": Cargo, "atividade": AtividadePlano,
}
# Relações, padrões, configuração e complementos documentais ficam locais.
CAMPOS_DA_ORIGEM = {
    "servidor": {"nome", "cpf", "rg", "telefone", "ativo"},
    "viatura": {"placa", "modelo", "tipo", "porte", "ativo"},
    "unidade": {"nome", "sigla", "ativo"},
    "cargo": {"nome", "ativo"},
    "atividade": {"nome", "ativo"},
}


class FonteLocalCadastros:
    """Catálogos globais já autorizados pelos fluxos; não concede acesso a documentos.

    `incluir` serve apenas aos IDs que o consumidor já autorizou no registro editado.
    Assim um item inativo selecionado continua legível fora da página inicial.
    """

    def consultar(self, entidade: str, *, incluir: Iterable[int] = (), ativos=True):
        modelo = MODELOS[entidade]
        qs = modelo._default_manager.all()
        if ativos:
            qs = qs.filter(Q(ativo=True) | Q(pk__in=list(incluir)))
        if entidade == "servidor":
            qs = qs.select_related("cargo", "unidade")
        elif entidade == "viatura":
            qs = qs.select_related("combustivel", "unidade")
        return qs


fonte_local = FonteLocalCadastros()


def atividades_e_servicos(*, incluir=()):
    return fonte_local.consultar("atividade", incluir=incluir).order_by("nome", "pk")


def _exigir_alteracao(usuario, entidade):
    modelo = MODELOS.get(entidade)
    policies.exigir(modelo is not None and policies.pode_alterar_cadastro(usuario, modelo))
    return modelo


@transaction.atomic
def vincular_fonte(usuario, *, entidade: str, registro_id: int, fonte: str,
                   identificador_externo: str, campos_externos: Iterable[str]):
    modelo = _exigir_alteracao(usuario, entidade)
    campos = set(campos_externos)
    if not campos or not campos <= CAMPOS_DA_ORIGEM[entidade]:
        raise ValidationError("Declare somente campos de cadastro autorizados à fonte.")
    if not fonte.strip() or not identificador_externo.strip():
        raise ValidationError("Informe a fonte e seu identificador estável.")
    registro = modelo._default_manager.select_for_update().get(pk=registro_id)
    vinculo = VinculoFonteCadastro(
        entidade=entidade, registro_id=registro.pk, fonte=fonte.strip(),
        identificador_externo=identificador_externo.strip(), campos_externos=sorted(campos),
        ultimo_estado={campo: getattr(registro, campo) for campo in sorted(campos)})
    vinculo.full_clean()
    vinculo.save()
    return vinculo


@transaction.atomic
def atualizar_da_fonte(usuario, *, vinculo_id: int, revisao: str, valores: dict):
    vinculo = VinculoFonteCadastro.objects.select_for_update().get(pk=vinculo_id)
    modelo = _exigir_alteracao(usuario, vinculo.entidade)
    if (not vinculo.campos_externos
            or not set(vinculo.campos_externos) <= CAMPOS_DA_ORIGEM[vinculo.entidade]):
        raise ValidationError("O vínculo declara campos locais. Revise a propriedade dos dados.")
    if not revisao.strip() or set(valores) != set(vinculo.campos_externos):
        raise ValidationError("Informe a revisão e todos os campos declarados da origem.")
    registro = modelo._default_manager.select_for_update().get(pk=vinculo.registro_id)
    try:
        valores = normalizar_da_origem(vinculo.entidade, valores)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    revisao = VinculoFonteCadastro._meta.get_field("revisao").clean(revisao, vinculo)
    valores = {campo: modelo._meta.get_field(campo).clean(valor, registro)
               for campo, valor in valores.items()}
    if revisao == vinculo.revisao and valores != vinculo.ultimo_estado:
        raise ValidationError("A revisão já foi recebida com outros valores. Confira a fonte.")
    local = {campo: getattr(registro, campo) for campo in vinculo.campos_externos}
    mudancas = reconciliar(vinculo.ultimo_estado, local, valores)
    for campo, valor in mudancas.items():
        setattr(registro, campo, valor)
    if mudancas:
        registro.full_clean()
        registro.save()
    vinculo.ultimo_estado, vinculo.revisao = valores.copy(), revisao
    vinculo.save(update_fields=["ultimo_estado", "revisao", "atualizado_em"])
    return registro


def exigir_campos_locais(registro, dados: dict):
    """CRUD local continua funcional; campos da origem pedem resolução explícita."""
    entidade = next((tipo for tipo, modelo in MODELOS.items()
                     if registro._meta.concrete_model is modelo), None)
    if entidade is None or not registro.pk:
        return
    vinculo = VinculoFonteCadastro.objects.filter(
        entidade=entidade, registro_id=registro.pk).first()
    if vinculo is None:
        return
    campos = [campo for campo in vinculo.campos_externos
              if campo in dados and getattr(registro, campo) != dados[campo]]
    if campos:
        raise ConflitoDeCadastro(campos)
