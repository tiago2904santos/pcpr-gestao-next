"""Modelos técnicos da plataforma: trilha de auditoria, outbox transacional e avisos."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class EventoAuditoria(models.Model):
    """Registro imutável gravado por *trigger* do PostgreSQL.

    A aplicação nunca escreve nesta tabela diretamente: o banco registra toda
    inserção/alteração/exclusão das tabelas auditadas, encadeando um hash
    SHA-256 com o registro anterior (evidência de adulteração). UPDATE e
    DELETE na tabela são bloqueados por trigger.
    """

    id = models.BigAutoField(primary_key=True)
    ocorrido_em = models.DateTimeField()
    tabela = models.TextField()
    registro_id = models.TextField()
    operacao = models.CharField(max_length=6)
    usuario_id = models.BigIntegerField(null=True)
    ip = models.GenericIPAddressField(null=True)
    requisicao_id = models.TextField(null=True)  # noqa: DJ001 (espelha o SQL)
    antes = models.JSONField(null=True)
    depois = models.JSONField(null=True)
    alterados = models.JSONField(null=True)
    hash_anterior = models.TextField(null=True)  # noqa: DJ001 (espelha o SQL)
    hash = models.TextField()

    class Meta:
        managed = False
        db_table = "auditoria_evento"
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"{self.operacao} {self.tabela}#{self.registro_id}"


class MensagemOutbox(models.Model):
    """Efeito colateral a executar *depois* do commit (e-mail, PDF, integrações).

    Gravada na mesma transação da mudança de negócio: ou ambos persistem, ou
    nenhum. O worker (`manage.py processar_outbox`) consome com
    `FOR UPDATE SKIP LOCKED`, com tentativas e backoff exponencial.
    """

    class Situacao(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PROCESSADA = "processada", "Processada"
        FALHOU = "falhou", "Falhou definitivamente"

    topico = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    chave_idempotencia = models.CharField(max_length=200, unique=True)
    situacao = models.CharField(
        max_length=12, choices=Situacao.choices, default=Situacao.PENDENTE
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    disponivel_em = models.DateTimeField()
    tentativas = models.PositiveSmallIntegerField(default=0)
    processada_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.TextField(blank=True)

    class Meta:
        db_table = "plataforma_outbox"
        indexes = [
            models.Index(
                fields=["disponivel_em"],
                name="outbox_pendentes_idx",
                condition=models.Q(situacao="pendente"),
            )
        ]

    def __str__(self) -> str:
        return f"{self.topico} ({self.situacao})"


class Notificacao(models.Model):
    """Um aviso do sino para uma pessoa (um aviso para N pessoas = N linhas), como na
    referência. Fora da trilha de auditoria: é comunicação, não dado de negócio."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="notificacoes")
    titulo = models.CharField(max_length=150)
    mensagem = models.CharField(max_length=255, blank=True)
    link = models.CharField(max_length=255, blank=True)  # caminho interno (reverse)
    lida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criada_em", "-pk"]
        indexes = [models.Index(fields=["usuario", "lida"], name="notificacao_usuario_lida")]
        verbose_name = "notificação"
        verbose_name_plural = "notificações"

    def __str__(self) -> str:
        return self.titulo


class RotinaDoDia(models.Model):
    """Marca de que as rotinas diárias já rodaram neste dia. A chave única no dia garante
    uma rodada só entre processos (sem cache compartilhado configurado)."""

    dia = models.DateField(unique=True)
    iniciada_em = models.DateTimeField(auto_now_add=True)
    resultado = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "rotina do dia"
        verbose_name_plural = "rotinas do dia"

    def __str__(self) -> str:
        return f"Rotinas de {self.dia:%d/%m/%Y}"


class AssinaturaAgenda(models.Model):
    """O link pessoal do feed iCalendar da agenda (A2c). Guarda só o hash do token: o link
    aparece uma vez, ao gerar; gerar de novo invalida o anterior; revogar apaga; trocar a
    senha também invalida (selo)."""

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="assinatura_agenda")
    token_hash = models.CharField(max_length=64, unique=True)
    # Impressão da senha na hora de gerar: trocou a senha, o link deixa de valer.
    selo = models.CharField(max_length=32)
    gerada_em = models.DateTimeField()
    usada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "assinatura da agenda"
        verbose_name_plural = "assinaturas da agenda"

    def __str__(self) -> str:
        return f"Assinatura da agenda de {self.usuario}"
