"""Correspondência "linha do sistema antigo → linha deste sistema" (uma por origem).

Não é `cadastros.VinculoFonteCadastro`: aquele trava a edição e a exclusão do cadastro; este é
só o mapa da migração, consultado pelas etapas seguintes e por quem conferir a carga.
"""

from __future__ import annotations

from django.db import models


class MapaLegado(models.Model):
    class Sistema(models.TextChoices):
        EVENTOS = "ev", "Eventos Sociais"
        VIAGENS = "gv", "Gerenciador de Viagens"

    sistema = models.CharField(max_length=2, choices=Sistema.choices)
    tabela = models.CharField(max_length=100)          # tabela de origem
    origem_pk = models.CharField(max_length=64)
    modelo = models.CharField(max_length=100)          # "app_label.Modelo" de destino
    destino_pk = models.CharField(max_length=64)
    criado = models.BooleanField(default=True)         # False = casou com um registro existente
    lote = models.CharField(max_length=40)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "correspondência da migração"
        verbose_name_plural = "correspondências da migração"
        constraints = [models.UniqueConstraint(fields=["sistema", "tabela", "origem_pk"],
                                               name="mapa_legado_origem_unica")]
        indexes = [models.Index(fields=["modelo", "destino_pk"], name="mapa_legado_destino_idx")]

    def __str__(self) -> str:
        return f"{self.sistema}:{self.tabela}:{self.origem_pk} → {self.modelo}:{self.destino_pk}"
