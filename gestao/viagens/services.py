"""Comandos do módulo Viagens. Toda escrita de negócio passa por aqui.

Cada comando: valida permissão e estado, roda numa transação, registra o
histórico de negócio e publica efeitos colaterais na outbox (mesma transação).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from itertools import pairwise

from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.utils import timezone

from gestao.cadastros.models import ConfiguracaoInstitucional, Municipio, Servidor
from gestao.plataforma import outbox

from . import policies
from .dominio import bate_volta as dominio_bate_volta
from .dominio import diarias as dominio_diarias
from .dominio.numeracao import proximo_numero
from .dominio.prazos import AvaliacaoPrazo, avaliar_prazo
from .models import (
    BateVoltaRoteiro,
    Documento,
    Historico,
    LacunaNumeracao,
    NumeracaoAnual,
    Oficio,
    Roteiro,
    Trecho,
    TrechoRoteiro,
    Viajante,
)
from .queries import buscar_tabelas_vigentes, trechos_de, trechos_do_roteiro, viajantes_de


class RegraViolada(Exception):
    """Erro de negócio com mensagem pronta para o usuário."""


class ConflitoDeEdicao(RegraViolada):
    pass


def _registrar(oficio: Oficio, acao: str, descricao: str, usuario, **dados) -> None:
    Historico.objects.create(oficio=oficio, acao=acao, descricao=descricao, usuario=usuario,
                             dados=dados)


def configuracao_da_unidade(oficio_ou_unidade) -> ConfiguracaoInstitucional:
    unidade = getattr(oficio_ou_unidade, "unidade", oficio_ou_unidade)
    try:
        return unidade.configuracao
    except ConfiguracaoInstitucional.DoesNotExist as exc:
        raise RegraViolada(
            f"A unidade {unidade} ainda não tem configuração institucional (cabeçalho, "
            "chefia e destinatário). Peça ao administrador para cadastrá-la."
        ) from exc


# ---------------------------------------------------------------- numeração
def reservar_numero(ano: int) -> int:
    """Próximo número do ano (dominio.numeracao). Serializa por ano com lock na linha de
    numeração; a lacuna usada deixa de existir na mesma transação."""
    numeracao, _ = NumeracaoAnual.objects.get_or_create(ano=ano)
    NumeracaoAnual.objects.select_for_update().get(pk=numeracao.pk)
    ocupados = Oficio.objects.filter(ano=ano).values_list("numero", flat=True)
    lacunas = LacunaNumeracao.objects.filter(ano=ano).values_list("numero", flat=True)
    numero = proximo_numero(ocupados, numeracao.piso, lacunas)
    LacunaNumeracao.objects.filter(ano=ano, numero=numero).delete()
    return numero


# ---------------------------------------------------------------- criação
@transaction.atomic
def criar_rascunho(usuario, *, data_oficio: date | None = None) -> Oficio:
    policies.exigir(policies.pode_criar(usuario),
                    "Seu usuário não está lotado em uma unidade ou não pode criar ofícios.")
    unidade = policies.unidade_do_usuario(usuario)
    if unidade is None:
        raise RegraViolada("Seu usuário não está lotado em nenhuma unidade.")
    config = configuracao_da_unidade(unidade)
    data_oficio = data_oficio or timezone.localdate()
    oficio = Oficio.objects.create(
        unidade=unidade, ano=data_oficio.year, numero=reservar_numero(data_oficio.year),
        data_oficio=data_oficio, sede=config.sede, criado_por=usuario,
    )
    _registrar(oficio, Historico.Acao.CRIADO,
               f"Rascunho criado com o número {oficio.numero_formatado}.", usuario)
    return oficio


# ---------------------------------------------------------------- edição
CAMPOS_EDITAVEIS = [
    "data_oficio", "protocolo", "marcador", "motivo", "custeio", "custeio_instituicao",
    "tipo_transporte", "viatura", "transporte_descricao", "transporte_placa",
    "transporte_combustivel", "porte_arma", "justificativa_modelo", "justificativa", "roteiro",
    "sede",
]


def _travar_para_edicao(oficio: Oficio, usuario, versao: int | None) -> Oficio:
    atual = (Oficio.objects.select_for_update(of=("self",))
             .select_related("sede", "viatura").get(pk=oficio.pk))
    policies.exigir(policies.pode_editar(usuario, atual),
                    "Este ofício não pode ser alterado (emitido, cancelado ou sem permissão).")
    if versao is not None and versao != atual.versao:
        raise ConflitoDeEdicao(
            "Outra pessoa salvou este ofício enquanto você editava. Recarregue a página para "
            "ver a versão atual antes de salvar de novo."
        )
    return atual


@transaction.atomic
def salvar_dados(oficio: Oficio, usuario, dados: dict, *, versao: int | None = None) -> Oficio:
    atual = _travar_para_edicao(oficio, usuario, versao)
    _aplicar_dados(atual, usuario, dados)
    return atual


@transaction.atomic
def salvar_edicao(oficio: Oficio, usuario, dados: dict, trechos: list[TrechoInformado] | None,
                  *, versao: int | None = None) -> Oficio:
    """Dados + roteiro do formulário numa só transação: ou grava tudo, ou nada."""
    atual = _travar_para_edicao(oficio, usuario, versao)
    _aplicar_dados(atual, usuario, dados)
    if trechos is not None:
        _aplicar_trechos(atual, trechos, tocar=False)  # a versão já subiu com os dados
        recalcular_diarias(atual)
    return atual


def _aplicar_dados(atual: Oficio, usuario, dados: dict) -> None:
    if dados.get("data_oficio") and dados["data_oficio"].year != atual.ano:
        raise RegraViolada(
            f"A data do ofício deve estar em {atual.ano}, o ano do número "
            f"{atual.numero_formatado}."
        )
    alterados = []
    for campo in CAMPOS_EDITAVEIS:
        if campo in dados and getattr(atual, campo) != dados[campo]:
            setattr(atual, campo, dados[campo])
            alterados.append(campo)
    if atual.tipo_transporte == Oficio.TipoTransporte.VIATURA:
        atual.transporte_descricao = atual.transporte_placa = ""
        atual.transporte_combustivel = None
    else:
        atual.viatura = None
    if atual.custeio != Oficio.Custeio.OUTRA_INSTITUICAO:
        atual.custeio_instituicao = ""
    atual.versao += 1
    atual.save()
    # Diárias dependem só de trechos, equipe e sede: nada aqui muda o cálculo.
    if alterados:
        _registrar(atual, Historico.Acao.ALTERADO, "Dados do ofício alterados.", usuario,
                   campos=alterados)


@transaction.atomic
def adicionar_viajante(oficio: Oficio, usuario, servidor: Servidor) -> Viajante:
    atual = _travar_para_edicao(oficio, usuario, None)
    if not servidor.ativo:
        raise RegraViolada(f"{servidor} está inativo no cadastro de servidores.")
    if atual.viajantes.filter(servidor=servidor).exists():
        raise RegraViolada(f"{servidor} já está na equipe deste ofício.")
    ordem = (atual.viajantes.aggregate(m=Max("ordem"))["m"] or 0) + 1
    viajante = Viajante.objects.create(oficio=atual, servidor=servidor, ordem=ordem)
    _registrar(atual, Historico.Acao.VIAJANTE, f"{servidor} incluído na equipe.", usuario)
    _tocar(atual)
    return viajante


@transaction.atomic
def remover_viajante(oficio: Oficio, usuario, viajante_id: int) -> None:
    atual = _travar_para_edicao(oficio, usuario, None)
    viajante = atual.viajantes.select_related("servidor").get(pk=viajante_id)
    viajante.delete()
    _registrar(atual, Historico.Acao.VIAJANTE, f"{viajante.servidor} removido da equipe.",
               usuario)
    _tocar(atual)


@transaction.atomic
def definir_motorista(oficio: Oficio, usuario, viajante_id: int | None) -> None:
    atual = _travar_para_edicao(oficio, usuario, None)
    atual.viajantes.filter(motorista=True).update(motorista=False)
    if viajante_id:
        atual.viajantes.filter(pk=viajante_id).update(motorista=True)
    _tocar(atual, recalcular=False)


def _tocar(oficio: Oficio, *, recalcular: bool = True) -> None:
    Oficio.objects.filter(pk=oficio.pk).update(versao=oficio.versao + 1,
                                               atualizado_em=timezone.now())
    oficio.versao += 1
    if recalcular:
        recalcular_diarias(oficio)


@dataclass(frozen=True)
class TrechoInformado:
    origem_id: int
    destino_id: int
    saida_em: datetime
    chegada_em: datetime
    distancia_km: Decimal | None = None
    tempo_viagem_min: int | None = None
    tempo_adicional_min: int = 0

    def campos(self) -> dict:
        return {"origem_id": self.origem_id, "destino_id": self.destino_id,
                "saida_em": self.saida_em, "chegada_em": self.chegada_em,
                "distancia_km": self.distancia_km, "tempo_viagem_min": self.tempo_viagem_min,
                "tempo_adicional_min": self.tempo_adicional_min}


@transaction.atomic
def salvar_trechos(oficio: Oficio, usuario, trechos: list[TrechoInformado]) -> None:
    _aplicar_trechos(_travar_para_edicao(oficio, usuario, None), trechos)


# Teto de trechos gravados: vinte dias de bate-volta (duas pernas por dia).
LIMITE_TRECHOS = 40


def _validar_sequencia(trechos: list[TrechoInformado]) -> None:
    """Regras comuns ao roteiro do ofício e ao roteiro cadastrado."""
    if len(trechos) > LIMITE_TRECHOS:
        raise RegraViolada(
            f"São {len(trechos)} trechos e o limite é {LIMITE_TRECHOS} "
            f"({LIMITE_TRECHOS // 2} dias de bate-volta). Divida em mais de um roteiro."
        )
    for anterior, seguinte in pairwise(trechos):
        if seguinte.saida_em < anterior.chegada_em:
            raise RegraViolada(
                "Um trecho sai antes da chegada do anterior. Confira datas e horários."
            )
        if seguinte.origem_id != anterior.destino_id:
            raise RegraViolada("Cada trecho deve sair da cidade onde o anterior chegou.")


def _aplicar_trechos(atual: Oficio, trechos: list[TrechoInformado], *, tocar: bool = True) -> None:
    _validar_sequencia(trechos)
    atual.trechos.all().delete()
    Trecho.objects.bulk_create([
        Trecho(oficio=atual, ordem=i, **t.campos()) for i, t in enumerate(trechos, start=1)
    ])
    if tocar:
        _tocar(atual)


# ---------------------------------------------------------------- cálculo
def _calcular_trechos(trechos, sede, servidores: int) -> dominio_diarias.CalculoDiarias:
    if not trechos:
        raise dominio_diarias.RoteiroIncalculavel("Informe os trechos (ida e volta).")
    if trechos[-1].destino_id != sede.pk:
        raise dominio_diarias.RoteiroIncalculavel(
            f"O último trecho precisa voltar para a sede ({sede})."
        )
    destinos = [
        dominio_diarias.Destino(t.destino.nome, t.destino.uf,
                                timezone.localtime(t.saida_em), timezone.localtime(t.chegada_em))
        for t in trechos
    ]
    return dominio_diarias.calcular(
        destinos, timezone.localtime(trechos[-1].chegada_em),
        buscar_tabelas=buscar_tabelas_vigentes,
        servidores=servidores,
        sede=(sede.nome, sede.uf),
    )


def calcular(oficio: Oficio) -> dominio_diarias.CalculoDiarias:
    """Calcula as diárias do ofício (sem gravar). Levanta erros de domínio."""
    return _calcular_trechos(trechos_de(oficio), oficio.sede, len(viajantes_de(oficio)))


def calcular_informados(trechos: list[TrechoInformado], sede,
                        servidores: int = 1) -> dominio_diarias.CalculoDiarias:
    """Diárias de trechos ainda não gravados (prévia enquanto a pessoa preenche a tela).
    Mesmas regras do cálculo que vale ao salvar — nada é persistido."""
    municipios = Municipio.objects.in_bulk([t.destino_id for t in trechos])
    objetos = [Trecho(origem_id=t.origem_id, destino_id=t.destino_id, saida_em=t.saida_em,
                      chegada_em=t.chegada_em) for t in trechos]
    for objeto, informado in zip(objetos, trechos, strict=True):
        objeto.destino = municipios[informado.destino_id]
    return _calcular_trechos(objetos, sede, servidores)


def _gravar_diarias(obj: Oficio | Roteiro, calcular_fn) -> None:
    """Grava o cálculo (ou o motivo de não calcular) no ofício ou no roteiro."""
    modelo = type(obj)
    try:
        resultado = calcular_fn()
    except (dominio_diarias.RoteiroIncalculavel, dominio_diarias.SemTabelaDeDiarias) as exc:
        modelo.objects.filter(pk=obj.pk).update(
            diarias_total=Decimal(0), diarias_resumo="", diarias_calculo={},
            diarias_erro=str(exc)[:300])
        obj.diarias_total, obj.diarias_resumo, obj.diarias_erro = Decimal(0), "", str(exc)
        obj.diarias_calculo = {}
        return
    dados = resultado.como_dict()
    modelo.objects.filter(pk=obj.pk).update(
        diarias_total=resultado.total, diarias_resumo=resultado.resumo, diarias_calculo=dados,
        diarias_erro="")
    obj.diarias_total, obj.diarias_resumo = resultado.total, resultado.resumo
    obj.diarias_calculo, obj.diarias_erro = dados, ""


def recalcular_diarias(oficio: Oficio) -> None:
    _gravar_diarias(oficio, lambda: calcular(oficio))


def avaliar_prazo_do_oficio(oficio: Oficio) -> AvaliacaoPrazo:
    trechos = trechos_de(oficio)
    saida = timezone.localdate(trechos[0].saida_em) if trechos else None
    prazo = configuracao_da_unidade(oficio).prazo_justificativa_dias
    return avaliar_prazo(oficio.data_oficio, saida, prazo)


# ---------------------------------------------------------------- pendências
@dataclass(frozen=True)
class Pendencia:
    secao: str
    mensagem: str
    bloqueia: bool = True


@dataclass
class Prontidao:
    pendencias: list[Pendencia] = field(default_factory=list)

    @property
    def bloqueantes(self) -> list[Pendencia]:
        return [p for p in self.pendencias if p.bloqueia]

    @property
    def pode_emitir(self) -> bool:
        return not self.bloqueantes

    def da_secao(self, secao: str) -> list[Pendencia]:
        return [p for p in self.pendencias if p.secao == secao]


def verificar_prontidao(oficio: Oficio) -> Prontidao:
    p: list[Pendencia] = []
    if not oficio.motivo.strip():
        p.append(Pendencia("dados", "Descreva o motivo da viagem."))
    if not oficio.protocolo:
        # Decisão D1: protocolo é obrigatório para emitir (como na referência).
        p.append(Pendencia("dados", "Informe o protocolo do eProtocolo."))
    if oficio.custeio == Oficio.Custeio.OUTRA_INSTITUICAO and not oficio.custeio_instituicao:
        p.append(Pendencia("dados", "Informe qual instituição custeia a viagem."))
    viajantes = viajantes_de(oficio)
    if not viajantes:
        p.append(Pendencia("equipe", "Inclua ao menos um servidor na equipe."))
    if oficio.tipo_transporte == Oficio.TipoTransporte.VIATURA:
        if not oficio.viatura_id:
            p.append(Pendencia("transporte", "Escolha a viatura."))
        if viajantes and not any(v.motorista for v in viajantes):
            p.append(Pendencia("equipe", "Indique quem da equipe é o motorista da viatura."))
    elif not oficio.transporte_descricao.strip():
        p.append(Pendencia("transporte", "Descreva o meio de transporte."))
    if not trechos_de(oficio):
        p.append(Pendencia("roteiro", "Informe os trechos de ida e de volta."))
    if oficio.diarias_erro:
        p.append(Pendencia("diarias", oficio.diarias_erro))
    prazo = avaliar_prazo_do_oficio(oficio)
    if prazo.justificativa_obrigatoria and not oficio.justificativa.strip():
        p.append(Pendencia("justificativa", prazo.mensagem))
    conflitos = conflitos_de_agenda(oficio)
    p.extend(Pendencia("equipe", c, False) for c in conflitos)
    return Prontidao(p)


def conflitos_de_agenda(oficio: Oficio) -> list[str]:
    """Avisos (não bloqueiam): servidor ou viatura em outro ofício no mesmo período."""
    trechos = trechos_de(oficio)
    if not trechos:
        return []
    inicio, fim = trechos[0].saida_em, trechos[-1].chegada_em
    sobrepostos = (
        Oficio.objects.exclude(pk=oficio.pk).exclude(situacao=Oficio.Situacao.CANCELADO)
        .filter(trechos__saida_em__lt=fim, trechos__chegada_em__gt=inicio).distinct()
    )
    servidores = {v.servidor_id for v in viajantes_de(oficio)}
    avisos = []
    for outro in sobrepostos.prefetch_related("viajantes__servidor"):
        for v in outro.viajantes.all():
            if v.servidor_id in servidores:
                avisos.append(f"{v.servidor} também está no Ofício {outro.numero_formatado} "
                              "no mesmo período.")
        if oficio.viatura is not None and outro.viatura_id == oficio.viatura_id:
            avisos.append(f"A viatura {oficio.viatura.placa_formatada} também está no Ofício "
                          f"{outro.numero_formatado} no mesmo período.")
    return avisos


# ---------------------------------------------------------------- emissão
@transaction.atomic
def emitir(oficio: Oficio, usuario, *, versao: int | None = None) -> Documento:
    atual = _travar_para_edicao(oficio, usuario, versao)
    policies.exigir(policies.pode_emitir(usuario, atual), "Você não pode emitir ofícios.")
    recalcular_diarias(atual)
    prontidao = verificar_prontidao(atual)
    if not prontidao.pode_emitir:
        raise RegraViolada("Ainda há pendências: " + "; ".join(
            p.mensagem for p in prontidao.bloqueantes))
    agora = timezone.now()
    atual.situacao = Oficio.Situacao.EMITIDO
    atual.emitido_em = agora
    atual.versao += 1
    atual.save(update_fields=["situacao", "emitido_em", "versao", "atualizado_em"])

    from .documentos.dados import dados_do_oficio  # evita import circular

    documentos = []
    tipos = [Documento.Tipo.OFICIO]
    if atual.justificativa.strip():
        tipos.append(Documento.Tipo.JUSTIFICATIVA)
    for tipo in tipos:
        ultima = atual.documentos.filter(tipo=tipo).aggregate(m=Max("versao"))["m"] or 0
        doc = Documento.objects.create(oficio=atual, tipo=tipo, versao=ultima + 1,
                                       dados=dados_do_oficio(atual), emitido_por=usuario)
        outbox.publicar("viagens.documento.gerar", {"documento_id": doc.pk},
                        chave=f"documento:{doc.pk}")
        documentos.append(doc)
    _registrar(atual, Historico.Acao.EMITIDO,
               f"Ofício {atual.numero_formatado} emitido (versão {documentos[0].versao}).",
               usuario, total=str(atual.diarias_total), resumo=atual.diarias_resumo)
    outbox.publicar("viagens.oficio.emitido", {"oficio_id": atual.pk},
                    chave=f"oficio-emitido:{atual.pk}:{documentos[0].versao}")
    return documentos[0]


@transaction.atomic
def reabrir(oficio: Oficio, usuario, motivo: str) -> Oficio:
    atual = (Oficio.objects.select_for_update(of=("self",))
             .select_related("sede", "viatura").get(pk=oficio.pk))
    policies.exigir(policies.pode_reabrir(usuario, atual), "Você não pode reabrir este ofício.")
    if not motivo.strip():
        raise RegraViolada("Explique por que o ofício está sendo reaberto.")
    atual.situacao = Oficio.Situacao.RASCUNHO
    atual.emitido_em = None
    atual.versao += 1
    atual.save(update_fields=["situacao", "emitido_em", "versao", "atualizado_em"])
    _registrar(atual, Historico.Acao.REABERTO, f"Reaberto para correção: {motivo.strip()}",
               usuario)
    return atual


@transaction.atomic
def cancelar(oficio: Oficio, usuario, motivo: str) -> Oficio:
    atual = (Oficio.objects.select_for_update(of=("self",))
             .select_related("sede", "viatura").get(pk=oficio.pk))
    policies.exigir(policies.pode_cancelar(usuario, atual), "Você não pode cancelar este ofício.")
    if not motivo.strip():
        raise RegraViolada("Informe o motivo do cancelamento.")
    atual.situacao = Oficio.Situacao.CANCELADO
    atual.cancelado_em = timezone.now()
    atual.motivo_cancelamento = motivo.strip()
    atual.versao += 1
    atual.save(update_fields=["situacao", "cancelado_em", "motivo_cancelamento", "versao",
                              "atualizado_em"])
    _registrar(atual, Historico.Acao.CANCELADO, f"Cancelado: {motivo.strip()}", usuario)
    return atual


@transaction.atomic
def excluir_rascunho(oficio: Oficio, usuario) -> str:
    atual = (Oficio.objects.select_for_update(of=("self",))
             .select_related("sede", "viatura").get(pk=oficio.pk))
    policies.exigir(policies.pode_excluir(usuario, atual),
                    "Só rascunhos sem documento emitido podem ser excluídos.")
    numero = atual.numero_formatado
    ano, livre = atual.ano, atual.numero
    atual.historico.all().delete()
    atual.delete()
    # Só a exclusão libera número para reaproveitamento (decisão D5).
    LacunaNumeracao.objects.get_or_create(ano=ano, numero=livre)
    return numero


def buscar_por_texto(qs, termo: str):
    """Busca por número (131 ou 131/2026), protocolo, motivo, destino ou servidor."""
    termo = (termo or "").strip()
    if not termo:
        return qs
    filtro = (Q(motivo__icontains=termo) | Q(trechos__destino__nome__unaccent__icontains=termo)
              | Q(viajantes__servidor__nome__unaccent__icontains=termo))
    digitos = "".join(c for c in termo if c.isdigit())
    numero = re.match(r"^(\d{1,5})(?:\s*/\s*(\d{4})?)?$", termo)
    if numero:
        por_numero = Q(numero=int(numero.group(1)))
        if numero.group(2):
            por_numero &= Q(ano=int(numero.group(2)))
        filtro |= por_numero
    if len(digitos) >= 5:
        filtro |= Q(protocolo__contains=digitos)
    return qs.filter(filtro).distinct()


__all__ = ["IntegrityError"]


def assunto_do_oficio(oficio: Oficio):
    """Autorização × Convalidação pela data do ofício e da 1ª saída (dominio.assunto)."""
    from .dominio.assunto import resolver_assunto

    trechos = trechos_de(oficio)
    saida = timezone.localdate(trechos[0].saida_em) if trechos else None
    return resolver_assunto(oficio.data_oficio, saida, oficio.marcador)


# ---------------------------------------------------------------- roteiros cadastrados
CAMPOS_ROTEIRO = ["quantidade_servidores", "observacoes", "sede", "bate_volta"]


def recalcular_diarias_roteiro(roteiro: Roteiro) -> None:
    """Diárias estimadas do roteiro para o efetivo informado (quantidade de servidores)."""
    _gravar_diarias(roteiro, lambda: _calcular_trechos(
        list(roteiro.trechos.select_related("origem", "destino")), roteiro.sede,
        roteiro.quantidade_servidores))


@transaction.atomic
def salvar_roteiro(usuario, roteiro: Roteiro | None, dados: dict,
                   trechos: list[TrechoInformado] | None,
                   blocos: list[dominio_bate_volta.Bloco] | None = None) -> Roteiro:
    """Cria (roteiro=None) ou altera um roteiro. A sede é a da unidade, como no ofício.
    Roteiro sem trechos é permitido (rascunho); as diárias dizem o que falta."""
    if roteiro is None:
        policies.exigir(policies.pode_criar_roteiro(usuario),
                        "Seu usuário precisa estar lotado em uma unidade para criar roteiros.")
        unidade = policies.unidade_do_usuario(usuario)
        roteiro = Roteiro(unidade=unidade, sede=configuracao_da_unidade(unidade).sede,
                          criado_por=usuario)
    else:
        roteiro = (Roteiro.objects.select_for_update(of=("self",)).select_related("sede")
                   .get(pk=roteiro.pk))
        policies.exigir(policies.pode_editar_roteiro(usuario, roteiro),
                        "Este roteiro não pode ser alterado (cancelado ou sem permissão).")
    for campo in CAMPOS_ROTEIRO:
        if campo in dados:
            setattr(roteiro, campo, dados[campo])
    roteiro.save()
    if trechos is not None:
        _validar_sequencia(trechos)
        roteiro.trechos.all().delete()
        TrechoRoteiro.objects.bulk_create([
            TrechoRoteiro(roteiro=roteiro, ordem=i, **t.campos())
            for i, t in enumerate(trechos, start=1)
        ])
    if blocos is not None:
        # Desligar o modo apaga os blocos: guardá-los inertes os faria reaparecer, com datas
        # velhas, se o modo fosse religado.
        roteiro.bate_voltas.all().delete()
        if roteiro.bate_volta:
            BateVoltaRoteiro.objects.bulk_create([
                BateVoltaRoteiro(roteiro=roteiro, ordem=i, destino_id=b.destino_id,
                                 dia_inicial=b.dia_inicial, dia_final=b.dia_final,
                                 hora_saida=b.hora_saida, hora_volta=b.hora_volta)
                for i, b in enumerate(blocos, start=1)
            ])
    recalcular_diarias_roteiro(roteiro)
    return roteiro


@transaction.atomic
def cancelar_roteiro(usuario, roteiro: Roteiro) -> Roteiro:
    policies.exigir(policies.pode_cancelar_roteiro(usuario, roteiro))
    Roteiro.objects.filter(pk=roteiro.pk).update(situacao=Roteiro.Situacao.CANCELADO,
                                                 atualizado_em=timezone.now())
    roteiro.situacao = Roteiro.Situacao.CANCELADO
    return roteiro


@transaction.atomic
def reativar_roteiro(usuario, roteiro: Roteiro) -> Roteiro:
    policies.exigir(policies.pode_cancelar_roteiro(usuario, roteiro))
    Roteiro.objects.filter(pk=roteiro.pk).update(situacao=Roteiro.Situacao.ATIVO,
                                                 atualizado_em=timezone.now())
    roteiro.situacao = Roteiro.Situacao.ATIVO
    return roteiro


@transaction.atomic
def excluir_roteiro(usuario, roteiro: Roteiro) -> None:
    policies.exigir(policies.pode_excluir_roteiro(usuario, roteiro))
    usados = list(roteiro.oficios.order_by("ano", "numero")[:3])
    if usados:
        nomes = ", ".join(o.numero_formatado for o in usados)
        raise RegraViolada(f"O roteiro #{roteiro.pk} já serviu de modelo para o(s) Ofício(s) "
                           f"{nomes}. Cancele o roteiro em vez de excluir.")
    roteiro.delete()


def _informado(t: Trecho | TrechoRoteiro) -> TrechoInformado:
    return TrechoInformado(t.origem_id, t.destino_id, t.saida_em, t.chegada_em, t.distancia_km,
                           t.tempo_viagem_min, t.tempo_adicional_min)


def trechos_informados_do_roteiro_de(oficio: Oficio) -> list[TrechoInformado]:
    """Trechos do ofício no formato de entrada (para cadastrar um roteiro a partir dele)."""
    return [_informado(t) for t in trechos_de(oficio)]


def trechos_informados_do_roteiro(roteiro: Roteiro) -> list[TrechoInformado]:
    return [_informado(t) for t in trechos_do_roteiro(roteiro)]


def exigir_roteiro_compativel(roteiro: Roteiro, oficio: Oficio) -> None:
    """Roteiro ativo serve a qualquer ofício visível; a sede vem junto com os trechos."""
    if not roteiro.editavel:
        raise RegraViolada(f"O roteiro #{roteiro.pk} está cancelado.")


@transaction.atomic
def criar_oficio_do_roteiro(usuario, roteiro: Roteiro) -> Oficio:
    """"Criar ofício com este roteiro": rascunho numerado com os trechos copiados do roteiro.
    Mudar o roteiro depois não altera o ofício (e vice-versa)."""
    policies.exigir(policies.pode_ver_roteiro(usuario, roteiro))
    oficio = criar_rascunho(usuario)
    exigir_roteiro_compativel(roteiro, oficio)
    trechos = trechos_informados_do_roteiro(roteiro)
    if trechos:  # a sede do roteiro vira a sede do ofício (abaixo)
        _aplicar_trechos(oficio, trechos, tocar=False)
    Oficio.objects.filter(pk=oficio.pk).update(roteiro=roteiro, sede=roteiro.sede)
    oficio.roteiro, oficio.sede = roteiro, roteiro.sede
    recalcular_diarias(oficio)
    _registrar(oficio, Historico.Acao.ALTERADO,
               f"Roteiro preenchido a partir do roteiro #{roteiro.pk}.", usuario,
               campos=["roteiro"])
    return oficio
