"""Modelos do módulo Viagens: o Ofício de viagem e o que gira em torno dele.

Invariantes garantidos pelo banco (constraints), não só pela aplicação:
- número único por ano; ofício emitido sempre tem número;
- no máximo um motorista por ofício; um servidor aparece uma vez por ofício;
- trecho chega depois de sair; valores de diária não negativos;
- versão de documento única por ofício e tipo.
Toda tabela é auditada por trigger (migração 0002).
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q

from gestao.cadastros.models import (
    AtividadePlano,
    Cargo,
    Combustivel,
    ModeloTexto,
    Municipio,
    ProgramaSolicitante,
    Servidor,
    Unidade,
    Viatura,
)

from .dominio.numeracao import formatar_numero


class Viagem(models.Model):
    """O agrupador de uma ação: roteiro, ofícios (com justificativa e termos), OS e plano
    (paridade com `viagens_viagem` da referência). Sem numeração própria: o título nasce
    dos tipos. "Em execução" e "finalizada" não se gravam — saem das datas e da prestação."""

    class Situacao(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        PREPARACAO = "preparacao", "Em preparação"
        GERADOS = "gerados", "Documentos gerados"
        CANCELADA = "cancelada", "Cancelada"

    unidade = models.ForeignKey(Unidade, on_delete=models.PROTECT, related_name="viagens")
    titulo = models.CharField("título", max_length=255, blank=True)
    descricao = models.TextField("descrição/objetivo", blank=True)
    motivo = models.TextField("motivo", blank=True)
    tipos = models.ManyToManyField("cadastros.TipoViagem", blank=True, related_name="viagens")
    data_inicio = models.DateField("início", null=True, blank=True)
    data_fim = models.DateField("fim", null=True, blank=True)
    situacao = models.CharField(max_length=12, choices=Situacao.choices,
                                default=Situacao.RASCUNHO)
    situacao_anterior = models.CharField(max_length=12, choices=Situacao.choices, blank=True)
    motivo_cancelamento = models.CharField("motivo do cancelamento", max_length=1000,
                                           blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(data_fim__isnull=True) | Q(data_inicio__isnull=True)
                | Q(data_fim__gte=models.F("data_inicio")),
                name="viagem_periodo_ordenado"),
        ]

    def __str__(self) -> str:
        return self.titulo or f"Viagem #{self.pk}"

    @property
    def cancelada(self) -> bool:
        return self.situacao == self.Situacao.CANCELADA


class ViagemDestino(models.Model):
    """Destinos da viagem na ordem da visita (o primeiro é o principal)."""

    viagem = models.ForeignKey(Viagem, on_delete=models.CASCADE, related_name="destinos")
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name="+")
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordem"]
        constraints = [models.UniqueConstraint(fields=["viagem", "ordem"],
                                               name="viagem_destino_ordem_unica")]

    def __str__(self) -> str:
        return str(self.municipio)


class Oficio(models.Model):
    class Situacao(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        EMITIDO = "emitido", "Emitido"
        CANCELADO = "cancelado", "Cancelado"

    class Custeio(models.TextChoices):
        UNIDADE = "unidade", "Unidade (diárias e combustível custeados pela unidade)"
        OUTRA_INSTITUICAO = "outra_instituicao", "Outra instituição"
        ONUS_LIMITADO = "onus_limitado", "Ônus limitados aos próprios vencimentos"

    class TipoTransporte(models.TextChoices):
        VIATURA = "viatura", "Viatura oficial"
        OUTRO = "outro", "Outro meio (informar)"

    class Marcador(models.TextChoices):
        NENHUM = "", "Nenhum (documento original)"
        RETIFICADO = "retificado", "Retificado (corrige ofício anterior à viagem)"
        COMPLEMENTAR = "complementar", "Complementar (acrescenta ao ofício já enviado)"

    unidade = models.ForeignKey(Unidade, on_delete=models.PROTECT, related_name="oficios",
                                verbose_name="unidade emissora")
    # Viagem que agrupa o documento (módulo 8); excluir a viagem não apaga documento.
    viagem = models.ForeignKey(Viagem, on_delete=models.PROTECT, null=True, blank=True,
                               related_name="oficios")
    ano = models.PositiveSmallIntegerField("ano")
    numero = models.PositiveIntegerField("número")
    data_oficio = models.DateField("data do ofício")
    protocolo = models.CharField(
        "protocolo (eProtocolo)", max_length=9, blank=True,
        help_text="Nove dígitos, com ou sem pontuação (ex.: 12.345.678-9).",
    )

    class OrigemProtocolo(models.TextChoices):
        """De onde veio o número (docs/integrations/eprotocolo.md). Só MANUAL e EPROTOCOLO
        valem como protocolo oficial; treinamento e simulado nunca."""

        MANUAL = "manual", "Digitado"
        EPROTOCOLO = "eprotocolo", "Aberto no eProtocolo"
        TREINAMENTO = "treinamento", "eProtocolo de treinamento (não oficial)"
        SIMULADO = "simulado", "Simulado (não oficial)"

    protocolo_origem = models.CharField("origem do protocolo", max_length=12, blank=True,
                                        choices=OrigemProtocolo.choices)
    # O assunto do documento é calculado (Autorização × Convalidação), nunca texto livre:
    # ver viagens.dominio.assunto. O marcador ajusta o rótulo.
    marcador = models.CharField("marcador do documento", max_length=15, blank=True,
                                choices=Marcador.choices, default=Marcador.NENHUM)
    motivo = models.TextField("motivo da viagem", blank=True)
    # Modo bate-volta: o itinerário vem dos blocos (bate_voltas), não da lista de destinos.
    # O campo distingue "modo desligado" de "ligado e ainda vazio", estado que precisa
    # sobreviver a um salvamento recusado na validação.
    bate_volta = models.BooleanField("bate-volta", default=False)
    custeio = models.CharField("custeio", max_length=20, choices=Custeio.choices,
                               default=Custeio.UNIDADE)
    custeio_instituicao = models.CharField("instituição que custeia", max_length=160,
                                           blank=True)

    tipo_transporte = models.CharField("meio de transporte", max_length=10,
                                       choices=TipoTransporte.choices,
                                       default=TipoTransporte.VIATURA)
    viatura = models.ForeignKey(Viatura, on_delete=models.PROTECT, null=True, blank=True,
                                related_name="oficios")
    transporte_descricao = models.CharField("descrição do transporte", max_length=120,
                                            blank=True)
    transporte_placa = models.CharField("placa", max_length=7, blank=True)
    transporte_combustivel = models.ForeignKey(Combustivel, on_delete=models.PROTECT,
                                               null=True, blank=True)
    porte_arma = models.BooleanField("porte/trânsito de arma", default=True)

    sede = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name="+",
                             verbose_name="cidade sede")

    justificativa_modelo = models.ForeignKey(
        ModeloTexto, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        limit_choices_to={"tipo": ModeloTexto.Tipo.JUSTIFICATIVA},
    )
    justificativa = models.TextField("justificativa", blank=True)
    # Roteiro cadastrado que serviu de modelo (os trechos são copiados para o ofício; mudar o
    # roteiro depois não altera o ofício).
    roteiro = models.ForeignKey("Roteiro", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="oficios", verbose_name="roteiro de origem")

    # Instantâneo do cálculo (refeito a cada alteração de trechos/viajantes).
    diarias_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal(0))
    diarias_resumo = models.CharField(max_length=120, blank=True)
    diarias_calculo = models.JSONField(default=dict, blank=True)
    diarias_erro = models.CharField(max_length=300, blank=True)

    situacao = models.CharField(max_length=10, choices=Situacao.choices,
                                default=Situacao.RASCUNHO)
    versao = models.PositiveIntegerField(default=1)  # concorrência otimista
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    emitido_em = models.DateTimeField(null=True, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    motivo_cancelamento = models.TextField(blank=True)
    # Motorista de fora da equipe (D3; paridade com motorista_modo/manual da referência).
    # Ele viaja por outro ofício: não entra nas diárias deste, e o documento cita o nome.
    class MotoristaExterno(models.TextChoices):
        NENHUM = "", "Da equipe"
        SERVIDOR = "servidor", "Servidor de outro ofício"
        MANUAL = "manual", "Pessoa não cadastrada"

    motorista_externo = models.CharField("motorista de fora da equipe", max_length=10,
                                         blank=True, choices=MotoristaExterno.choices)
    motorista_externo_servidor = models.ForeignKey(
        Servidor, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        verbose_name="servidor motorista")
    motorista_externo_nome = models.CharField("nome do motorista", max_length=255, blank=True)
    motorista_externo_rg = models.CharField("RG do motorista", max_length=30, blank=True)
    motorista_externo_cpf = models.CharField("CPF do motorista", max_length=11, blank=True)
    motorista_externo_cargo = models.CharField("cargo do motorista", max_length=120, blank=True)
    motorista_externo_unidade = models.CharField("unidade do motorista", max_length=255,
                                                 blank=True)
    motorista_externo_observacao = models.TextField("observação sobre o motorista", blank=True)
    motorista_oficio_origem = models.CharField("ofício do motorista", max_length=12,
                                               blank=True)
    motorista_protocolo_origem = models.CharField("protocolo do motorista", max_length=9,
                                                  blank=True)
    # Situação de antes do cancelamento: reativar volta para ela (D2). Vazio fora do cancelado.
    situacao_anterior = models.CharField("situação antes do cancelamento", max_length=10,
                                         blank=True)
    # Arquivar (D1) é uma marca, não uma situação: tira o ofício das abas de trabalho sem
    # apagar nada; desarquivar devolve. Arquivado não se edita nem se emite.
    arquivado_em = models.DateTimeField("arquivado em", null=True, blank=True)
    arquivado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                      null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["-ano", "-numero"]
        verbose_name = "ofício"
        verbose_name_plural = "ofícios"
        permissions = [
            ("emitir_oficio", "Pode emitir ofícios"),
            ("cancelar_oficio", "Pode cancelar ofícios"),
            ("reabrir_oficio", "Pode reabrir ofícios emitidos"),
            ("reativar_oficio", "Pode reativar ofícios cancelados (com justificativa)"),
            ("arquivar_oficio", "Pode arquivar e desarquivar ofícios"),
            ("ver_todas_unidades", "Vê ofícios de todas as unidades"),
            ("gerir_numeracao", "Pode configurar a numeração anual"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["ano", "numero"], name="oficio_numero_unico_ano"),
            models.CheckConstraint(condition=Q(numero__gt=0), name="oficio_numero_positivo"),
            models.CheckConstraint(condition=Q(diarias_total__gte=0),
                                   name="oficio_diarias_nao_negativas"),
            models.CheckConstraint(
                condition=Q(protocolo="") | Q(protocolo__regex=r"^\d{9}$"),
                name="oficio_protocolo_9_digitos",
            ),
            models.CheckConstraint(
                condition=~Q(situacao="emitido") | Q(emitido_em__isnull=False),
                name="oficio_emitido_tem_data",
            ),
            models.CheckConstraint(
                condition=~Q(situacao="cancelado") | ~Q(motivo_cancelamento=""),
                name="oficio_cancelado_tem_motivo",
            ),
        ]
        indexes = [
            models.Index(fields=["situacao", "-ano", "-numero"], name="oficio_situacao_idx"),
            models.Index(fields=["unidade", "-ano", "-numero"], name="oficio_unidade_idx"),
            models.Index(fields=["protocolo"], name="oficio_protocolo_idx"),
        ]

    def __str__(self) -> str:
        return f"Ofício {self.numero_formatado}"

    @property
    def descricao(self) -> str:
        """Segunda linha nas escolhas de ofício (ex.: ofícios ligados a uma OS)."""
        return self.get_situacao_display()

    @property
    def numero_formatado(self) -> str:
        return formatar_numero(self.numero, self.ano)

    @property
    def protocolo_formatado(self) -> str:
        p = self.protocolo
        if len(p) != 9:
            return p
        return f"{p[:2]}.{p[2:5]}.{p[5:8]}-{p[8]}"

    @property
    def editavel(self) -> bool:
        return self.situacao == self.Situacao.RASCUNHO and self.arquivado_em is None

    @property
    def arquivado(self) -> bool:
        return self.arquivado_em is not None


class Viajante(models.Model):
    oficio = models.ForeignKey(Oficio, on_delete=models.CASCADE, related_name="viajantes")
    servidor = models.ForeignKey(Servidor, on_delete=models.PROTECT, related_name="viagens")
    motorista = models.BooleanField("motorista", default=False)
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "id"]
        # Como aparece quando um cadastro não pode ser excluído ("ligado a 3 participações…").
        verbose_name = "participação em ofício"
        verbose_name_plural = "participações em ofícios"
        constraints = [
            models.UniqueConstraint(fields=["oficio", "servidor"], name="viajante_unico"),
            models.UniqueConstraint(fields=["oficio"], condition=Q(motorista=True),
                                    name="um_motorista_por_oficio"),
        ]

    def __str__(self) -> str:
        return f"{self.servidor} ({'motorista' if self.motorista else 'viajante'})"


class Trecho(models.Model):
    """Deslocamento: origem → destino, com saída e chegada (horário local)."""

    oficio = models.ForeignKey(Oficio, on_delete=models.CASCADE, related_name="trechos")
    ordem = models.PositiveSmallIntegerField()
    origem = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name="+")
    destino = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name="+")
    saida_em = models.DateTimeField("saída")
    chegada_em = models.DateTimeField("chegada")
    # Itinerário 2.0 (ADR 0016): a chegada é saída + tempo de estrada + tempo adicional.
    distancia_km = models.DecimalField("distância (km)", max_digits=8, decimal_places=1,
                                       null=True, blank=True)
    tempo_viagem_min = models.PositiveIntegerField("tempo de estrada (min)", null=True,
                                                   blank=True)
    tempo_adicional_min = models.PositiveIntegerField("tempo adicional (min)", default=0)

    class Meta:
        ordering = ["ordem"]
        constraints = [
            models.UniqueConstraint(fields=["oficio", "ordem"], name="trecho_ordem_unica"),
            models.CheckConstraint(condition=Q(chegada_em__gt=models.F("saida_em")),
                                   name="trecho_chega_depois_de_sair"),
            models.CheckConstraint(condition=~Q(origem=models.F("destino")),
                                   name="trecho_origem_diferente_destino"),
        ]

    def __str__(self) -> str:
        return f"{self.origem} → {self.destino}"


class Roteiro(models.Model):
    """Roteiro reutilizável (como no sistema de referência): saída da sede, destinos, volta
    e diárias estimadas para um efetivo. Serve de modelo para ofícios."""

    class Situacao(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        CANCELADO = "cancelado", "Cancelado"

    unidade = models.ForeignKey(Unidade, on_delete=models.PROTECT, related_name="roteiros")
    # Viagem que agrupa o documento (módulo 8); excluir a viagem não apaga documento.
    viagem = models.ForeignKey(Viagem, on_delete=models.PROTECT, null=True, blank=True,
                               related_name="roteiros")
    sede = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name="+",
                             verbose_name="sede (origem da viagem)")
    quantidade_servidores = models.PositiveSmallIntegerField(
        "quantidade de servidores", default=1,
        help_text="Efetivo usado para estimar as diárias do roteiro.")
    observacoes = models.TextField("observações", blank=True)
    # Modo bate-volta: o itinerário vem dos blocos (bate_voltas), não da lista de destinos.
    # O campo distingue "modo desligado" de "ligado e ainda vazio", estado que precisa
    # sobreviver a um salvamento recusado na validação.
    bate_volta = models.BooleanField("bate-volta", default=False)
    situacao = models.CharField(max_length=10, choices=Situacao.choices, default=Situacao.ATIVO)
    diarias_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal(0))
    diarias_resumo = models.CharField(max_length=120, blank=True)
    diarias_calculo = models.JSONField(default=dict, blank=True)
    diarias_erro = models.CharField(max_length=300, blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "roteiro"
        verbose_name_plural = "roteiros"
        constraints = [
            models.CheckConstraint(condition=Q(quantidade_servidores__gte=1),
                                   name="roteiro_ao_menos_um_servidor"),
            models.CheckConstraint(condition=Q(diarias_total__gte=0),
                                   name="roteiro_diarias_nao_negativas"),
        ]
        indexes = [models.Index(fields=["unidade", "situacao"], name="roteiro_unidade_idx")]

    def __str__(self) -> str:
        return f"Roteiro #{self.pk}"

    @property
    def editavel(self) -> bool:
        return self.situacao == self.Situacao.ATIVO


class TrechoRoteiro(models.Model):
    """Trecho de um roteiro (mesmas regras do trecho do ofício)."""

    roteiro = models.ForeignKey(Roteiro, on_delete=models.CASCADE, related_name="trechos")
    ordem = models.PositiveSmallIntegerField()
    origem = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name="+")
    destino = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name="+")
    saida_em = models.DateTimeField("saída")
    chegada_em = models.DateTimeField("chegada")
    # Itinerário 2.0 (ADR 0016): a chegada é saída + tempo de estrada + tempo adicional.
    distancia_km = models.DecimalField("distância (km)", max_digits=8, decimal_places=1,
                                       null=True, blank=True)
    tempo_viagem_min = models.PositiveIntegerField("tempo de estrada (min)", null=True,
                                                   blank=True)
    tempo_adicional_min = models.PositiveIntegerField("tempo adicional (min)", default=0)

    class Meta:
        ordering = ["ordem"]
        constraints = [
            models.UniqueConstraint(fields=["roteiro", "ordem"], name="trecho_roteiro_ordem_unica"),
            models.CheckConstraint(condition=Q(chegada_em__gt=models.F("saida_em")),
                                   name="trecho_roteiro_chega_depois_de_sair"),
            models.CheckConstraint(condition=~Q(origem=models.F("destino")),
                                   name="trecho_roteiro_origem_diferente_destino"),
        ]

    def __str__(self) -> str:
        return f"{self.origem} → {self.destino}"


class BateVoltaBase(models.Model):
    """Um destino visitado todo dia de um período, saindo e voltando à sede no mesmo dia.

    Os trechos continuam sendo a verdade gravada: ao salvar, o bloco é expandido em duas
    pernas por dia (dominio/bate_volta.py). Guardar o bloco é o que permite reabrir e mudar
    uma data sem ter de adivinhar o agrupamento a partir dos trechos.
    Especificação: docs/superpowers/specs/2026-10-02-bate-volta-design.md
    """

    ordem = models.PositiveSmallIntegerField()
    destino = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name="+")
    dia_inicial = models.DateField("primeiro dia")
    dia_final = models.DateField("último dia")
    hora_saida = models.TimeField("hora de saída")
    hora_volta = models.TimeField("hora da volta")

    class Meta:
        abstract = True
        ordering = ["ordem"]

    def __str__(self) -> str:
        return f"{self.destino} ({self.dia_inicial} a {self.dia_final})"


class BateVolta(BateVoltaBase):
    oficio = models.ForeignKey(Oficio, on_delete=models.CASCADE, related_name="bate_voltas")

    class Meta(BateVoltaBase.Meta):
        abstract = False
        constraints = [
            models.UniqueConstraint(fields=["oficio", "ordem"], name="bate_volta_ordem_unica"),
            models.CheckConstraint(condition=Q(dia_final__gte=models.F("dia_inicial")),
                                   name="bate_volta_periodo_valido"),
            models.CheckConstraint(condition=Q(hora_volta__gt=models.F("hora_saida")),
                                   name="bate_volta_volta_no_mesmo_dia"),
        ]


class BateVoltaRoteiro(BateVoltaBase):
    roteiro = models.ForeignKey(Roteiro, on_delete=models.CASCADE, related_name="bate_voltas")

    class Meta(BateVoltaBase.Meta):
        abstract = False
        constraints = [
            models.UniqueConstraint(fields=["roteiro", "ordem"],
                                    name="bate_volta_roteiro_ordem_unica"),
            models.CheckConstraint(condition=Q(dia_final__gte=models.F("dia_inicial")),
                                   name="bate_volta_roteiro_periodo_valido"),
            models.CheckConstraint(condition=Q(hora_volta__gt=models.F("hora_saida")),
                                   name="bate_volta_roteiro_volta_no_mesmo_dia"),
        ]


class DistanciaMunicipios(models.Model):
    """Cache da rota entre dois municípios (sentido origem → destino), como na referência.
    Tabela de cache: não é auditada (só reflete o serviço de rotas)."""

    origem = models.ForeignKey(Municipio, on_delete=models.CASCADE, related_name="+")
    destino = models.ForeignKey(Municipio, on_delete=models.CASCADE, related_name="+")
    km = models.DecimalField(max_digits=8, decimal_places=1)
    minutos = models.PositiveIntegerField("tempo de estrada (min)")
    geometria = models.JSONField(default=list, blank=True)  # [[lat, lon], ...] simplificada
    fonte = models.CharField(max_length=20)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["origem", "destino"],
                                               name="distancia_par_unico")]

    def __str__(self) -> str:
        return f"{self.origem} → {self.destino}: {self.km} km"


class Documento(models.Model):
    """Versão emitida de um documento do ofício (PDF/A-2a). Nunca é alterada."""

    class Tipo(models.TextChoices):
        OFICIO = "oficio", "Ofício"
        JUSTIFICATIVA = "justificativa", "Justificativa"

    class Situacao(models.TextChoices):
        GERANDO = "gerando", "Gerando"
        PRONTO = "pronto", "Pronto"
        FALHOU = "falhou", "Falhou"

    oficio = models.ForeignKey(Oficio, on_delete=models.PROTECT, related_name="documentos")
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    versao = models.PositiveSmallIntegerField()
    situacao = models.CharField(max_length=10, choices=Situacao.choices,
                                default=Situacao.GERANDO)
    dados = models.JSONField("instantâneo dos dados usados", default=dict)
    arquivo = models.FileField(upload_to="documentos/%Y/", blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    tamanho = models.PositiveIntegerField(default=0)
    erro = models.TextField(blank=True)
    emitido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="+")
    emitido_em = models.DateTimeField(auto_now_add=True)
    gerado_em = models.DateTimeField(null=True, blank=True)
    # Texto editado em vigor na emissão (ADR 0018); o instantâneo em `dados["edicao"]` é o
    # que gera o PDF — a chave só diz de onde ele veio.
    edicao = models.ForeignKey("EdicaoDocumento", on_delete=models.PROTECT, null=True,
                               blank=True, related_name="documentos")

    class Meta:
        ordering = ["tipo", "-versao"]
        constraints = [
            models.UniqueConstraint(fields=["oficio", "tipo", "versao"],
                                    name="documento_versao_unica"),
            models.CheckConstraint(condition=~Q(situacao="pronto") | ~Q(sha256=""),
                                   name="documento_pronto_tem_hash"),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.oficio.numero_formatado} v{self.versao}"

    @property
    def nome_arquivo(self) -> str:
        base = f"{self.get_tipo_display()}-{self.oficio.numero:02d}-{self.oficio.ano}"
        return f"{base}-v{self.versao}.pdf".lower().replace("í", "i")


class ViaAssinada(models.Model):
    """A via assinada de um documento gerado (o PDF que voltou assinado). Nunca é alterada:
    anexar outra cria uma versão nova; remover revoga (o arquivo fica como prova). Regra em
    `assinados.py`."""

    class Tipo(models.TextChoices):
        OFICIO = "oficio", "Ofício"
        JUSTIFICATIVA = "justificativa", "Justificativa"
        TERMO = "termo", "Termo de autorização"
        ORDEM = "ordem", "Ordem de serviço"

    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    oficio = models.ForeignKey(Oficio, on_delete=models.PROTECT, null=True, blank=True,
                               related_name="vias_assinadas")
    termo = models.ForeignKey("TermoAutorizacao", on_delete=models.PROTECT, null=True,
                              blank=True, related_name="vias_assinadas")
    ordem = models.ForeignKey("OrdemServico", on_delete=models.PROTECT, null=True, blank=True,
                              related_name="vias_assinadas")
    # Qual documento do termo: o id do servidor, "generico" ou "viatura" (vazio nos demais).
    chave = models.CharField(max_length=20, blank=True)
    # A versão PDF/A do ofício que foi assinada (ofício e justificativa).
    documento = models.ForeignKey(Documento, on_delete=models.PROTECT, null=True, blank=True,
                                  related_name="vias_assinadas")
    arquivo = models.FileField(upload_to="assinados/%Y/")
    nome_original = models.CharField(max_length=255, blank=True)
    sha256 = models.CharField(max_length=64)
    tamanho = models.PositiveIntegerField()
    # SHA-256 dos dados do documento quando a via foi anexada (termo e OS, gerados na hora):
    # se mudarem, a tela avisa "Assinado, mas os dados mudaram".
    impressao_dos_dados = models.CharField(max_length=64, blank=True)
    conferencia = models.JSONField("o que se leu do PDF", default=dict, blank=True)
    enviado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="+")
    enviado_em = models.DateTimeField(auto_now_add=True)
    revogada_em = models.DateTimeField(null=True, blank=True)
    revogada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     null=True, blank=True, related_name="+")
    motivo_revogacao = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-enviado_em"]
        verbose_name = "via assinada"
        verbose_name_plural = "vias assinadas"
        constraints = [
            models.CheckConstraint(
                condition=(Q(tipo__in=["oficio", "justificativa"], oficio__isnull=False,
                             termo__isnull=True, ordem__isnull=True)
                           | Q(tipo="termo", termo__isnull=False, oficio__isnull=True,
                               ordem__isnull=True)
                           | Q(tipo="ordem", ordem__isnull=False, oficio__isnull=True,
                               termo__isnull=True)),
                name="via_assinada_um_dono_do_tipo"),
            models.CheckConstraint(condition=~Q(sha256=""), name="via_assinada_tem_hash"),
            # No máximo uma via em vigor por documento (trocar revoga a anterior).
            models.UniqueConstraint(
                fields=["tipo", "oficio", "termo", "ordem", "chave"],
                condition=Q(revogada_em__isnull=True), nulls_distinct=False,
                name="via_assinada_uma_vigente"),
        ]

    def __str__(self) -> str:
        return f"Via assinada — {self.get_tipo_display()} ({self.enviado_em:%d/%m/%Y})"

    @property
    def nome_download(self) -> str:
        if self.oficio is not None:
            base = f"{self.tipo}-{self.oficio.numero:02d}-{self.oficio.ano}"
        elif self.ordem is not None:
            base = f"os-{self.ordem.numero:03d}-{self.ordem.ano}"
        else:
            base = f"termo-{self.termo_id}-{self.chave}"
        return f"{base}-assinado.pdf"


class EdicaoDocumento(models.Model):
    """Uma versão do texto editado de um documento do ofício (ADR 0018).

    Só acrescenta: cada salvamento, restauração ou "voltar ao modelo" é uma linha nova; a
    versão em vigor é a de maior `numero` do par (ofício, tipo). `regioes` guarda o HTML
    saneado de cada região editável (`cabecalho`, `corpo`, `rodape`); região ausente sai do
    modelo. `regioes == {}` significa "como o modelo gera".
    """

    class Acao(models.TextChoices):
        EDITADO = "editado", "Texto editado"
        RESTAURADO = "restaurado", "Versão restaurada"
        MODELO = "modelo", "Voltou ao modelo"

    oficio = models.ForeignKey(Oficio, on_delete=models.CASCADE, related_name="edicoes")
    tipo = models.CharField(max_length=15, choices=Documento.Tipo.choices)
    numero = models.PositiveIntegerField()
    acao = models.CharField(max_length=10, choices=Acao.choices, default=Acao.EDITADO)
    regioes = models.JSONField("HTML por região", default=dict, blank=True)
    # Rótulos dos blocos que diferem do modelo nesta versão — o histórico legível.
    blocos_alterados = models.JSONField(default=list, blank=True)
    # Impressão (sha256) de cada região como o modelo a gerava quando o texto foi salvo:
    # se o cadastro mudar depois, a folha avisa que o texto editado ficou para trás.
    impressoes = models.JSONField(default=dict, blank=True)
    restaurada_de = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   null=True, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tipo", "-numero"]
        constraints = [
            models.UniqueConstraint(fields=["oficio", "tipo", "numero"],
                                    name="edicao_documento_numero_unico"),
        ]
        verbose_name = "edição de documento"
        verbose_name_plural = "edições de documento"

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.oficio.numero_formatado} — texto v{self.numero}"

    @property
    def do_modelo(self) -> bool:
        return not self.regioes


class Historico(models.Model):
    """Linha do tempo de negócio exibida ao usuário (a trilha técnica é do banco)."""

    class Acao(models.TextChoices):
        CRIADO = "criado", "Rascunho criado"
        ALTERADO = "alterado", "Dados alterados"
        VIAJANTE = "viajante", "Equipe alterada"
        EMITIDO = "emitido", "Ofício emitido"
        DOCUMENTO = "documento", "Documento gerado"
        REABERTO = "reaberto", "Reaberto para correção"
        CANCELADO = "cancelado", "Ofício cancelado"
        REATIVADO = "reativado", "Ofício reativado"
        ARQUIVADO = "arquivado", "Ofício arquivado"
        DESARQUIVADO = "desarquivado", "Ofício desarquivado"
        TEXTO = "texto", "Texto do documento alterado"
        ASSINADO = "assinado", "Via assinada"

    oficio = models.ForeignKey(Oficio, on_delete=models.CASCADE, related_name="historico")
    acao = models.CharField(max_length=12, choices=Acao.choices)
    descricao = models.CharField(max_length=300)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                null=True, related_name="+")
    em = models.DateTimeField(auto_now_add=True)
    dados = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-em", "-id"]
        verbose_name = "histórico"

    def __str__(self) -> str:
        return f"{self.get_acao_display()} — {self.oficio}"


class NumeracaoAnual(models.Model):
    """Piso da numeração de um ano (ex.: começar 2026 no 100)."""

    ano = models.PositiveSmallIntegerField(unique=True)
    piso = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "numeração anual"
        verbose_name_plural = "numeração anual"

    def __str__(self) -> str:
        return f"{self.ano}: a partir de {self.piso}"


class LacunaNumeracao(models.Model):
    """Número liberado pela exclusão de um rascunho; é o único tipo de número reaproveitado."""

    ano = models.PositiveSmallIntegerField()
    numero = models.PositiveIntegerField()
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "lacuna de numeração"
        verbose_name_plural = "lacunas de numeração"
        constraints = [
            models.UniqueConstraint(fields=["ano", "numero"], name="lacuna_numeracao_unica"),
        ]

    def __str__(self) -> str:
        return f"{self.numero:02d}/{self.ano} (livre)"


class TermoAutorizacao(models.Model):
    """Termo de autorização para participar de um evento (um por servidor, mais o genérico
    e o da viatura). Paridade com `viagens_termos` da referência: pode nascer de um ofício
    — e então **herda** dele o que ficar em branco (destinos, período, servidores, viatura)
    — ou ser avulso. Os documentos são gerados na hora, do estado atual."""

    class Situacao(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        CANCELADO = "cancelado", "Cancelado"

    unidade = models.ForeignKey(Unidade, on_delete=models.PROTECT, related_name="termos")
    # Viagem que agrupa o documento (módulo 8); excluir a viagem não apaga documento.
    viagem = models.ForeignKey(Viagem, on_delete=models.PROTECT, null=True, blank=True,
                               related_name="termos")
    oficio = models.ForeignKey(Oficio, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="termos", verbose_name="ofício vinculado")
    # Como o termo nomeia a participação ("manifesto o interesse em participar do …").
    # O valor inicial é o da referência.
    evento = models.CharField("evento", max_length=160, default="PCPR na Comunidade")
    data_inicio = models.DateField("data inicial", null=True, blank=True)
    data_fim = models.DateField("data final", null=True, blank=True)
    servidores = models.ManyToManyField(Servidor, blank=True, related_name="termos")
    viatura = models.ForeignKey(Viatura, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="termos")
    situacao = models.CharField(max_length=10, choices=Situacao.choices,
                                default=Situacao.ATIVO)
    motivo_cancelamento = models.CharField("motivo do cancelamento", max_length=1000,
                                           blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "termo de autorização"
        verbose_name_plural = "termos de autorização"
        constraints = [
            models.CheckConstraint(
                condition=Q(data_fim__isnull=True) | Q(data_inicio__isnull=False,
                                                       data_fim__gte=models.F("data_inicio")),
                name="termo_periodo_ordenado"),
            models.CheckConstraint(
                condition=~Q(situacao="cancelado") | ~Q(motivo_cancelamento=""),
                name="termo_cancelado_tem_motivo"),
        ]

    def __str__(self) -> str:
        return f"Termo #{self.pk}"

    @property
    def cancelado(self) -> bool:
        return self.situacao == self.Situacao.CANCELADO


class TermoDestino(models.Model):
    """Destinos próprios do termo, na ordem em que foram informados."""

    termo = models.ForeignKey(TermoAutorizacao, on_delete=models.CASCADE,
                              related_name="destinos")
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name="+")
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "id"]
        constraints = [models.UniqueConstraint(fields=["termo", "municipio"],
                                               name="termo_destino_unico")]

    def __str__(self) -> str:
        return str(self.municipio)


class OrdemServico(models.Model):
    """Ordem de Serviço (paridade com `viagens_ordens` da referência): determina o
    deslocamento de uma equipe — destinos, período, motivo — com o texto do tipo de
    necessidade (`dominio.ordem_servico`). Não tem viatura, roteiro nem protocolo próprios:
    liga-se aos ofícios. Numeração anual própria: menor lacuna liberada por exclusão, senão
    o maior número + 1 ("OS 001/2026")."""

    class Situacao(models.TextChoices):
        ATIVA = "ativa", "Ativa"
        CANCELADA = "cancelada", "Cancelada"

    TIPOS = (("padrao", "Padrão / texto livre"),
             ("operacao_retorno_posterior", "Operação policial - um dia posterior"),
             ("caminhao", "Caminhão - dois dias antes e depois"),
             ("microonibus", "Micro-ônibus"),
             ("cerimonial_antecipado", "Cerimonial - ida antecipada"))

    unidade = models.ForeignKey(Unidade, on_delete=models.PROTECT, related_name="ordens")
    # Viagem que agrupa o documento (módulo 8); excluir a viagem não apaga documento.
    viagem = models.ForeignKey(Viagem, on_delete=models.PROTECT, null=True, blank=True,
                               related_name="ordens")
    numero = models.PositiveIntegerField()
    ano = models.PositiveSmallIntegerField()
    oficios = models.ManyToManyField(Oficio, blank=True, related_name="ordens")
    tipo = models.CharField("tipo de necessidade", max_length=40, choices=TIPOS,
                            default="padrao")
    data_inicio = models.DateField("data inicial", null=True, blank=True)
    data_fim = models.DateField("data final", null=True, blank=True)
    # A data que sai no documento: nasce na primeira geração e não muda sozinha (todas as
    # vias saem com a mesma data); ajusta-se na tela.
    data_documento = models.DateField("data do documento", null=True, blank=True)
    # Primeira geração do documento: depois dela a OS não se exclui (o número já saiu num
    # documento oficial) — só se cancela.
    documento_gerado_em = models.DateTimeField(null=True, blank=True)
    servidores = models.ManyToManyField(Servidor, blank=True, related_name="ordens")
    # {"<id do servidor>": "<função>"} nos tipos com função (caminhão, micro-ônibus, cerimonial).
    funcoes = models.JSONField("funções da equipe", default=dict, blank=True)
    motivo = models.TextField("motivo", blank=True)
    # Quem assina só esta OS; vazio, vale a configuração (substituto do período ou chefia).
    assinante = models.ForeignKey(Servidor, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="+", verbose_name="assinante desta OS")
    situacao = models.CharField(max_length=10, choices=Situacao.choices,
                                default=Situacao.ATIVA)
    motivo_cancelamento = models.CharField(max_length=1000, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ano", "-numero"]
        verbose_name = "ordem de serviço"
        verbose_name_plural = "ordens de serviço"
        constraints = [
            models.UniqueConstraint(fields=["ano", "numero"], name="os_numero_unico"),
            models.CheckConstraint(condition=Q(numero__gt=0), name="os_numero_positivo"),
            models.CheckConstraint(
                condition=Q(data_fim__isnull=True) | Q(data_inicio__isnull=False,
                                                       data_fim__gte=models.F("data_inicio")),
                name="os_periodo_ordenado"),
            models.CheckConstraint(
                condition=~Q(situacao="cancelada") | ~Q(motivo_cancelamento=""),
                name="os_cancelada_tem_motivo"),
        ]

    def __str__(self) -> str:
        return f"OS {self.numero_formatado}"

    @property
    def numero_formatado(self) -> str:
        return f"{self.numero:03d}/{self.ano}"

    @property
    def cancelada(self) -> bool:
        return self.situacao == self.Situacao.CANCELADA


class OrdemServicoDestino(models.Model):
    ordem = models.ForeignKey(OrdemServico, on_delete=models.CASCADE, related_name="destinos")
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name="+")
    posicao = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["posicao", "id"]
        constraints = [models.UniqueConstraint(fields=["ordem", "municipio"],
                                               name="os_destino_unico")]

    def __str__(self) -> str:
        return str(self.municipio)


class NumeracaoOrdemServico(models.Model):
    """Uma linha por ano: trava a numeração das OS (select_for_update)."""

    ano = models.PositiveSmallIntegerField(unique=True)

    def __str__(self) -> str:
        return str(self.ano)


class LacunaOrdemServico(models.Model):
    """Número de OS liberado por exclusão (o próximo do ano o reaproveita)."""

    ano = models.PositiveSmallIntegerField()
    numero = models.PositiveIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["ano", "numero"],
                                               name="os_lacuna_unica")]

    def __str__(self) -> str:
        return f"{self.numero:03d}/{self.ano}"


# ---------------------------------------------------------------- plano de trabalho
class PlanoTrabalho(models.Model):
    """Plano de Trabalho (paridade com `viagens_planos` da referência): planejamento
    operacional e financeiro de uma ação itinerante — atuação (destinos, datas, horário),
    efetivo e diárias, atividades com metas e recursos, coordenadores e os textos do
    documento. Numeração anual própria com sufixo ("07/2026/ASCOM").

    Na referência o plano liga-se à viagem (módulo 8, ainda não migrado); aqui, até ela
    existir, liga-se aos ofícios de onde vêm destino, datas, efetivo e deslocamento."""

    class Situacao(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        GERADO = "gerado", "Gerado"

    class Genero(models.TextChoices):
        MASCULINO = "M", "o Coordenador"
        FEMININO = "F", "a Coordenadora"

    unidade = models.ForeignKey(Unidade, on_delete=models.PROTECT, related_name="planos")
    # Viagem que agrupa o documento (módulo 8); excluir a viagem não apaga documento.
    viagem = models.ForeignKey(Viagem, on_delete=models.PROTECT, null=True, blank=True,
                               related_name="planos")
    numero = models.PositiveIntegerField()
    ano = models.PositiveSmallIntegerField()
    sufixo = models.CharField("sufixo do número", max_length=20, blank=True)
    oficios = models.ManyToManyField(Oficio, blank=True, related_name="planos")
    situacao = models.CharField(max_length=10, choices=Situacao.choices,
                                default=Situacao.RASCUNHO)
    cancelado = models.BooleanField(default=False)
    motivo_cancelamento = models.CharField("motivo do cancelamento", max_length=1000,
                                           blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    # A data que sai no documento nasce na primeira geração (e não muda sozinha).
    data_documento = models.DateField("data do documento", null=True, blank=True)
    documento_gerado_em = models.DateTimeField(null=True, blank=True)
    assinante = models.ForeignKey(Servidor, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="+", verbose_name="assinante deste plano")

    # 1. Identificação e atuação
    programa = models.ForeignKey(ProgramaSolicitante, on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="planos", verbose_name="programa")
    programa_outros = models.CharField("outro programa", max_length=200, blank=True)
    data_inicio = models.DateField("data de início", null=True, blank=True)
    data_fim = models.DateField("data de fim", null=True, blank=True)
    horario = models.CharField("horário de atendimento", max_length=60,
                               default="09:00 até 17:00", blank=True)
    coordenador_adm = models.ForeignKey(
        Servidor, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="coordenador administrativo")
    coordenador_adm_nome = models.CharField("nome (fora do cadastro)", max_length=255,
                                            blank=True)
    coordenador_adm_cargo = models.CharField("cargo (fora do cadastro)", max_length=120,
                                             blank=True)
    # Como sai no documento ("o Coordenador"/"a Coordenadora"); vazio = ainda não escolhido
    # (pendência quando há coordenador — um padrão errado sairia no documento sem aviso).
    coordenador_adm_genero = models.CharField(max_length=1, choices=Genero.choices, blank=True)
    coordenador_op = models.ForeignKey(
        Servidor, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="coordenador operacional")
    coordenador_op_nome = models.CharField("nome (fora do cadastro)", max_length=255,
                                           blank=True)
    coordenador_op_cargo = models.CharField("cargo (fora do cadastro)", max_length=120,
                                            blank=True)
    coordenador_op_genero = models.CharField(max_length=1, choices=Genero.choices, blank=True)

    # Textos do documento: gerados enquanto o interruptor está ligado; escrever um texto
    # diferente do automático desliga, apagar (ou repetir o automático) religa.
    contextualizacao = models.TextField(blank=True)
    contextualizacao_auto = models.BooleanField(default=True)
    coordenacao = models.TextField(blank=True)
    coordenacao_auto = models.BooleanField(default=True)
    consideracoes = models.TextField(blank=True)
    consideracoes_auto = models.BooleanField(default=True)

    # 2. Deslocamento e diárias (cópia do cálculo, refeita a cada gravação)
    saida_em = models.DateTimeField("saída da sede", null=True, blank=True)
    chegada_em = models.DateTimeField("chegada na sede", null=True, blank=True)
    diarias_composicao = models.CharField(max_length=120, blank=True)
    diarias_unitario = models.DecimalField(max_digits=12, decimal_places=2, null=True,
                                           blank=True)
    diarias_total = models.DecimalField(max_digits=12, decimal_places=2, null=True,
                                        blank=True)

    # 3. Atividades (e os textos que nascem delas)
    atividades = models.ManyToManyField(AtividadePlano, blank=True, related_name="planos")
    atividades_texto = models.TextField(blank=True)
    metas = models.TextField(blank=True)
    recursos = models.TextField(blank=True)
    unidade_movel_texto = models.TextField(blank=True)

    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ano", "-numero"]
        verbose_name = "plano de trabalho"
        verbose_name_plural = "planos de trabalho"
        constraints = [
            models.UniqueConstraint(fields=["ano", "numero"], name="plano_numero_unico"),
            models.CheckConstraint(condition=Q(numero__gt=0), name="plano_numero_positivo"),
            models.CheckConstraint(
                condition=Q(data_fim__isnull=True) | Q(data_inicio__isnull=False,
                                                       data_fim__gte=models.F("data_inicio")),
                name="plano_periodo_ordenado"),
            models.CheckConstraint(
                condition=~Q(cancelado=True) | ~Q(motivo_cancelamento=""),
                name="plano_cancelado_tem_motivo"),
            models.CheckConstraint(
                condition=(Q(diarias_unitario__isnull=True) | Q(diarias_unitario__gte=0))
                & (Q(diarias_total__isnull=True) | Q(diarias_total__gte=0)),
                name="plano_diarias_nao_negativas"),
        ]

    def __str__(self) -> str:
        return f"Plano de Trabalho {self.numero_formatado}"

    @property
    def numero_formatado(self) -> str:
        sufixo = f"/{self.sufixo}" if self.sufixo else ""
        return f"{self.numero:02d}/{self.ano}{sufixo}"

    @property
    def gerado(self) -> bool:
        return self.situacao == self.Situacao.GERADO

    @property
    def programa_nome(self) -> str:
        return self.programa.nome if self.programa is not None else self.programa_outros


class PlanoDestino(models.Model):
    """Destinos do plano na ordem informada; o primeiro é o principal (entra nas diárias)."""

    plano = models.ForeignKey(PlanoTrabalho, on_delete=models.CASCADE, related_name="destinos")
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name="+")
    posicao = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["posicao", "id"]
        constraints = [models.UniqueConstraint(fields=["plano", "municipio"],
                                               name="plano_destino_unico")]

    def __str__(self) -> str:
        return str(self.municipio)


class EfetivoPlano(models.Model):
    """Uma linha do efetivo: quantos de um cargo (de uma unidade). O mesmo cargo pode
    repetir em linhas (referência)."""

    plano = models.ForeignKey(PlanoTrabalho, on_delete=models.CASCADE, related_name="efetivo")
    unidade = models.ForeignKey(Unidade, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="+")
    cargo = models.ForeignKey(Cargo, on_delete=models.PROTECT, related_name="+")
    quantidade = models.PositiveSmallIntegerField(default=1)
    posicao = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["posicao", "id"]
        constraints = [models.CheckConstraint(condition=Q(quantidade__gte=1),
                                              name="efetivo_quantidade_positiva")]

    def __str__(self) -> str:
        return f"{self.quantidade} {self.cargo}"


class EventoPlano(models.Model):
    """Evento adicional de um plano de vários eventos (o evento 1 são os campos do próprio
    plano). Na referência o plano servia de "rascunho do evento atual"; aqui cada evento é
    um registro editado à parte. Efetivo e deslocamento são do plano: a mesma equipe numa
    viagem só (as diárias saem combinadas)."""

    plano = models.ForeignKey(PlanoTrabalho, on_delete=models.CASCADE, related_name="eventos")
    posicao = models.PositiveSmallIntegerField(default=0)
    programa = models.ForeignKey(ProgramaSolicitante, on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="+")
    programa_outros = models.CharField("outro programa", max_length=200, blank=True)
    data_inicio = models.DateField("início do evento", null=True, blank=True)
    data_fim = models.DateField("fim do evento", null=True, blank=True)
    horario = models.CharField("horário de atendimento", max_length=60, blank=True)
    coordenador_op = models.ForeignKey(Servidor, on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="+")
    coordenador_op_nome = models.CharField(max_length=255, blank=True)
    coordenador_op_cargo = models.CharField(max_length=120, blank=True)
    coordenador_op_genero = models.CharField(max_length=1, blank=True)
    atividades = models.ManyToManyField(AtividadePlano, blank=True, related_name="+")
    atividades_texto = models.TextField(blank=True)
    metas = models.TextField(blank=True)
    recursos = models.TextField(blank=True)
    unidade_movel_texto = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["posicao", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(data_fim__isnull=True) | Q(data_inicio__isnull=False,
                                                       data_fim__gte=models.F("data_inicio")),
                name="evento_plano_periodo_ordenado"),
        ]

    def __str__(self) -> str:
        return f"Evento {self.posicao + 2} do {self.plano}"

    @property
    def programa_nome(self) -> str:
        return self.programa.nome if self.programa is not None else self.programa_outros


class EventoDestino(models.Model):
    evento = models.ForeignKey(EventoPlano, on_delete=models.CASCADE, related_name="destinos")
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name="+")
    posicao = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["posicao", "id"]
        constraints = [models.UniqueConstraint(fields=["evento", "municipio"],
                                               name="evento_destino_unico")]

    def __str__(self) -> str:
        return str(self.municipio)


class ResultadoAtividade(models.Model):
    """O realizado de uma atividade do plano, lançado depois da ação (referência)."""

    plano = models.ForeignKey(PlanoTrabalho, on_delete=models.CASCADE, related_name="resultados")
    atividade = models.ForeignKey(AtividadePlano, on_delete=models.PROTECT, related_name="+")
    realizado = models.PositiveIntegerField(null=True, blank=True)
    observacao = models.CharField("observação", max_length=500, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["atividade__nome"]
        constraints = [models.UniqueConstraint(fields=["plano", "atividade"],
                                               name="resultado_atividade_unico")]

    def __str__(self) -> str:
        return f"{self.atividade}: {self.realizado}"


class NumeracaoPlano(models.Model):
    """Uma linha por ano: trava a numeração dos planos (select_for_update)."""

    ano = models.PositiveSmallIntegerField(unique=True)

    def __str__(self) -> str:
        return str(self.ano)


class LacunaPlano(models.Model):
    """Número de plano liberado por exclusão (o próximo do ano o reaproveita)."""

    ano = models.PositiveSmallIntegerField()
    numero = models.PositiveIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["ano", "numero"],
                                               name="plano_lacuna_unica")]

    def __str__(self) -> str:
        return f"{self.numero:02d}/{self.ano}"


class PrestacaoContas(models.Model):
    """Prestação de contas de um ofício (referência: uma por ofício), com uma prestação por
    servidor da equipe. Nasce quando o ofício é emitido. Regra em `prestacao.py`."""

    oficio = models.OneToOneField(Oficio, on_delete=models.PROTECT, related_name="prestacao")
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "prestação de contas"
        verbose_name_plural = "prestações de contas"

    def __str__(self) -> str:
        return f"Prestação do {self.oficio}"


class PrestacaoServidor(models.Model):
    """A prestação de um servidor do ofício: solicitação, diárias, prazo de saque,
    finalização e envio ao financeiro (referência: PrestacaoServidor)."""

    class Situacao(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PREENCHIMENTO = "preenchimento", "Em preenchimento"
        ENVIADA = "enviada", "Enviada"
        APROVADA = "aprovada", "Aprovada"
        DEVOLVIDA = "devolvida", "Devolvida"

    prestacao = models.ForeignKey(PrestacaoContas, on_delete=models.CASCADE,
                                  related_name="servidores")
    servidor = models.ForeignKey(Servidor, on_delete=models.PROTECT, related_name="prestacoes")
    numero_solicitacao = models.CharField("nº da solicitação", max_length=60, blank=True)
    data_liberacao_diarias = models.DateField("liberação das diárias", null=True, blank=True)
    prazo_limite_saque = models.DateField("prazo limite de saque", null=True, blank=True)
    diaria_valor_override = models.DecimalField(max_digits=12, decimal_places=2, null=True,
                                                blank=True)
    diaria_valor_override_observacao = models.CharField(max_length=255, blank=True)
    situacao = models.CharField(max_length=14, choices=Situacao.choices,
                                default=Situacao.PENDENTE)
    arquivada_em = models.DateTimeField(null=True, blank=True)
    finalizada_em = models.DateTimeField(null=True, blank=True)
    justificativa_finalizacao = models.TextField(blank=True)
    enviada_em = models.DateField(null=True, blank=True)
    protocolo_envio = models.CharField("protocolo ou e-mail do envio", max_length=120,
                                       blank=True)
    decidida_em = models.DateTimeField(null=True, blank=True)
    motivo_devolucao = models.TextField(blank=True)
    # Saiu da equipe com dados já lançados: some das listas, mas não se perde.
    removida_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["servidor__nome"]
        verbose_name = "prestação de servidor"
        verbose_name_plural = "prestações de servidor"
        constraints = [
            models.UniqueConstraint(fields=["prestacao", "servidor"],
                                    name="prestacao_servidor_unica"),
            models.CheckConstraint(
                condition=Q(prazo_limite_saque__isnull=True)
                | Q(data_liberacao_diarias__isnull=True)
                | Q(prazo_limite_saque__gte=models.F("data_liberacao_diarias")),
                name="prestacao_prazo_depois_da_liberacao"),
            models.CheckConstraint(condition=Q(diaria_valor_override__isnull=True)
                                   | Q(diaria_valor_override__gt=0),
                                   name="prestacao_diaria_positiva"),
        ]

    def __str__(self) -> str:
        return f"{self.servidor} — {self.prestacao.oficio}"

    @property
    def finalizada(self) -> bool:
        return self.finalizada_em is not None

    @property
    def arquivada(self) -> bool:
        return self.arquivada_em is not None


class DiarioBordo(models.Model):
    """Diário de bordo da viatura, um por prestação (a equipe compartilha). As linhas
    espelham os trechos do ofício; motorista e viatura podem ser trocados só aqui (o ofício
    não muda). Paridade: `DiarioBordo` da referência (docs/migration/prestacao.md)."""

    class Motorista(models.TextChoices):
        OFICIO = "oficio", "Manter o motorista do ofício"
        SERVIDOR = "servidor", "Outro servidor deste ofício"
        OUTRO = "outro_oficio", "Motorista de outro ofício"

    class ViaturaModo(models.TextChoices):
        OFICIO = "oficio", "Manter a viatura do ofício"
        CADASTRO = "cadastro", "Escolher do cadastro"
        MANUAL = "manual", "Preencher à mão"

    prestacao = models.OneToOneField(PrestacaoContas, on_delete=models.PROTECT,
                                     related_name="diario")
    motorista_modo = models.CharField(max_length=12, choices=Motorista.choices,
                                      default=Motorista.OFICIO)
    motorista_servidor = models.ForeignKey(Servidor, on_delete=models.PROTECT, null=True,
                                           blank=True, related_name="+")
    motorista_nome = models.CharField("nome do motorista", max_length=255, blank=True)
    motorista_cpf = models.CharField("CPF do motorista", max_length=11, blank=True)
    motorista_oficio = models.CharField("ofício do motorista", max_length=16, blank=True)
    motorista_protocolo = models.CharField("protocolo do motorista", max_length=30,
                                           blank=True)
    viatura_modo = models.CharField(max_length=10, choices=ViaturaModo.choices,
                                    default=ViaturaModo.OFICIO)
    viatura = models.ForeignKey(Viatura, on_delete=models.PROTECT, null=True, blank=True,
                                related_name="+")
    viatura_modelo = models.CharField("modelo", max_length=120, blank=True)
    viatura_placa = models.CharField("placa", max_length=8, blank=True)
    viatura_tipo = models.CharField("tipo", max_length=20, choices=Viatura.Tipo.choices,
                                    blank=True)
    viatura_combustivel = models.CharField("combustível", max_length=60, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "diário de bordo"
        verbose_name_plural = "diários de bordo"

    def __str__(self) -> str:
        return f"Diário de bordo — {self.prestacao.oficio}"


class DiarioBordoTrecho(models.Model):
    diario = models.ForeignKey(DiarioBordo, on_delete=models.CASCADE, related_name="linhas")
    # Trecho refeito no ofício: a linha fica (guarda os km) e o diário a reaproveita.
    trecho = models.ForeignKey(Trecho, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="+")
    ordem = models.PositiveIntegerField(default=0)
    km_inicial = models.PositiveIntegerField("km inicial", null=True, blank=True)
    km_final = models.PositiveIntegerField("km final", null=True, blank=True)
    abastecimento = models.BooleanField("necessidade de abastecimento", null=True,
                                        blank=True, default=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["diario", "ordem", "pk"]
        verbose_name = "trecho do diário de bordo"
        verbose_name_plural = "trechos do diário de bordo"
        constraints = [
            models.UniqueConstraint(fields=["diario", "ordem"], name="diario_linha_ordem_unica"),
            models.CheckConstraint(
                condition=Q(km_inicial__isnull=True) | Q(km_final__isnull=True)
                | Q(km_final__gte=models.F("km_inicial")),
                name="diario_km_final_depois_do_inicial",
                violation_error_message="O km final não pode ser menor que o km inicial."),
        ]

    def __str__(self) -> str:
        return f"Trecho {self.ordem + 1} — {self.diario}"


class RelatorioTecnico(models.Model):
    """Relatório técnico da prestação: o texto é da equipe (um por prestação) e o documento
    sai por servidor (nome, CPF e a diária dele). Paridade: `RelatorioTecnico` da
    referência (docs/migration/prestacao.md, 9c)."""

    prestacao = models.OneToOneField(PrestacaoContas, on_delete=models.PROTECT,
                                     related_name="relatorio")
    motivo = models.TextField("descrição do evento", blank=True)
    diaria = models.CharField("diária", max_length=255, blank=True)
    translado = models.CharField("translado", max_length=255, blank=True)
    combustivel = models.CharField("combustível", max_length=255, blank=True)
    passagem = models.CharField("passagem", max_length=255, blank=True)
    atividade = models.TextField("objetivo da participação", blank=True)
    conclusao = models.TextField("conclusão", blank=True)
    medidas = models.TextField("medidas a serem adotadas pelo órgão", blank=True)
    info_complementares = models.TextField("informações complementares", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "relatório técnico"
        verbose_name_plural = "relatórios técnicos"

    def __str__(self) -> str:
        return f"Relatório técnico — {self.prestacao.oficio}"
