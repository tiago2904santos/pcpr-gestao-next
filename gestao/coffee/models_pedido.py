"""A solicitação de coffee break — a própria Ordem de Serviço ao fornecedor — e o histórico
(CB2; paridade com `coffee_break/models.py` da referência, docs/migration/coffee-break.md §3).
O lote é escolhido pelo município; o valor unitário é congelado na criação (ou na troca de
lote). A situação financeira é derivada dos marcos, nunca gravada; as etapas 2 e 3 (nota,
ofício, protocolo, ordem bancária) completam os campos na CB3."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from . import dominio_pedido
from .models import Carimbos, Lote


class Solicitacao(Carimbos):
    lote = models.ForeignKey(Lote, on_delete=models.PROTECT, related_name="solicitacoes")
    municipio = models.ForeignKey("cadastros.Municipio", verbose_name="município do evento",
                                  on_delete=models.PROTECT, related_name="+")
    data_solicitacao = models.DateField("data da solicitação")
    numero = models.CharField("Nº da OS", max_length=20, blank=True)
    descricao = models.TextField("descrição do evento (objeto da OS)")
    quantidade = models.PositiveIntegerField("quantidade de pessoas")
    data_evento = models.DateField("data do evento", null=True, blank=True)
    horario = models.TimeField("horário", null=True, blank=True)
    local_entrega = models.CharField("local de entrega", max_length=255, blank=True)
    endereco = models.CharField("endereço", max_length=255, blank=True)
    bairro = models.CharField("bairro", max_length=120, blank=True)
    cep = models.CharField("CEP", max_length=9, blank=True)
    responsavel = models.CharField("responsável pelo recebimento", max_length=200, blank=True,
                                   help_text="Nome e telefone de quem recebe no local.")
    valor_unitario = models.DecimalField("valor unitário", max_digits=12, decimal_places=4,
                                         null=True, blank=True)
    # Marcos do fluxo financeiro (as etapas 2 e 3 chegam com a CB3).
    nota_fiscal = models.CharField("nº da nota fiscal", max_length=60, blank=True)
    quantidade_faturada = models.PositiveIntegerField("quantidade faturada", null=True,
                                                      blank=True)
    numero_oficio = models.CharField("nº do ofício", max_length=20, blank=True)
    data_oficio = models.DateField("data do ofício", null=True, blank=True)
    protocolo_pcpr = models.CharField("PCPR protocolo n.º", max_length=30, blank=True)
    protocolo_pagamento = models.CharField("protocolo de pagamento", max_length=20, blank=True)
    atesto_em = models.DateField("atesto e envio ao GAF", null=True, blank=True)
    ordem_bancaria_em = models.DateField("ordem bancária emitida em", null=True, blank=True)
    envio_empresa_em = models.DateField("ordem bancária enviada à empresa em", null=True,
                                        blank=True)
    observacoes = models.TextField("observações", blank=True)
    em_correcao = models.BooleanField("aberta para correção", default=False)
    # Pagamento conjunto: as OS do mesmo lote que vão num só ofício e num só protocolo
    # apontam para a principal (a principal não aponta para ninguém).
    pagamento_com = models.ForeignKey("self", verbose_name="pagamento junto com",
                                      on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="conjuntas")
    cancelada = models.BooleanField("cancelada", default=False)
    cancelada_em = models.DateTimeField(null=True, blank=True)
    cancelada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                      null=True, blank=True, related_name="+")
    motivo_cancelamento = models.CharField("motivo do cancelamento", max_length=255,
                                           blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="+")

    class Meta:
        app_label = "coffee"
        ordering = ["-data_solicitacao", "-pk"]
        verbose_name = "solicitação de coffee break"
        verbose_name_plural = "solicitações de coffee break"
        constraints = [
            models.UniqueConstraint(fields=["numero"], condition=~models.Q(numero=""),
                                    name="coffee_os_numero_unico"),
            models.CheckConstraint(condition=models.Q(cancelada=True)
                                   | models.Q(quantidade__gte=1),
                                   name="coffee_os_quantidade_positiva"),
            models.CheckConstraint(condition=models.Q(ordem_bancaria_em__isnull=True)
                                   | models.Q(atesto_em__isnull=True)
                                   | models.Q(ordem_bancaria_em__gte=models.F("atesto_em")),
                                   name="coffee_os_ob_depois_do_atesto"),
            models.CheckConstraint(condition=models.Q(envio_empresa_em__isnull=True)
                                   | models.Q(ordem_bancaria_em__isnull=True)
                                   | models.Q(envio_empresa_em__gte=models.F(
                                       "ordem_bancaria_em")),
                                   name="coffee_os_envio_depois_da_ob"),
        ]
        indexes = [models.Index(fields=["lote", "cancelada"], name="coffee_os_lote_ativa")]

    def __str__(self) -> str:
        return f"OS {self.numero}" if self.numero else f"Solicitação #{self.pk}"

    @property
    def marcos(self) -> dominio_pedido.Marcos:
        return dominio_pedido.Marcos(
            cancelada=self.cancelada, nota=bool(self.nota_fiscal),
            protocolo=bool(self.protocolo_pagamento), atesto=bool(self.atesto_em),
            ordem_bancaria=bool(self.ordem_bancaria_em),
            envio_empresa=bool(self.envio_empresa_em))

    @property
    def situacao(self) -> str:
        return dominio_pedido.situacao(self.marcos)

    @property
    def situacao_rotulo(self) -> str:
        return dominio_pedido.ROTULO_SITUACAO[self.situacao]

    @property
    def situacao_tom(self) -> str:
        return dominio_pedido.TOM_SITUACAO[self.situacao]

    @property
    def financeiro_iniciado(self) -> bool:
        return dominio_pedido.financeiro_iniciado(self.marcos)

    @property
    def concluida(self) -> bool:
        return bool(self.envio_empresa_em) and not self.cancelada

    @property
    def bloqueada(self) -> bool:
        """Cancelada, ou concluída sem estar aberta para correção: só consulta."""
        return self.cancelada or (self.concluida and not self.em_correcao)

    @property
    def valores_dos_marcos(self) -> dict:
        return {campo: getattr(self, campo) for campo, *_ in dominio_pedido.MARCOS}

    @property
    def quantidade_efetiva(self) -> int:
        return dominio_pedido.quantidade_efetiva(self.quantidade, self.quantidade_faturada)

    @property
    def valor(self) -> Decimal | None:
        return dominio_pedido.valor(self.quantidade_efetiva, self.valor_unitario)


class Movimento(models.Model):
    """O que aconteceu com a solicitação, com quem, quando e o texto. As mudanças campo a
    campo ficam na trilha do banco."""

    class Acao(models.TextChoices):
        CRIADA = "criada", "Solicitação criada"
        ATUALIZADA = "atualizada", "Solicitação atualizada"
        CANCELADA = "cancelada", "Solicitação cancelada"
        REATIVADA = "reativada", "Solicitação reativada"
        ANDAMENTO = "andamento", "Andamento registrado"
        CONJUNTO = "conjunto", "Pagamento conjunto"
        DOCUMENTO = "documento", "Documento"
        CORRECAO = "correcao", "Correção"

    solicitacao = models.ForeignKey(Solicitacao, on_delete=models.CASCADE,
                                    related_name="movimentos")
    acao = models.CharField(max_length=20, choices=Acao.choices)
    texto = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="+")
    em = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "coffee"
        ordering = ["-em", "-pk"]
        verbose_name = "movimento da solicitação de coffee break"
        verbose_name_plural = "movimentos das solicitações de coffee break"

    def __str__(self) -> str:
        return f"{self.solicitacao} — {self.get_acao_display()}"


class Via(models.Model):
    """Cada PDF que sai (visualizar, baixar) fica guardado como via emitida; a folha igual
    à última não gera outra. A via assinada (anexada) vale no lugar do gerado até ser
    removida — removida, fica guardada (removida_em)."""

    solicitacao = models.ForeignKey(Solicitacao, on_delete=models.CASCADE, related_name="vias")
    tipo = models.CharField(max_length=12)
    arquivo = models.FileField(upload_to="coffee/vias/%Y/")
    nome = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    assinada = models.BooleanField(default=False)
    emitida_em = models.DateTimeField(auto_now_add=True)
    emitida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="+")
    removida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "coffee"
        ordering = ["-emitida_em", "-pk"]
        verbose_name = "via de documento do coffee break"
        verbose_name_plural = "vias de documentos do coffee break"
        indexes = [models.Index(fields=["solicitacao", "tipo"], name="coffee_via_documento")]

    def __str__(self) -> str:
        return f"{self.nome} ({'assinada' if self.assinada else 'emitida'})"
