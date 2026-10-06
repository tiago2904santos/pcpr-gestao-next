"""Solicitação de evento social (paridade com `SolicitacaoEvento` da referência): o que,
quando e onde, quem pede, a estrutura (serviços, equipes, unidade móvel) e o despacho da
Diretoria-Geral. O status anda pelos serviços (solicitacoes.py); cada passo vira um
Movimento; as edições ficam na trilha de auditoria do banco."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from .models import Equipe, OrgaoResponsavel, Servico, TipoEvento, UnidadeMovel


class Solicitacao(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        AGUARDANDO = "aguardando_despacho", "Aguardando despacho"
        DEVOLVIDA = "devolvida", "Devolvida para correção"
        DEFERIDA = "deferida", "Deferida — em andamento"
        ATENDIDA = "atendida", "Atendida"
        NAO_ATENDIDA = "nao_atendida", "Não atendida"
        CANCELADA = "cancelada", "Cancelada"

    class Decisao(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        ATENDER = "atender", "Atender"
        NAO_ATENDER = "nao_atender", "Não atender"
        CANCELADO = "cancelado", "Evento cancelado"

    class Operacao(models.TextChoices):
        DIARIA = "diaria", "Diária"
        EXTRAJORNADA = "extrajornada", "Extrajornada"

    data_solicitacao = models.DateField("data da solicitação")
    data_inicio_evento = models.DateField("início do evento", null=True, blank=True)
    data_fim_evento = models.DateField("fim do evento", null=True, blank=True)
    municipio = models.ForeignKey("cadastros.Municipio", verbose_name="município",
                                  on_delete=models.PROTECT, null=True, blank=True,
                                  related_name="solicitacoes_evento")
    tipo_evento = models.ForeignKey(TipoEvento, verbose_name="tipo de evento",
                                    on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="solicitacoes")
    solicitante_nome = models.CharField("solicitante", max_length=150, blank=True)
    solicitante_cargo_unidade = models.CharField("cargo / unidade", max_length=255, blank=True)
    contato = models.CharField("contato", max_length=100, blank=True)
    orgao_responsavel = models.ForeignKey(OrgaoResponsavel, verbose_name="órgão responsável",
                                          on_delete=models.PROTECT, null=True, blank=True,
                                          related_name="solicitacoes")
    unidade_movel = models.BooleanField("unidade móvel", default=False)
    unidade_movel_designada = models.ForeignKey(UnidadeMovel, verbose_name="qual unidade móvel",
                                                on_delete=models.PROTECT, null=True,
                                                blank=True, related_name="solicitacoes")
    local_evento = models.CharField("local do evento", max_length=255, blank=True)
    endereco = models.CharField("endereço", max_length=255, blank=True)
    bairro = models.CharField("bairro", max_length=120, blank=True)
    cep = models.CharField("CEP", max_length=9, blank=True)
    protocolo = models.CharField("protocolo", max_length=20, blank=True, db_index=True)
    descricao_complementar = models.TextField("descrição complementar", blank=True)
    quantidade_servidores = models.PositiveIntegerField("total de servidores", default=0)
    tipo_operacao = models.CharField("tipo de operação", max_length=15,
                                     choices=Operacao.choices, default=Operacao.DIARIA)
    quantidade_cin = models.PositiveIntegerField("quantidade de CIN agendadas", null=True,
                                                 blank=True)
    motorista = models.ForeignKey("cadastros.Servidor", verbose_name="motorista",
                                  on_delete=models.PROTECT, null=True, blank=True,
                                  related_name="solicitacoes_evento")
    status = models.CharField("status", max_length=25, choices=Status.choices,
                              default=Status.RASCUNHO)
    decisao_dg = models.CharField("decisão da DG", max_length=15, choices=Decisao.choices,
                                  default=Decisao.PENDENTE)
    observacoes_dg = models.TextField("observações da DG", blank=True)
    decidido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     null=True, blank=True, related_name="+")
    decidido_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="responsável",
                                   on_delete=models.PROTECT, related_name="solicitacoes_evento")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "eventos"
        ordering = ["-data_solicitacao", "-criado_em"]
        verbose_name = "solicitação de evento"
        verbose_name_plural = "solicitações de evento"
        permissions = [("despachar_solicitacao", "Despachar solicitações de evento (DG)"),
                       ("ver_todas_solicitacoes", "Ver as solicitações de todos")]
        indexes = [models.Index(fields=["status", "data_inicio_evento"],
                                name="eventos_solic_status_inicio")]
        constraints = [models.CheckConstraint(
            condition=(models.Q(data_inicio_evento__isnull=True)
                       | models.Q(data_fim_evento__isnull=True)
                       | models.Q(data_fim_evento__gte=models.F("data_inicio_evento"))),
            name="eventos_solic_periodo_valido")]

    def __str__(self) -> str:
        return f"Solicitação #{self.pk}"

    @property
    def finalizada(self) -> bool:
        return self.status in (self.Status.ATENDIDA, self.Status.NAO_ATENDIDA,
                               self.Status.CANCELADA)


class SolicitacaoServico(models.Model):
    solicitacao = models.ForeignKey(Solicitacao, on_delete=models.CASCADE,
                                    related_name="servicos")
    servico = models.ForeignKey(Servico, on_delete=models.PROTECT, related_name="solicitacoes")
    observacao = models.CharField("observação", max_length=255, blank=True)

    class Meta:
        app_label = "eventos"
        ordering = ["servico__nome"]
        constraints = [models.UniqueConstraint(fields=["solicitacao", "servico"],
                                               name="eventos_solic_servico_unico")]

    def __str__(self) -> str:
        return str(self.servico)


class SolicitacaoEquipe(models.Model):
    solicitacao = models.ForeignKey(Solicitacao, on_delete=models.CASCADE,
                                    related_name="equipes")
    equipe = models.ForeignKey(Equipe, on_delete=models.PROTECT, related_name="solicitacoes")
    quantidade_servidores = models.PositiveIntegerField("servidores", null=True, blank=True)
    observacao = models.CharField("observação", max_length=255, blank=True)

    class Meta:
        app_label = "eventos"
        ordering = ["equipe__nome"]
        constraints = [models.UniqueConstraint(fields=["solicitacao", "equipe"],
                                               name="eventos_solic_equipe_unica")]

    def __str__(self) -> str:
        return f"{self.equipe} ({self.quantidade_servidores or 0})"


class AnexoSolicitacao(models.Model):
    solicitacao = models.ForeignKey(Solicitacao, on_delete=models.CASCADE,
                                    related_name="anexos")
    arquivo = models.FileField(upload_to="eventos/%Y/")
    nome_original = models.CharField(max_length=255)
    tamanho = models.PositiveIntegerField(default=0)
    enviado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "eventos"
        ordering = ["criado_em", "pk"]
        verbose_name = "anexo da solicitação"
        verbose_name_plural = "anexos das solicitações"

    def __str__(self) -> str:
        return self.nome_original


class Movimento(models.Model):
    """Um passo da solicitação, com quem, quando e a observação."""

    class Acao(models.TextChoices):
        CRIACAO = "criacao", "Rascunho criado"
        ENVIO = "envio", "Solicitação enviada"
        DEVOLUCAO = "devolucao", "Enviada para correção"
        REENVIO = "reenvio", "Alterada e reenviada para a DG"
        AJUSTE_DG = "ajuste_dg", "Servidores ajustados pela DG"
        DECISAO = "decisao", "Decisão da DG registrada"
        CONCLUSAO = "conclusao", "Atendimento confirmado"
        CANCELAMENTO = "cancelamento", "Evento cancelado"
        TRANSFERENCIA = "transferencia", "Responsável transferido"
        ANEXO = "anexo", "Anexos"

    solicitacao = models.ForeignKey(Solicitacao, on_delete=models.CASCADE,
                                    related_name="movimentos")
    acao = models.CharField(max_length=20, choices=Acao.choices)
    status_anterior = models.CharField(max_length=25, blank=True)
    status_novo = models.CharField(max_length=25, blank=True)
    observacao = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="+")
    em = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "eventos"
        ordering = ["-em", "-pk"]
        verbose_name = "movimento da solicitação"
        verbose_name_plural = "movimentos das solicitações"

    def __str__(self) -> str:
        return f"{self.solicitacao} — {self.get_acao_display()}"
