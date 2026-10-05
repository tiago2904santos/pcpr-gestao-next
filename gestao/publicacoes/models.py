"""Controle de publicações da ASCOM (paridade com o "Relatório de Publicações" da referência).

Cada pauta entra pela assessoria, passa por redação, edição e revisão e sai publicada no
site da PCPR (e, eventualmente, na AEN). O status anda pelo registro de andamento
(`Andamento`); as edições dos campos ficam na trilha de auditoria do banco (trigger).
Integrantes da equipe e unidades responsáveis são cadastros de apoio, para padronizar os
nomes. (A "unidade" aqui é texto da ASCOM, como na referência — não o cadastro de
unidades de Viagens.)
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from . import dominio


class Integrante(models.Model):
    """Integrante da equipe de comunicação (ou parceiro, como SESP e AEN)."""

    nome = models.CharField("nome", max_length=100)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "integrante da equipe"
        verbose_name_plural = "equipe de comunicação"
        constraints = [models.UniqueConstraint(Lower("nome"),
                                               name="publicacoes_integrante_nome")]

    def __str__(self) -> str:
        return self.nome


class UnidadeResponsavel(models.Model):
    """Unidade policial responsável pela pauta (DP, DHPP, DPC...)."""

    nome = models.CharField("nome", max_length=150)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "unidade responsável"
        verbose_name_plural = "unidades responsáveis"
        constraints = [models.UniqueConstraint(Lower("nome"),
                                               name="publicacoes_unidade_nome")]

    def __str__(self) -> str:
        return self.nome


class Publicacao(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "pendente", dominio.ROTULOS["pendente"]
        EM_ANDAMENTO = "em_andamento", dominio.ROTULOS["em_andamento"]
        PUBLICADA = "publicada", dominio.ROTULOS["publicada"]
        CANCELADA = "cancelada", dominio.ROTULOS["cancelada"]

    data = models.DateField("data da pauta")
    jornalista = models.ForeignKey(Integrante, verbose_name="jornalista responsável",
                                   on_delete=models.PROTECT, related_name="pautas")
    unidade = models.ForeignKey(UnidadeResponsavel, verbose_name="unidade responsável",
                                on_delete=models.PROTECT, related_name="pautas",
                                null=True, blank=True)
    fonte = models.CharField("fonte da pauta", max_length=200, blank=True)
    inicio_pauta = models.TimeField("início da pauta", null=True, blank=True)
    titulo = models.CharField("título da pauta", max_length=300)
    status = models.CharField("status", max_length=15, choices=Status.choices,
                              default=Status.PENDENTE)
    andamento = models.TextField("andamento", blank=True)
    colocada_edicao = models.TimeField("colocada para edição", null=True, blank=True)
    data_publicacao = models.DateField("data de publicação", null=True, blank=True)
    horario_publicacao = models.TimeField("horário de publicação", null=True, blank=True)
    revisao = models.ForeignKey(Integrante, verbose_name="revisão", on_delete=models.PROTECT,
                                related_name="revisoes", null=True, blank=True)
    galeria_fotos = models.ForeignKey(Integrante, verbose_name="galeria de fotos",
                                      on_delete=models.PROTECT, related_name="galerias",
                                      null=True, blank=True)
    bitly_grupos = models.BooleanField("Bitly nos grupos", null=True, blank=True)
    enviado_sesp = models.BooleanField("enviado para a SESP", null=True, blank=True)
    publicado_aen = models.BooleanField("publicado na AEN", null=True, blank=True)
    link_site = models.URLField("link no site da PCPR", max_length=500, blank=True)
    link_aen = models.URLField("link na AEN", max_length=500, blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="publicacoes")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "-inicio_pauta", "-pk"]
        verbose_name = "publicação"
        verbose_name_plural = "publicações"
        indexes = [
            models.Index(fields=["status", "data"], name="publicacoes_status_data"),
            models.Index(fields=["data_publicacao"], name="publicacoes_data_pub"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(data_publicacao__isnull=True)
                           | models.Q(data_publicacao__gte=models.F("data"))),
                name="publicacoes_publicada_apos_pauta"),
        ]

    def __str__(self) -> str:
        return f"Pauta #{self.pk}"

    @property
    def aberta(self) -> bool:
        return self.status in dominio.ABERTOS

    @property
    def tom(self) -> str:
        return dominio.TONS.get(self.status, "neutro")

    @property
    def tempo_ate_publicar(self) -> timedelta | None:
        return dominio.tempo_ate_publicar(self.data, self.inicio_pauta, self.data_publicacao,
                                          self.horario_publicacao)

    @property
    def tempo_ate_publicar_texto(self) -> str:
        return dominio.formatar_duracao(self.tempo_ate_publicar)

    @property
    def quando_publicada(self) -> str:
        return dominio.quando_publicada(self.data_publicacao, self.horario_publicacao)


class Andamento(models.Model):
    """Uma mudança de status, com a anotação de quem registrou."""

    publicacao = models.ForeignKey(Publicacao, on_delete=models.CASCADE,
                                   related_name="andamentos")
    status_anterior = models.CharField(max_length=15, choices=Publicacao.Status.choices)
    status_novo = models.CharField(max_length=15, choices=Publicacao.Status.choices)
    anotacao = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="+")
    em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-em", "-pk"]
        verbose_name = "andamento da pauta"
        verbose_name_plural = "andamentos das pautas"

    def __str__(self) -> str:
        return f"{self.publicacao} → {self.get_status_novo_display()}"
