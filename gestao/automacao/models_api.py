"""Modelos da API de automação v1 (contrato docs/automacao/contratos/api-automacao.v1.yaml) e
do registro de ferramentas (ADR 0020): credenciais por integração, idempotência, delegação
emitida pelo PCPR, execuções de ferramenta, pedidos de aprovação e eventos para o n8n.

Credencial e delegação só existem como hash: o valor em claro aparece uma vez, na criação.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q


class CredencialIntegracao(models.Model):
    """Token de serviço (transporte do n8n, IA) ou pessoal (cliente MCP), com escopos mínimos,
    ambiente fixo, validade, rotação e modo emergência."""

    class Tipo(models.TextChoices):
        TRANSPORTE = "transporte", "Transporte (n8n)"
        IA = "ia", "IA (ferramentas com delegação)"
        PESSOAL = "pessoal", "Pessoal (age como o próprio usuário)"

    nome = models.CharField(max_length=80)
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    prefixo = models.CharField(max_length=24)  # parte visível, para reconhecer na tela
    token_hash = models.CharField(max_length=64, unique=True)
    ambiente = models.CharField(max_length=12)
    escopos = models.JSONField(default=list)
    ferramentas = models.JSONField(default=list, blank=True)  # só para tipo IA
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
                                blank=True, related_name="+")  # dono do token pessoal
    criada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="+")
    criada_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    revogada_em = models.DateTimeField(null=True, blank=True)
    revogada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     null=True, blank=True, related_name="+")
    emergencia = models.BooleanField(default=False)
    substitui = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True,
                                  related_name="substituida_por")
    ultimo_uso_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criada_em"]
        constraints = [
            models.CheckConstraint(condition=~Q(tipo="pessoal") | Q(usuario__isnull=False),
                                   name="credencial_pessoal_tem_dono"),
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.prefixo}…)"


class RegistroIdempotencia(models.Model):
    """Resposta guardada de um POST: repetir a chave com a mesma requisição devolve a mesma
    resposta; com outra requisição, 422. Só 2xx e 409 são guardados (contrato)."""

    credencial = models.ForeignKey(CredencialIntegracao, on_delete=models.CASCADE,
                                   related_name="+")
    chave = models.CharField(max_length=200)
    rota = models.CharField(max_length=120)
    impressao = models.CharField(max_length=64)
    status = models.PositiveSmallIntegerField()
    corpo = models.JSONField(default=dict)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)  # limpeza

    class Meta:
        constraints = [models.UniqueConstraint(fields=["credencial", "chave"],
                                               name="idempotencia_unica")]

    def __str__(self) -> str:
        return f"Idempotência {self.chave}"


class Delegacao(models.Model):
    """Agir em nome de alguém exige delegação emitida pelo PCPR no momento da ação humana:
    usuário, ferramentas, recurso, validade curta, uso único, para uma credencial."""

    token_hash = models.CharField(max_length=64, unique=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="+")
    credencial = models.ForeignKey(CredencialIntegracao, on_delete=models.PROTECT,
                                   related_name="delegacoes")
    ferramentas = models.JSONField(default=list)
    recurso = models.CharField(max_length=80, blank=True)
    motivo = models.CharField(max_length=200)
    criada_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    usada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criada_em"]

    def __str__(self) -> str:
        return f"Delegação #{self.pk}"


class ExecucaoFerramenta(models.Model):
    """Toda execução de ferramenta: quem (usuário efetivo), por qual credencial e delegação,
    com que entrada (resumida, sem dado pessoal) e resultado."""

    class Resultado(models.TextChoices):
        OK = "ok", "Executada"
        NEGADA = "negada", "Negada"
        PENDENTE = "pendente", "Aguardando aprovação"
        ERRO = "erro", "Erro"
        SOMBRA = "sombra", "Simulada (modo sombra)"

    ferramenta = models.CharField(max_length=80)
    versao = models.PositiveSmallIntegerField(default=1)
    risco = models.CharField(max_length=12)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                null=True, blank=True, related_name="+")
    credencial = models.ForeignKey(CredencialIntegracao, on_delete=models.PROTECT, null=True,
                                   blank=True, related_name="execucoes")
    delegacao = models.ForeignKey(Delegacao, on_delete=models.PROTECT, null=True, blank=True,
                                  related_name="execucoes")
    origem = models.CharField(max_length=12, default="api")  # api | tela | ia
    entrada = models.JSONField(default=dict)
    resultado = models.CharField(max_length=10, choices=Resultado.choices)
    detalhe = models.CharField(max_length=255, blank=True)
    duracao_ms = models.PositiveIntegerField(null=True, blank=True)
    correlacao = models.CharField(max_length=120, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criada_em", "-id"]

    def __str__(self) -> str:
        return f"{self.ferramenta} #{self.pk}"


class PedidoAprovacao(models.Model):
    """Ação irreversível pedida por automação: só uma pessoa com permissão aprova, na tela."""

    class Situacao(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        APROVADO = "aprovado", "Aprovado e executado"
        RECUSADO = "recusado", "Recusado"
        FALHOU = "falhou", "Aprovado, mas a execução falhou"
        EXPIRADO = "expirado", "Expirado"

    ferramenta = models.CharField(max_length=80)
    entrada = models.JSONField(default=dict)
    resumo = models.CharField(max_length=255)
    recurso = models.CharField(max_length=80, blank=True)
    unidade = models.ForeignKey("cadastros.Unidade", on_delete=models.PROTECT, null=True,
                                blank=True, related_name="+")
    pedido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   null=True, blank=True, related_name="+")
    execucao = models.OneToOneField(ExecucaoFerramenta, on_delete=models.PROTECT,
                                    related_name="aprovacao")
    situacao = models.CharField(max_length=10, choices=Situacao.choices,
                                default=Situacao.PENDENTE)
    decidido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     null=True, blank=True, related_name="+")
    decidido_em = models.DateTimeField(null=True, blank=True)
    motivo = models.CharField(max_length=255, blank=True)
    expira_em = models.DateTimeField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em", "-id"]

    def __str__(self) -> str:
        return f"Pedido de aprovação #{self.pk}"


class EventoIntegracao(models.Model):
    """Evento PCPR → n8n (envelope `evento-integracao.schema.json`), entregue por um worker
    com lease, assinado com HMAC, pela rede interna. Nasce na transação da mudança."""

    class Situacao(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        ENTREGANDO = "entregando", "Entregando"
        ENTREGUE = "entregue", "Entregue"
        FALHOU = "falhou", "Falhou"
        CONFIGURACAO = "configuracao", "Recusado pelo destino (configuração)"

    uuid = models.UUIDField(unique=True)
    tipo = models.CharField(max_length=80)
    corpo = models.JSONField()
    situacao = models.CharField(max_length=14, choices=Situacao.choices,
                                default=Situacao.PENDENTE)
    tentativas = models.PositiveSmallIntegerField(default=0)
    disponivel_em = models.DateTimeField()
    reservado_ate = models.DateTimeField(null=True, blank=True)
    entregue_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em", "id"]
        indexes = [models.Index(fields=["situacao", "disponivel_em"], name="evento_fila_idx")]

    def __str__(self) -> str:
        return f"Evento {self.tipo} #{self.pk}"
