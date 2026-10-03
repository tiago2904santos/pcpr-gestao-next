"""Comandos do módulo Viagens. Toda escrita de negócio passa por aqui.

Cada comando: valida permissão e estado, roda numa transação, registra o
histórico de negócio e publica efeitos colaterais na outbox (mesma transação).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise

from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q
from django.utils import timezone

from gestao.cadastros import textos
from gestao.cadastros.models import ConfiguracaoInstitucional, ModeloTexto, Municipio, Servidor
from gestao.cadastros.validacoes import somente_digitos
from gestao.plataforma import outbox

from . import policies
from .documentos.campos import CAMPOS, CampoVinculado
from .documentos.regioes import (
    blocos_alterados,
    campos_presentes,
    impressao,
    normalizar,
    sanear_html,
)
from .dominio import bate_volta as dominio_bate_volta
from .dominio import busca as dominio_busca
from .dominio import diarias as dominio_diarias
from .dominio.numeracao import proximo_numero
from .dominio.prazos import AvaliacaoPrazo, avaliar_prazo
from .models import (
    BateVoltaRoteiro,
    Documento,
    EdicaoDocumento,
    Historico,
    LacunaNumeracao,
    NumeracaoAnual,
    Oficio,
    Roteiro,
    Trecho,
    TrechoRoteiro,
    Viajante,
)
from .queries import (
    aplicar_leitura,
    buscar_tabelas_vigentes,
    trechos_de,
    trechos_do_roteiro,
    viajantes_de,
)


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


@dataclass(frozen=True)
class AnoDeNumeracao:
    ano: int
    piso: int
    maior: int | None       # maior número já ocupado no ano
    total: int              # ofícios numerados no ano (cancelados contam)
    lacunas: list[int]      # liberados por exclusão, ainda livres
    proximo: int            # o número que o próximo "Novo ofício" do ano recebe


def resumo_numeracao(anos: list[int] | None = None) -> list[AnoDeNumeracao]:
    """Numeração por ano: piso, ocupação, lacunas e o próximo número (dominio.numeracao).
    Mostra o ano corrente e todo ano com ofício, piso ou lacuna; consultas fixas."""
    pisos = dict(NumeracaoAnual.objects.values_list("ano", "piso"))
    ocupacao: dict[int, tuple[int | None, int]] = {
        o["ano"]: (o["maior"], o["total"])
        for o in Oficio.objects.values("ano").annotate(maior=Max("numero"), total=Count("id"))}
    lacunas: dict[int, list[int]] = {}
    for ano, numero in LacunaNumeracao.objects.order_by("numero").values_list("ano", "numero"):
        lacunas.setdefault(ano, []).append(numero)
    todos = sorted(set(anos or []) | {timezone.localdate().year} | set(pisos) | set(ocupacao)
                   | set(lacunas), reverse=True)
    resumo = []
    for ano in todos:
        piso = pisos.get(ano, 1)
        maior, total = ocupacao.get(ano, (None, 0))
        livres = lacunas.get(ano, [])
        # Lacunas já ocupadas não existem (a reserva as apaga): o domínio decide o próximo.
        proximo = proximo_numero([maior] if maior else [], piso, livres)
        resumo.append(AnoDeNumeracao(ano, piso, maior, total, livres, proximo))
    return resumo


@transaction.atomic
def definir_piso(usuario, ano: int, piso: int) -> NumeracaoAnual:
    """Número inicial do ano. Não renumera nada: só muda de onde a sequência continua
    quando o piso passa do maior número já usado (dominio.numeracao)."""
    policies.exigir(policies.pode_gerir_numeracao(usuario),
                    "Só o gestor de viagens define a numeração anual.")
    if not 2000 <= ano <= 2100:
        raise RegraViolada("Informe um ano entre 2000 e 2100.")
    if not 1 <= piso <= 99999:
        raise RegraViolada("O piso vai de 1 a 99999.")
    numeracao, _ = NumeracaoAnual.objects.get_or_create(ano=ano)
    numeracao = NumeracaoAnual.objects.select_for_update().get(pk=numeracao.pk)
    numeracao.piso = piso
    numeracao.save(update_fields=["piso"])
    return numeracao


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
    # O motivo nasce com o texto padrão do catálogo, como na referência ("padrão sugerido
    # no novo"); a pessoa ajusta na folha.
    motivo_padrao = textos.padrao(ModeloTexto.Tipo.MOTIVO)
    oficio = Oficio.objects.create(
        unidade=unidade, ano=data_oficio.year, numero=reservar_numero(data_oficio.year),
        data_oficio=data_oficio, sede=config.sede, criado_por=usuario,
        motivo=motivo_padrao.texto if motivo_padrao else "",
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
    # Motorista de fora da equipe (D3)
    "motorista_externo", "motorista_externo_servidor", "motorista_externo_nome",
    "motorista_externo_rg", "motorista_externo_cpf", "motorista_externo_cargo",
    "motorista_externo_unidade", "motorista_externo_observacao", "motorista_oficio_origem",
    "motorista_protocolo_origem",
]
CAMPOS_MOTORISTA_MANUAL = ["motorista_externo_nome", "motorista_externo_rg",
                           "motorista_externo_cpf", "motorista_externo_cargo",
                           "motorista_externo_unidade", "motorista_externo_observacao"]
OFICIO_DE_ORIGEM = re.compile(r"^\d{1,6}/\d{4}$")  # até 6 dígitos, como a referência


def _normalizar_motorista_externo(atual: Oficio) -> bool:
    """Um motorista só: externo (servidor OU pessoa não cadastrada) apaga a marca de motorista
    da equipe; sem externo, os campos dele ficam vazios. Devolve se a equipe mudou."""
    modo = atual.motorista_externo
    if modo != Oficio.MotoristaExterno.SERVIDOR:
        atual.motorista_externo_servidor = None
    if modo != Oficio.MotoristaExterno.MANUAL:
        for campo in CAMPOS_MOTORISTA_MANUAL:
            setattr(atual, campo, "")
    if not modo:
        atual.motorista_oficio_origem = atual.motorista_protocolo_origem = ""
        return False
    return bool(atual.viajantes.filter(motorista=True).update(motorista=False))


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
                  *, versao: int | None = None, registrar: bool = True) -> Oficio:
    """Dados + roteiro do formulário numa só transação: ou grava tudo, ou nada.

    `registrar=False` grava sem escrever no histórico — é o autosave, que salvaria uma
    linha a cada pausa na digitação e transformaria a história do ofício em ruído. A
    auditoria do banco (trigger) continua registrando cada alteração.
    """
    atual = _travar_para_edicao(oficio, usuario, versao)
    _aplicar_dados(atual, usuario, dados, registrar=registrar)
    if trechos is not None:
        _aplicar_trechos(atual, trechos, tocar=False)  # a versão já subiu com os dados
        recalcular_diarias(atual)
    return atual


def _aplicar_dados(atual: Oficio, usuario, dados: dict, *, registrar: bool = True) -> None:
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
    if "protocolo" in alterados:
        # Quem digita o número assume a origem (apaga marca de simulado/treinamento).
        atual.protocolo_origem = Oficio.OrigemProtocolo.MANUAL if atual.protocolo else ""
    if atual.tipo_transporte == Oficio.TipoTransporte.VIATURA:
        atual.transporte_descricao = atual.transporte_placa = ""
        atual.transporte_combustivel = None
    else:
        atual.viatura = None
    if atual.custeio != Oficio.Custeio.OUTRA_INSTITUICAO:
        atual.custeio_instituicao = ""
    _normalizar_motorista_externo(atual)
    atual.versao += 1
    atual.save()
    # Diárias dependem só de trechos, equipe e sede: nada aqui muda o cálculo.
    if alterados and registrar:
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
        if atual.motorista_externo:  # motorista da equipe substitui o de fora
            atual.motorista_externo = Oficio.MotoristaExterno.NENHUM
            _normalizar_motorista_externo(atual)
            atual.save(update_fields=["motorista_externo", "motorista_externo_servidor",
                                      *CAMPOS_MOTORISTA_MANUAL, "motorista_oficio_origem",
                                      "motorista_protocolo_origem"])
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
    def avisos(self) -> list[Pendencia]:
        """O que não impede a emissão mas merece ser visto antes (ex.: conflito de agenda)."""
        return [p for p in self.pendencias if not p.bloqueia]

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
        if (viajantes and not any(v.motorista for v in viajantes)
                and not oficio.motorista_externo):
            p.append(Pendencia("equipe", "Indique quem da equipe é o motorista da viatura."))
    elif not oficio.transporte_descricao.strip():
        p.append(Pendencia("transporte", "Descreva o meio de transporte."))
    p.extend(pendencias_do_motorista_externo(oficio, viajantes))
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


def pendencias_do_motorista_externo(oficio: Oficio, viajantes) -> list[Pendencia]:
    """Paridade com pendencias_motorista_documento da referência: pessoa não cadastrada
    precisa do nome; servidor de fora, de ser escolhido (e não pode já estar na equipe);
    os dois precisam do ofício de origem (N/AAAA) e do protocolo de 9 dígitos."""
    modo = oficio.motorista_externo
    if not modo:
        return []
    p: list[Pendencia] = []
    if modo == Oficio.MotoristaExterno.MANUAL and not oficio.motorista_externo_nome.strip():
        return [Pendencia("transporte", "Informe o nome do motorista.")]
    if modo == Oficio.MotoristaExterno.SERVIDOR:
        if not oficio.motorista_externo_servidor_id:
            return [Pendencia("transporte", "Escolha o servidor que vai dirigir.")]
        if any(v.servidor_id == oficio.motorista_externo_servidor_id for v in viajantes):
            return [Pendencia("transporte", "O motorista escolhido já está na equipe: marque-o "
                                            "como motorista nela.")]
    if not OFICIO_DE_ORIGEM.match(oficio.motorista_oficio_origem or ""):
        p.append(Pendencia("transporte",
                           "Informe o ofício do motorista no formato número/ano."))
    if len(somente_digitos(oficio.motorista_protocolo_origem)) != 9:
        p.append(Pendencia("transporte", "Informe o protocolo do motorista com 9 dígitos."))
    return p


def nome_do_motorista(oficio: Oficio, viajantes=None) -> str:
    """O nome que vai no documento: o da equipe, ou o de fora (servidor ou não cadastrado)."""
    if oficio.motorista_externo == Oficio.MotoristaExterno.SERVIDOR:
        return oficio.motorista_externo_servidor.nome if oficio.motorista_externo_servidor else ""
    if oficio.motorista_externo == Oficio.MotoristaExterno.MANUAL:
        return oficio.motorista_externo_nome.strip()
    equipe = viajantes if viajantes is not None else viajantes_de(oficio)
    return next((v.servidor.nome for v in equipe if v.motorista), "")


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


# ---------------------------------------------------------------- texto dos documentos (ADR 0018)
TIPOS_DE_DOCUMENTO = {t.value for t in Documento.Tipo}
# Salvamentos seguidos da mesma pessoa, em poucos minutos, atualizam a mesma versão: o
# histórico fica legível (uma linha por sessão de escrita, não por tecla), e a trilha do
# banco continua guardando cada UPDATE.
JANELA_DE_COALESCENCIA = timedelta(minutes=10)
TEXTOS_PRONTOS_POR_DOCUMENTO = {
    "oficio": [ModeloTexto.Tipo.OFICIO, ModeloTexto.Tipo.MOTIVO],
    "justificativa": [ModeloTexto.Tipo.JUSTIFICATIVA],
}


def _tipo_de_documento(tipo: str) -> str:
    if tipo not in TIPOS_DE_DOCUMENTO:
        raise RegraViolada(f"Documento desconhecido: {tipo}.")
    return tipo


def edicao_vigente(oficio: Oficio, tipo: str) -> EdicaoDocumento | None:
    return (EdicaoDocumento.objects.filter(oficio=oficio, tipo=tipo).select_related("criado_por")
            .order_by("-numero").first())


def regioes_vigentes(oficio: Oficio, tipo: str) -> dict[str, str]:
    edicao = edicao_vigente(oficio, tipo)
    return dict(edicao.regioes) if edicao is not None else {}


def _descrever_texto(tipo: str, edicao: EdicaoDocumento) -> str:
    nome = Documento.Tipo(tipo).label
    if edicao.acao == EdicaoDocumento.Acao.MODELO:
        return f"Texto d{'o' if tipo == 'oficio' else 'a'} {nome.lower()} voltou ao modelo."
    if edicao.acao == EdicaoDocumento.Acao.RESTAURADO and edicao.restaurada_de is not None:
        return f"Texto d{'o' if tipo == 'oficio' else 'a'} {nome.lower()}: versão " \
               f"{edicao.restaurada_de.numero} restaurada (agora v{edicao.numero})."
    blocos = edicao.blocos_alterados
    partes = ", ".join(b["rotulo"] for b in blocos[:4])
    extra = f" e mais {len(blocos) - 4}" if len(blocos) > 4 else ""
    return (f"Texto d{'o' if tipo == 'oficio' else 'a'} {nome.lower()} editado "
            f"(v{edicao.numero}): {partes}{extra}.")[:300]


@transaction.atomic
def salvar_texto_do_documento(oficio: Oficio, usuario, tipo: str, regioes: dict[str, str], *,
                              versao_base: int | None = None) -> EdicaoDocumento:
    """Grava o texto das regiões editadas como uma versão nova (ou atualiza a recém-criada).

    Região igual ao modelo não é guardada; se nenhuma diferir, a versão é "do modelo".
    `versao_base` é o número que o editor tinha ao começar: diferente do vigente, alguém
    salvou antes — conflito, como no formulário.
    """
    from .documentos.dados import dados_do_oficio
    from .documentos.pdf import regioes_do_modelo

    atual = _travar_para_edicao(oficio, usuario, None)
    policies.exigir(policies.pode_editar_texto(usuario, atual))
    tipo = _tipo_de_documento(tipo)
    vigente = edicao_vigente(atual, tipo)
    numero_vigente = vigente.numero if vigente else 0
    if versao_base is not None and versao_base != numero_vigente:
        raise ConflitoDeEdicao(
            "Outra pessoa alterou o texto deste documento enquanto você editava. Recarregue "
            "a folha para ver a versão atual antes de salvar de novo.")
    originais = regioes_do_modelo(tipo, dados_do_oficio(atual))
    limpas: dict[str, str] = {}
    alterados: list[dict[str, str]] = []
    impressoes: dict[str, str] = {}
    for chave, original in originais.items():
        if chave not in regioes:
            if vigente is not None and chave in vigente.regioes:  # região não enviada: mantém
                limpas[chave] = vigente.regioes[chave]
                alterados += blocos_alterados(original, limpas[chave])
                impressoes[chave] = vigente.impressoes.get(chave, impressao(original))
            continue
        html = sanear_html(regioes[chave])
        faltando = campos_presentes(original) - campos_presentes(html)
        if faltando:
            rotulos = ", ".join(CAMPOS[c].rotulo for c in sorted(faltando))
            raise RegraViolada(f"O trecho «{rotulos}» vem do cadastro e não pode ser removido "
                               "do texto. Desfaça a alteração ou volte ao modelo.")
        # Compara os dois lados saneados: o navegador e o saneador reescrevem entidades e
        # espaços; só diferença de conteúdo conta.
        if normalizar(html) == normalizar(sanear_html(original)):
            continue
        limpas[chave] = html
        alterados += blocos_alterados(original, html)
        impressoes[chave] = impressao(original)
    acao = EdicaoDocumento.Acao.EDITADO if limpas else EdicaoDocumento.Acao.MODELO
    if vigente is not None and vigente.regioes == limpas:
        return vigente  # nada mudou
    if vigente is None and not limpas:
        raise RegraViolada("O texto está igual ao modelo: não há o que salvar.")
    coalesce = (vigente is not None and vigente.acao == EdicaoDocumento.Acao.EDITADO
                and acao == EdicaoDocumento.Acao.EDITADO
                and vigente.criado_por_id == getattr(usuario, "pk", None)
                and timezone.now() - vigente.criado_em < JANELA_DE_COALESCENCIA)
    if coalesce and vigente is not None:
        vigente.regioes, vigente.blocos_alterados = limpas, alterados
        vigente.impressoes = impressoes
        vigente.save(update_fields=["regioes", "blocos_alterados", "impressoes"])
        return vigente
    edicao = EdicaoDocumento.objects.create(
        oficio=atual, tipo=tipo, numero=numero_vigente + 1, acao=acao, regioes=limpas,
        blocos_alterados=alterados, impressoes=impressoes, criado_por=usuario)
    _registrar(atual, Historico.Acao.TEXTO, _descrever_texto(tipo, edicao), usuario,
               tipo=tipo, versao=edicao.numero)
    return edicao


@transaction.atomic
def restaurar_texto_do_documento(oficio: Oficio, usuario, tipo: str,
                                 numero: int) -> EdicaoDocumento:
    """Volta a um texto anterior criando uma versão nova (o histórico nunca perde nada)."""
    atual = _travar_para_edicao(oficio, usuario, None)
    policies.exigir(policies.pode_editar_texto(usuario, atual))
    tipo = _tipo_de_documento(tipo)
    try:
        origem = EdicaoDocumento.objects.get(oficio=atual, tipo=tipo, numero=numero)
    except EdicaoDocumento.DoesNotExist:
        raise RegraViolada(f"Não existe a versão {numero} do texto.") from None
    vigente = edicao_vigente(atual, tipo)
    if vigente is not None and vigente.pk == origem.pk:
        return vigente
    edicao = EdicaoDocumento.objects.create(
        oficio=atual, tipo=tipo, numero=(vigente.numero if vigente else 0) + 1,
        acao=EdicaoDocumento.Acao.RESTAURADO, regioes=dict(origem.regioes),
        blocos_alterados=list(origem.blocos_alterados), impressoes=dict(origem.impressoes),
        restaurada_de=origem, criado_por=usuario)
    _registrar(atual, Historico.Acao.TEXTO, _descrever_texto(tipo, edicao), usuario,
               tipo=tipo, versao=edicao.numero, restaurada_de=origem.numero)
    return edicao


@transaction.atomic
def voltar_texto_ao_modelo(oficio: Oficio, usuario, tipo: str) -> EdicaoDocumento | None:
    """Descarta o texto editado: o documento volta a sair como o modelo gera."""
    atual = _travar_para_edicao(oficio, usuario, None)
    policies.exigir(policies.pode_editar_texto(usuario, atual))
    tipo = _tipo_de_documento(tipo)
    vigente = edicao_vigente(atual, tipo)
    if vigente is None or vigente.do_modelo:
        return vigente
    edicao = EdicaoDocumento.objects.create(
        oficio=atual, tipo=tipo, numero=vigente.numero + 1, acao=EdicaoDocumento.Acao.MODELO,
        criado_por=usuario)
    _registrar(atual, Historico.Acao.TEXTO, _descrever_texto(tipo, edicao), usuario,
               tipo=tipo, versao=edicao.numero)
    return edicao


def _validar_campo_vinculado(campo: CampoVinculado, valor: str) -> str:
    valor = (valor or "").replace("\r\n", "\n").strip()
    if not campo.multilinha:
        valor = " ".join(valor.split())
    if campo.chave == "protocolo":
        valor = somente_digitos(valor)
        if valor and len(valor) != 9:
            raise RegraViolada(f"O protocolo tem 9 dígitos; você informou {len(valor)}.")
    if len(valor) > campo.maximo:
        raise RegraViolada(f"{campo.rotulo}: no máximo {campo.maximo} caracteres.")
    return valor


@transaction.atomic
def salvar_campo_do_documento(oficio: Oficio, usuario, chave: str, valor: str, *,
                              versao: int | None = None) -> Oficio:
    """Escreve um campo vinculado de dentro do documento (mesma concorrência do formulário)."""
    if chave not in CAMPOS:
        raise RegraViolada(f"Campo desconhecido: {chave}.")
    campo = CAMPOS[chave]
    atual = _travar_para_edicao(oficio, usuario, versao)
    policies.exigir(policies.pode_editar_texto(usuario, atual))
    novo = _validar_campo_vinculado(campo, valor)
    if getattr(atual, campo.atributo) == novo:
        return atual
    setattr(atual, campo.atributo, novo)
    atual.versao += 1
    gravar = [campo.atributo, "versao", "atualizado_em"]
    if campo.atributo == "protocolo":  # digitado no documento também é manual
        atual.protocolo_origem = Oficio.OrigemProtocolo.MANUAL if novo else ""
        gravar.append("protocolo_origem")
    atual.save(update_fields=gravar)
    _registrar(atual, Historico.Acao.ALTERADO, f"{campo.rotulo} alterado pelo texto do documento.",
               usuario, campos=[campo.atributo])
    return atual


def textos_prontos(tipo: str) -> list[ModeloTexto]:
    tipos = TEXTOS_PRONTOS_POR_DOCUMENTO.get(tipo, [])
    return list(ModeloTexto.objects.filter(ativo=True, tipo__in=tipos).order_by("tipo", "ordem",
                                                                               "nome"))


def criar_texto_pronto(usuario, tipo: str, nome: str, texto: str) -> ModeloTexto:
    """"Guardar como texto pronto" do editor de documento: o mesmo catálogo da folha."""
    tipo = _tipo_de_documento(tipo)
    if not " ".join((nome or "").split()) or not (texto or "").strip():
        raise RegraViolada("Dê um nome ao texto pronto e selecione o trecho a guardar.")
    tipo_modelo = (ModeloTexto.Tipo.OFICIO if tipo == "oficio" else ModeloTexto.Tipo.JUSTIFICATIVA)
    try:
        return textos.salvar(usuario, tipo=tipo_modelo, nome=nome, texto=texto)
    except textos.TextoInvalido as exc:
        raise RegraViolada(str(exc)) from None


def desativar_texto_pronto(usuario, pk: int) -> ModeloTexto:
    try:
        return textos.desativar(usuario, pk)
    except ModeloTexto.DoesNotExist:
        raise RegraViolada("Texto pronto não encontrado.") from None
    except textos.TextoInvalido as exc:
        raise RegraViolada(str(exc)) from None


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
        dados = dados_do_oficio(atual)
        edicao = edicao_vigente(atual, tipo)
        if edicao is not None and not edicao.do_modelo:
            # O PDF arquivado sai do instantâneo, texto editado incluído (ADR 0018).
            dados["edicao"] = {"numero": edicao.numero, "regioes": edicao.regioes,
                               "blocos_alterados": edicao.blocos_alterados}
        doc = Documento.objects.create(oficio=atual, tipo=tipo, versao=ultima + 1,
                                       dados=dados, emitido_por=usuario, edicao=edicao)
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
def retificar(oficio: Oficio, usuario) -> Oficio:
    """Abre para correção um ofício já emitido: ele volta a rascunho marcado como
    RETIFICADO e ganha uma versão nova. O PDF emitido continua guardado; ao emitir de novo
    sai a versão 2, que é o que a retificação significa no papel."""
    atual = (Oficio.objects.select_for_update(of=("self",))
             .select_related("sede", "viatura").get(pk=oficio.pk))
    policies.exigir(policies.pode_retificar(usuario, atual),
                    "Você não pode editar este ofício.")
    atual.situacao = Oficio.Situacao.RASCUNHO
    atual.emitido_em = None
    atual.marcador = Oficio.Marcador.RETIFICADO
    atual.versao += 1
    atual.save(update_fields=["situacao", "emitido_em", "marcador", "versao", "atualizado_em"])
    _registrar(atual, Historico.Acao.REABERTO,
               "Aberto para retificação: o ofício volta a rascunho como retificado.", usuario)
    return atual


@transaction.atomic
def cancelar(oficio: Oficio, usuario, motivo: str) -> Oficio:
    atual = (Oficio.objects.select_for_update(of=("self",))
             .select_related("sede", "viatura").get(pk=oficio.pk))
    policies.exigir(policies.pode_cancelar(usuario, atual), "Você não pode cancelar este ofício.")
    if not motivo.strip():
        raise RegraViolada("Informe o motivo do cancelamento.")
    anterior = atual.situacao
    atual.situacao = Oficio.Situacao.CANCELADO
    atual.situacao_anterior = anterior
    atual.cancelado_em = timezone.now()
    atual.motivo_cancelamento = motivo.strip()
    atual.versao += 1
    atual.save(update_fields=["situacao", "situacao_anterior", "cancelado_em",
                              "motivo_cancelamento", "versao", "atualizado_em"])
    _registrar(atual, Historico.Acao.CANCELADO, f"Cancelado: {motivo.strip()}", usuario,
               de=anterior, para=Oficio.Situacao.CANCELADO, motivo=motivo.strip())
    return atual


@transaction.atomic
def reativar(oficio: Oficio, usuario, justificativa: str) -> Oficio:
    """D2: o cancelado volta à situação que tinha (rascunho ou emitido). O número continua o
    mesmo (cancelado já o ocupava), nada é emitido de novo e o cancelamento continua no
    histórico — a reativação registra quem, quando, por quê, de onde e para onde."""
    atual = (Oficio.objects.select_for_update(of=("self",))
             .select_related("sede", "viatura").get(pk=oficio.pk))
    policies.exigir(policies.pode_reativar(usuario, atual),
                    "Só o gestor de viagens reativa um ofício cancelado.")
    justificativa = (justificativa or "").strip()
    if not justificativa:
        raise RegraViolada("Informe a justificativa da reativação.")
    para = atual.situacao_anterior or Oficio.Situacao.RASCUNHO
    cancelamento = {"motivo": atual.motivo_cancelamento,
                    "em": atual.cancelado_em.isoformat() if atual.cancelado_em else None}
    atual.situacao = para
    atual.situacao_anterior = ""
    atual.cancelado_em = None
    atual.motivo_cancelamento = ""
    atual.versao += 1
    atual.save(update_fields=["situacao", "situacao_anterior", "cancelado_em",
                              "motivo_cancelamento", "versao", "atualizado_em"])
    _registrar(atual, Historico.Acao.REATIVADO,
               f"Reativado ({Oficio.Situacao(para).label.lower()}): {justificativa}"[:300],
               usuario, de=Oficio.Situacao.CANCELADO, para=para,
               justificativa=justificativa, cancelamento=cancelamento)
    return atual


@transaction.atomic
def arquivar(oficio: Oficio, usuario) -> Oficio:
    """D1: tira o ofício das abas de trabalho; não apaga nada e não muda a situação."""
    atual = Oficio.objects.select_for_update(of=("self",)).get(pk=oficio.pk)
    policies.exigir(policies.pode_arquivar(usuario, atual), "Você não pode arquivar este ofício.")
    atual.arquivado_em, atual.arquivado_por = timezone.now(), usuario
    atual.save(update_fields=["arquivado_em", "arquivado_por", "atualizado_em"])
    _registrar(atual, Historico.Acao.ARQUIVADO, "Arquivado.", usuario,
               situacao=atual.situacao)
    return atual


@transaction.atomic
def desarquivar(oficio: Oficio, usuario) -> Oficio:
    atual = Oficio.objects.select_for_update(of=("self",)).get(pk=oficio.pk)
    policies.exigir(policies.pode_desarquivar(usuario, atual),
                    "Você não pode desarquivar este ofício.")
    atual.arquivado_em, atual.arquivado_por = None, None
    atual.save(update_fields=["arquivado_em", "arquivado_por", "atualizado_em"])
    _registrar(atual, Historico.Acao.DESARQUIVADO, "Desarquivado.", usuario,
               situacao=atual.situacao)
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


def buscar_por_texto(qs, termo: str, escopo: str = ""):
    """Busca por número (131 ou 131/2026), protocolo, motivo, destino ou servidor.

    Com `escopo`, procura só onde foi pedido (dominio.busca): é o que tira da frente as
    dezenas de ofícios que casam com "26" por acaso."""
    termo = (termo or "").strip()
    if not termo:
        return qs
    if escopo:
        escolhida = next(
            (leitura for leitura in dominio_busca.ler(termo, timezone.localdate().year)
             if leitura.escopo == escopo), None)
        if escolhida:
            return aplicar_leitura(qs, escolhida)
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
