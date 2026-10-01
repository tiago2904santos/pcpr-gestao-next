"""Cadastros de apoio ao módulo Viagens.

Redesenhados a partir do comportamento observado no sistema de referência
(docs/product/entities.md). Toda tabela é auditada por trigger (migração 0002).
"""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower

from .validacoes import formatar_cpf, formatar_placa


class Ativavel(models.Model):
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Unidade(Ativavel):
    sigla = models.CharField("sigla", max_length=40)
    nome = models.CharField("nome", max_length=255)

    class Meta:
        ordering = ["sigla"]
        constraints = [models.UniqueConstraint(Lower("nome"), name="unidade_nome_unico")]

    def __str__(self) -> str:
        return self.sigla or self.nome


class Cargo(Ativavel):
    nome = models.CharField("nome", max_length=120)

    class Meta:
        ordering = ["nome"]
        constraints = [models.UniqueConstraint(Lower("nome"), name="cargo_nome_unico")]

    def __str__(self) -> str:
        return self.nome


class Combustivel(Ativavel):
    nome = models.CharField("nome", max_length=60)

    class Meta:
        ordering = ["nome"]
        verbose_name = "combustível"
        verbose_name_plural = "combustíveis"

    def __str__(self) -> str:
        return self.nome


class Servidor(Ativavel):
    """Servidor público que viaja (viajante, motorista ou signatário)."""

    nome = models.CharField("nome completo", max_length=255)
    cpf = models.CharField("CPF", max_length=11, blank=True)
    rg = models.CharField("RG", max_length=30, blank=True)
    cargo = models.ForeignKey(Cargo, on_delete=models.PROTECT, related_name="servidores")
    unidade = models.ForeignKey(Unidade, on_delete=models.PROTECT, related_name="servidores")
    telefone = models.CharField("telefone", max_length=11, blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name_plural = "servidores"
        constraints = [
            models.UniqueConstraint(
                fields=["cpf"], condition=~models.Q(cpf=""), name="servidor_cpf_unico"
            ),
            models.CheckConstraint(
                condition=models.Q(cpf="") | models.Q(cpf__regex=r"^\d{11}$"),
                name="servidor_cpf_11_digitos",
            ),
        ]
        indexes = [models.Index(Lower("nome"), name="servidor_nome_idx")]

    def __str__(self) -> str:
        return self.nome

    @property
    def cpf_formatado(self) -> str:
        return formatar_cpf(self.cpf)

    @property
    def iniciais(self) -> str:
        partes = [p for p in self.nome.split() if len(p) > 2] or self.nome.split()
        return (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()


class Viatura(Ativavel):
    class Tipo(models.TextChoices):
        CARACTERIZADA = "caracterizada", "Caracterizada"
        DESCARACTERIZADA = "descaracterizada", "Descaracterizada"

    placa = models.CharField("placa", max_length=7, unique=True)
    modelo = models.CharField("modelo", max_length=120)
    combustivel = models.ForeignKey(Combustivel, on_delete=models.PROTECT)
    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices)
    unidade = models.ForeignKey(
        Unidade, on_delete=models.PROTECT, null=True, blank=True, related_name="viaturas"
    )

    class Meta:
        ordering = ["placa"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(placa__regex=r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$"),
                name="viatura_placa_formato",
            )
        ]

    def __str__(self) -> str:
        return f"{self.placa_formatada} · {self.modelo}"

    @property
    def placa_formatada(self) -> str:
        return formatar_placa(self.placa)


class Municipio(models.Model):
    """Município brasileiro (IBGE). Capital e DF determinam a faixa de diária."""

    codigo_ibge = models.CharField("código IBGE", max_length=7, unique=True)
    nome = models.CharField("nome", max_length=120)
    uf = models.CharField("UF", max_length=2)
    capital = models.BooleanField("capital do estado", default=False)

    class Meta:
        ordering = ["nome"]
        indexes = [models.Index(Lower("nome"), "uf", name="municipio_nome_uf_idx")]

    def __str__(self) -> str:
        return f"{self.nome}/{self.uf}"


class TabelaDiaria(models.Model):
    """Valor da diária de 24h por faixa de destino, com vigência.

    Os percentuais (15% e 30%) não são digitados: são derivados do valor de
    24h pela regra de domínio (`viagens.dominio.diarias.valor_percentual`).
    """

    class Faixa(models.TextChoices):
        INTERIOR = "interior", "Interior"
        CAPITAL = "capital", "Capital"
        BRASILIA = "brasilia", "Brasília"

    faixa = models.CharField("faixa", max_length=10, choices=Faixa.choices)
    vigente_desde = models.DateField("vigente a partir de")
    valor_24h = models.DecimalField(
        "diária de 24 horas", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    norma = models.CharField("norma de referência", max_length=200, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["faixa", "-vigente_desde"]
        verbose_name = "vigência de diária"
        verbose_name_plural = "tabela de diárias"
        constraints = [
            models.UniqueConstraint(fields=["faixa", "vigente_desde"], name="diaria_vigencia_unica"),
            models.CheckConstraint(condition=models.Q(valor_24h__gt=0), name="diaria_valor_positivo"),
        ]

    def __str__(self) -> str:
        return f"{self.get_faixa_display()} desde {self.vigente_desde:%d/%m/%Y}"


class ConfiguracaoInstitucional(models.Model):
    """Dados da unidade emissora usados nos ofícios (cabeçalho, rodapé, destinatário).

    Uma linha por unidade emissora; o operador emite pela configuração da sua unidade.
    """

    unidade = models.OneToOneField(Unidade, on_delete=models.PROTECT, related_name="configuracao")
    nome_extenso = models.CharField("nome da unidade no cabeçalho", max_length=160)
    sede = models.ForeignKey(Municipio, on_delete=models.PROTECT, verbose_name="cidade sede")
    endereco_rodape = models.CharField("endereço no rodapé", max_length=255)
    chefia_nome = models.CharField("nome da chefia (signatário)", max_length=150)
    chefia_cargo = models.CharField("cargo da chefia", max_length=150)
    destinatario_tratamento = models.CharField("tratamento", max_length=40, default="Exmo. Sr")
    destinatario_nome = models.CharField("destinatário", max_length=150)
    destinatario_cargo = models.CharField("cargo do destinatário", max_length=150)
    destinatario_orgao = models.CharField("órgão de destino", max_length=160)
    destinatario_cidade = models.CharField("cidade do destinatário", max_length=80,
                                           default="CURITIBA – Pr.")
    prazo_justificativa_dias = models.PositiveSmallIntegerField(
        "antecedência mínima (dias)", default=10,
        help_text="Viagens com menos dias de antecedência exigem justificativa.",
    )

    class Meta:
        verbose_name = "configuração institucional"
        verbose_name_plural = "configurações institucionais"

    def __str__(self) -> str:
        return f"Configuração de {self.unidade}"
