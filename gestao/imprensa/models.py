"""Atendimento à imprensa da ASCOM (paridade com o "Relatório de atendimento" da referência).

Cada atendimento é o pedido de um jornalista (veículo, contato, o que pediu), quem atendeu,
as fontes consultadas e a resposta enviada. A situação anda pelo registro de andamento
(`Andamento`: de qual para qual situação, com a anotação de quem registrou). As edições dos
campos ficam na trilha de auditoria do banco (trigger), lida pelo histórico da folha.
Integrantes da equipe e veículos são cadastros de apoio, para padronizar os nomes.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from . import dominio


class Integrante(models.Model):
    """Integrante da equipe de atendimento à imprensa (nome curto, como na planilha)."""

    nome = models.CharField("nome", max_length=100)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "integrante da equipe"
        verbose_name_plural = "equipe de atendimento"
        constraints = [models.UniqueConstraint(Lower("nome"), name="imprensa_integrante_nome")]

    def __str__(self) -> str:
        return self.nome


class Veiculo(models.Model):
    """Veículo de imprensa (TV, rádio, portal, jornal)."""

    nome = models.CharField("nome", max_length=150)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "veículo de imprensa"
        verbose_name_plural = "veículos de imprensa"
        constraints = [models.UniqueConstraint(Lower("nome"), name="imprensa_veiculo_nome")]

    def __str__(self) -> str:
        return self.nome


class Atendimento(models.Model):
    class Situacao(models.TextChoices):
        EM_ANDAMENTO = "em_andamento", dominio.ROTULOS["em_andamento"]
        EM_ANDAMENTO_TEXTO = "em_andamento_texto", dominio.ROTULOS["em_andamento_texto"]
        EM_ANDAMENTO_VIDEO = "em_andamento_video", dominio.ROTULOS["em_andamento_video"]
        AGUARDANDO_FONTE = "aguardando_fonte", dominio.ROTULOS["aguardando_fonte"]
        AGUARDANDO_PRODUTORA = "aguardando_produtora", dominio.ROTULOS["aguardando_produtora"]
        AGUARDAR_NOVA_SOLICITACAO = ("aguardar_nova_solicitacao",
                                     dominio.ROTULOS["aguardar_nova_solicitacao"])
        PROXIMO_MES = "proximo_mes", dominio.ROTULOS["proximo_mes"]
        ATENDIDO = "atendido", dominio.ROTULOS["atendido"]
        NAO_RESPONDER = "nao_responder", dominio.ROTULOS["nao_responder"]

    data = models.DateField("data do pedido")
    horario = models.TimeField("horário do pedido", null=True, blank=True)
    jornalista = models.CharField("jornalista", max_length=150)
    veiculo = models.ForeignKey(Veiculo, verbose_name="veículo", on_delete=models.PROTECT,
                                related_name="atendimentos", null=True, blank=True)
    contato = models.CharField("contato", max_length=150, blank=True)
    pedido = models.TextField("pedido")
    situacao = models.CharField("situação", max_length=30, choices=Situacao.choices,
                                default=Situacao.EM_ANDAMENTO)
    responsavel = models.ForeignKey(Integrante, verbose_name="responsável pelo atendimento",
                                    on_delete=models.PROTECT, related_name="atendimentos",
                                    null=True, blank=True)
    deadline = models.DateField("deadline / veiculação", null=True, blank=True)
    horario_resposta = models.TimeField("horário da resposta", null=True, blank=True)
    responsavel_resposta = models.ForeignKey(
        Integrante, verbose_name="responsável pela resposta", on_delete=models.PROTECT,
        related_name="respostas", null=True, blank=True)
    fonte = models.TextField("fontes consultadas", blank=True)
    inicio_pedido = models.TextField("início do pedido às fontes", blank=True)
    final_pedido = models.TextField("retorno das fontes", blank=True)
    andamento = models.TextField("andamento", blank=True)
    resposta = models.TextField("resposta enviada", blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="atendimentos_imprensa")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "-horario", "-pk"]
        verbose_name = "atendimento à imprensa"
        verbose_name_plural = "atendimentos à imprensa"
        indexes = [
            models.Index(fields=["situacao", "data"], name="imprensa_situacao_data"),
            models.Index(fields=["deadline"], name="imprensa_deadline"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(deadline__isnull=True)
                           | models.Q(deadline__gte=models.F("data"))),
                name="imprensa_deadline_depois_do_pedido"),
        ]

    def __str__(self) -> str:
        return f"Atendimento #{self.pk}"

    @property
    def aberto(self) -> bool:
        return self.situacao in dominio.ABERTAS

    @property
    def tom(self) -> str:
        return dominio.TONS.get(self.situacao, "neutro")

    @property
    def pedido_resumo(self) -> str:
        return dominio.resumo(self.pedido)

    @property
    def titulo(self) -> str:
        """Quem pediu e por qual veículo — o que identifica o atendimento."""
        veiculo = self.veiculo if self.veiculo_id else None
        return f"{self.jornalista} · {veiculo.nome}" if veiculo else self.jornalista


class Andamento(models.Model):
    """Uma mudança de situação, com a anotação de quem registrou."""

    atendimento = models.ForeignKey(Atendimento, on_delete=models.CASCADE,
                                    related_name="andamentos")
    situacao_anterior = models.CharField(max_length=30, choices=Atendimento.Situacao.choices)
    situacao_nova = models.CharField(max_length=30, choices=Atendimento.Situacao.choices)
    anotacao = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="+")
    em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-em", "-pk"]
        verbose_name = "andamento do atendimento"
        verbose_name_plural = "andamentos dos atendimentos"

    def __str__(self) -> str:
        return f"{self.atendimento} → {self.get_situacao_nova_display()}"
