"""Escrita dos cadastros de apoio (servidores, viaturas, unidades, cargos, combustíveis,
tabela de diárias e configuração institucional).

Toda gravação passa por aqui, em transação e com a permissão conferida de novo (a tela
só esconde o que não pode). A auditoria é do banco (trigger). Paridade com o CRUD da
referência: excluir só sem vínculos; quando há vínculos, a mensagem diz quais e sugere
desativar (o registro sai das escolhas, a história fica).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast

from django.db import IntegrityError, models, transaction
from django.db.models import Count

from . import policies
from .models import (
    Cargo,
    Combustivel,
    ConfiguracaoInstitucional,
    Servidor,
    SubstituicaoAssinante,
    TabelaDiaria,
    Unidade,
    Viatura,
)


class CadastroInvalido(Exception):
    """Erro com mensagem pronta para o usuário."""


# Valor mínimo da diária de 24 h: abaixo dele os 15% arredondam para zero (referência, P08).
DIARIA_MINIMA = Decimal("0.04")


@dataclass(frozen=True)
class Vinculo:
    rotulo: str
    total: int

    def __str__(self) -> str:
        return f"{self.total} {self.rotulo}"


def vinculos(objeto: models.Model) -> list[Vinculo]:
    """Registros que impedem a exclusão (relações PROTECT/RESTRICT que apontam para ele)."""
    por_modelo: dict[type[models.Model], int] = {}
    # include_hidden: as relações sem nome reverso ("+", ex.: sede do ofício) também protegem.
    for relacao in objeto._meta.get_fields(include_hidden=True):
        if not (relacao.auto_created and not relacao.concrete
                and (relacao.one_to_many or relacao.one_to_one)):
            continue
        if getattr(relacao, "on_delete", None) not in (models.PROTECT, models.RESTRICT):
            continue
        modelo = cast(type[models.Model], relacao.related_model)
        nome = cast(models.ForeignObjectRel, relacao).field.name
        total = modelo._default_manager.filter(**{nome: objeto}).count()
        if total:
            por_modelo[modelo] = por_modelo.get(modelo, 0) + total
    return [Vinculo(str(m._meta.verbose_name if n == 1 else m._meta.verbose_name_plural), n)
            for m, n in por_modelo.items()]


def _exigir_alterar(usuario, modelo) -> None:
    policies.exigir(policies.pode_alterar_cadastro(usuario, modelo),
                    f"Você não pode alterar {modelo._meta.verbose_name_plural}.")


def _gravar(objeto: models.Model, duplicado: str) -> None:
    """Grava; a unicidade do banco (nome, CPF…) vira mensagem, nunca erro 500."""
    try:
        with transaction.atomic():
            objeto.save()
    except IntegrityError as exc:
        raise CadastroInvalido(duplicado) from exc


# ---------------------------------------------------------------- catálogos simples
@transaction.atomic
def salvar_unidade(usuario, *, nome: str, sigla: str = "", pk: int | None = None) -> Unidade:
    if pk:
        _exigir_alterar(usuario, Unidade)
        unidade = Unidade.objects.select_for_update().get(pk=pk)
    else:
        policies.exigir(policies.pode_criar_cadastro(usuario, Unidade))
        unidade = Unidade()
    unidade.nome, unidade.sigla = nome, sigla
    _gravar(unidade, f"Já existe uma unidade chamada “{nome}”.")
    return unidade


@transaction.atomic
def salvar_catalogo(usuario, modelo: type[Cargo] | type[Combustivel], *, nome: str,
                    padrao: bool | None = None, pk: int | None = None):
    """Cargo ou combustível. `padrao=None` preserva o que está gravado (a edição do nome
    não desmarca o padrão — referência, P05)."""
    if pk:
        _exigir_alterar(usuario, modelo)
        objeto = modelo.objects.select_for_update().get(pk=pk)
    else:
        policies.exigir(policies.pode_criar_cadastro(usuario, modelo))
        objeto = modelo()
    objeto.nome = nome
    nome_cadastro = modelo._meta.verbose_name
    _gravar(objeto, f"Já existe um {nome_cadastro} chamado “{nome}”.")
    if padrao is not None and padrao != objeto.padrao:
        definir_padrao(usuario, modelo, objeto.pk, padrao=padrao)
        objeto.refresh_from_db()
    return objeto


@transaction.atomic
def definir_padrao(usuario, modelo: type[Cargo] | type[Combustivel], pk: int, *,
                   padrao: bool = True):
    """Um padrão por cadastro: marcar um novo desmarca o anterior na mesma transação."""
    _exigir_alterar(usuario, modelo)
    objeto = modelo.objects.select_for_update().get(pk=pk)
    if padrao:
        if not objeto.ativo:
            raise CadastroInvalido(f"“{objeto.nome}” está inativo: reative antes de "
                                   "usá-lo como padrão.")
        modelo.objects.filter(padrao=True).exclude(pk=pk).update(padrao=False)
    objeto.padrao = padrao
    try:
        with transaction.atomic():
            objeto.save(update_fields=["padrao", "atualizado_em"])
    except IntegrityError as exc:  # outra pessoa marcou outro padrão ao mesmo tempo
        raise CadastroInvalido("Outro padrão acabou de ser escolhido. Tente de novo.") from exc
    return objeto


@transaction.atomic
def alternar_ativo(usuario, modelo, pk: int):
    """Desativar tira das escolhas (ofício, viatura…) sem apagar a história; reativar volta."""
    _exigir_alterar(usuario, modelo)
    objeto = modelo.objects.select_for_update().get(pk=pk)
    objeto.ativo = not objeto.ativo
    campos = ["ativo", "atualizado_em"]
    if not objeto.ativo and getattr(objeto, "padrao", False):
        objeto.padrao = False  # o padrão precisa estar ativo (o banco também garante)
        campos.append("padrao")
    objeto.save(update_fields=campos)
    return objeto


@transaction.atomic
def excluir(usuario, modelo, pk: int) -> str:
    """Exclui de vez, só sem vínculos. Devolve o nome do que foi excluído."""
    policies.exigir(policies.pode_excluir_cadastro(usuario, modelo),
                    f"Você não pode excluir {modelo._meta.verbose_name_plural}.")
    objeto = modelo.objects.select_for_update().get(pk=pk)
    achados = vinculos(objeto)
    if achados:
        lista = " e ".join(str(v) for v in achados)
        raise CadastroInvalido(f"Não é possível excluir “{objeto}”: este cadastro é usado em "
                               f"{lista}. Desative para tirá-lo das escolhas sem perder a "
                               "história.")
    nome = str(objeto)
    viaturas = objeto.viaturas_que_dirige.count() if isinstance(objeto, Servidor) else 0
    if viaturas:  # vínculo que não protege (motorista habitual): sai junto, mas é dito
        nome += f" (deixou de ser motorista habitual de {viaturas} viatura" \
                f"{'s' if viaturas > 1 else ''})"
    try:
        with transaction.atomic():
            objeto.delete()
    except models.ProtectedError as exc:  # vínculo criado entre a conferência e a exclusão
        raise CadastroInvalido(f"Não é possível excluir “{nome}”: há registros ligados a "
                               "este cadastro. Desative para tirá-lo das escolhas.") from exc
    return nome


# ---------------------------------------------------------------- servidores
@transaction.atomic
def salvar_servidor(usuario, *, nome: str, cargo: Cargo | None = None, cpf: str = "",
                    rg: str = "", telefone: str = "", unidade: Unidade | None = None,
                    pk: int | None = None) -> Servidor:
    if pk:
        _exigir_alterar(usuario, Servidor)
        servidor = Servidor.objects.select_for_update().get(pk=pk)
    else:
        policies.exigir(policies.pode_criar_cadastro(usuario, Servidor))
        servidor = Servidor()
    servidor.nome, servidor.cargo, servidor.cpf = nome, cargo, cpf
    servidor.rg, servidor.telefone, servidor.unidade = rg, telefone, unidade
    _gravar(servidor, "Já existe um servidor com este nome, CPF, RG ou telefone.")
    return servidor


# ---------------------------------------------------------------- viaturas
@transaction.atomic
def salvar_viatura(usuario, *, placa: str, modelo: str = "", tipo: str = "",
                   combustivel: Combustivel | None = None, unidade: Unidade | None = None,
                   motoristas=(), pk: int | None = None) -> Viatura:
    if pk:
        _exigir_alterar(usuario, Viatura)
        viatura = Viatura.objects.select_for_update().get(pk=pk)
    else:
        policies.exigir(policies.pode_criar_cadastro(usuario, Viatura))
        viatura = Viatura()
    viatura.placa, viatura.modelo, viatura.tipo = placa, modelo, tipo
    viatura.combustivel, viatura.unidade = combustivel, unidade
    _gravar(viatura, f"Já existe uma viatura com a placa {viatura.placa_formatada}.")
    viatura.motoristas.set(list(motoristas))
    return viatura


# ---------------------------------------------------------------- tabela de diárias
@transaction.atomic
def salvar_vigencia(usuario, *, faixa: str, vigente_desde: date, valor_24h: Decimal,
                    norma: str = "", pk: int | None = None) -> TabelaDiaria:
    """Uma vigência por faixa e data. Os percentuais (15%, 30%) saem do valor de 24 h."""
    if pk:
        policies.exigir(policies.pode_alterar_cadastro(usuario, TabelaDiaria),
                        "Só o gestor altera a tabela de diárias.")
        vigencia = TabelaDiaria.objects.select_for_update().get(pk=pk)
    else:
        policies.exigir(policies.pode_criar_cadastro(usuario, TabelaDiaria),
                        "Só o gestor cadastra vigências de diária.")
        vigencia = TabelaDiaria()
    if valor_24h < DIARIA_MINIMA:
        raise CadastroInvalido("Valor muito baixo: o percentual de 15% ficaria zerado.")
    vigencia.faixa, vigencia.vigente_desde = faixa, vigente_desde
    vigencia.valor_24h, vigencia.norma = valor_24h, norma
    _gravar(vigencia, "Já existe uma vigência desta faixa nesta data. Edite a existente.")
    return vigencia


@transaction.atomic
def excluir_vigencia(usuario, pk: int) -> str:
    policies.exigir(policies.pode_excluir_cadastro(usuario, TabelaDiaria),
                    "Só o gestor exclui vigências de diária.")
    vigencia = TabelaDiaria.objects.select_for_update().get(pk=pk)
    restantes = TabelaDiaria.objects.filter(faixa=vigencia.faixa).exclude(pk=pk)
    if not restantes.exists():
        raise CadastroInvalido(f"É a única vigência da faixa {vigencia.get_faixa_display()}: "
                               "sem ela, nenhuma diária dessa faixa poderia ser calculada.")
    nome = str(vigencia)
    vigencia.delete()
    return nome


# ---------------------------------------------------------------- configuração da unidade
CAMPOS_CONFIGURACAO = (
    "nome_extenso", "sede", "endereco_rodape", "chefia_nome", "chefia_cargo",
    "destinatario_tratamento", "destinatario_nome", "destinatario_cargo",
    "destinatario_orgao", "destinatario_cidade", "prazo_justificativa_dias",
    "assina_oficio", "assina_justificativa",
    "cep", "logradouro", "numero", "bairro", "cidade_endereco", "uf", "email", "telefone",
    "ramal",
)


@transaction.atomic
def salvar_configuracao(usuario, unidade: Unidade, **dados) -> ConfiguracaoInstitucional:
    policies.exigir(policies.pode_alterar_configuracao(usuario, unidade),
                    "Só o gestor altera a configuração da unidade.")
    config = (ConfiguracaoInstitucional.objects.select_for_update()
              .filter(unidade=unidade).first() or ConfiguracaoInstitucional(unidade=unidade))
    for campo in CAMPOS_CONFIGURACAO:
        if campo in dados:
            setattr(config, campo, dados[campo])
    config.save()
    return config


def assinante(config: ConfiguracaoInstitucional, tipo: str, data) -> tuple[str, str]:
    """(nome, cargo) de quem assina o documento `tipo` ("oficio", "justificativa") datado em
    `data`: o substituto vigente na data (do tipo ou de todos; dois valendo, o de início mais
    recente); senão o titular escolhido para o tipo; senão a chefia escrita na configuração.
    Paridade com `_assinatura_nome_cargo` da referência."""
    for sub in config.substituicoes.all():  # ordem: início mais recente primeiro
        if sub.vale_em(tipo, data):
            return sub.servidor.nome, getattr(sub.servidor.cargo, "nome", "")
    titular = {"oficio": config.assina_oficio,
               "justificativa": config.assina_justificativa}.get(tipo)
    if titular is not None:
        return titular.nome, getattr(titular.cargo, "nome", "")
    return config.chefia_nome, config.chefia_cargo


@transaction.atomic
def salvar_substituicao(usuario, unidade: Unidade, *, servidor: Servidor, tipo: str,
                        inicio: date, fim: date | None = None, motivo: str = "",
                        pk: int | None = None) -> SubstituicaoAssinante:
    policies.exigir(policies.pode_alterar_configuracao(usuario, unidade),
                    "Só o gestor define substituições de assinante.")
    config = ConfiguracaoInstitucional.objects.filter(unidade=unidade).first()
    if config is None:
        raise CadastroInvalido("Salve a configuração da unidade antes de cadastrar "
                               "substituições.")
    if fim is not None and fim < inicio:
        raise CadastroInvalido("O fim não pode ser antes do início.")
    sub = (SubstituicaoAssinante.objects.select_for_update().get(pk=pk, configuracao=config)
           if pk else SubstituicaoAssinante(configuracao=config))
    sub.servidor, sub.tipo, sub.inicio, sub.fim, sub.motivo = servidor, tipo, inicio, fim, motivo
    sub.save()
    return sub


@transaction.atomic
def encerrar_substituicao(usuario, unidade: Unidade, pk: int) -> SubstituicaoAssinante:
    """Desativa (a história fica: documentos já emitidos citam quem assinou)."""
    policies.exigir(policies.pode_alterar_configuracao(usuario, unidade),
                    "Só o gestor define substituições de assinante.")
    sub = SubstituicaoAssinante.objects.select_for_update().get(
        pk=pk, configuracao__unidade=unidade)
    sub.ativo = not sub.ativo
    sub.save(update_fields=["ativo"])
    return sub


# ---------------------------------------------------------------- leitura de apoio
def contagem_por(qs, campo: str) -> dict[int, int]:
    """{pk: total} para os filtros com contagem (ex.: servidores por cargo)."""
    return dict(qs.exclude(**{f"{campo}__isnull": True}).values(campo)
                .annotate(n=Count("id")).values_list(campo, "n"))
