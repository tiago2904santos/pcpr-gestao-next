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
    Combustivel,
    ModeloTexto,
    Municipio,
    Servidor,
    Unidade,
    Viatura,
)

from .dominio.numeracao import formatar_numero


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
    ano = models.PositiveSmallIntegerField("ano")
    numero = models.PositiveIntegerField("número")
    data_oficio = models.DateField("data do ofício")
    protocolo = models.CharField(
        "protocolo (eProtocolo)", max_length=9, blank=True,
        help_text="Nove dígitos, com ou sem pontuação (ex.: 12.345.678-9).",
    )
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

    class Meta:
        ordering = ["-ano", "-numero"]
        verbose_name = "ofício"
        verbose_name_plural = "ofícios"
        permissions = [
            ("emitir_oficio", "Pode emitir ofícios"),
            ("cancelar_oficio", "Pode cancelar ofícios"),
            ("reabrir_oficio", "Pode reabrir ofícios emitidos"),
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
        return self.situacao == self.Situacao.RASCUNHO


class Viajante(models.Model):
    oficio = models.ForeignKey(Oficio, on_delete=models.CASCADE, related_name="viajantes")
    servidor = models.ForeignKey(Servidor, on_delete=models.PROTECT, related_name="viagens")
    motorista = models.BooleanField("motorista", default=False)
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "id"]
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
        TEXTO = "texto", "Texto do documento alterado"

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
