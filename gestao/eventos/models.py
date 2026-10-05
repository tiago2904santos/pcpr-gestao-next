"""Eventos Sociais — catálogos de apoio das solicitações de evento (paridade com o app
`cadastros` da referência; ver docs/migration/eventos-sociais.md).

Todos têm nome único (sem diferença de maiúsculas) e "ativo": o inativo sai dos
formulários novos, mas continua nas solicitações que já o usam (e o que está em uso não
pode ser excluído — só inativado). O tipo de evento guarda o "modelo da solicitação":
solicitante, cargo/unidade e órgão padrão, serviços sugeridos e equipes com quantidade.
"""

from __future__ import annotations

from django.db import models
from django.db.models.functions import Lower


class Catalogo(models.Model):
    nome = models.CharField("nome", max_length=150)
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Servico(Catalogo):
    class Meta(Catalogo.Meta):
        verbose_name = "serviço"
        verbose_name_plural = "serviços"
        constraints = [models.UniqueConstraint(Lower("nome"), name="eventos_servico_nome")]


class Equipe(Catalogo):
    class Meta(Catalogo.Meta):
        verbose_name = "equipe"
        verbose_name_plural = "equipes"
        constraints = [models.UniqueConstraint(Lower("nome"), name="eventos_equipe_nome")]


class OrgaoResponsavel(Catalogo):
    class Meta(Catalogo.Meta):
        verbose_name = "órgão responsável"
        verbose_name_plural = "órgãos responsáveis"
        constraints = [models.UniqueConstraint(Lower("nome"), name="eventos_orgao_nome")]


class UnidadeMovel(Catalogo):
    class Meta(Catalogo.Meta):
        verbose_name = "unidade móvel"
        verbose_name_plural = "unidades móveis"
        constraints = [models.UniqueConstraint(Lower("nome"), name="eventos_unidade_movel_nome")]


class TextoDespacho(Catalogo):
    """Texto pronto do despacho da DG: o nome é o rótulo do botão; o texto, o que entra."""

    texto = models.TextField("texto")

    class Meta(Catalogo.Meta):
        verbose_name = "texto pronto do despacho"
        verbose_name_plural = "textos prontos do despacho"
        constraints = [models.UniqueConstraint(Lower("nome"), name="eventos_texto_nome")]


class TipoEvento(Catalogo):
    """Tipo de evento, com o modelo da solicitação (o que já vem preenchido)."""

    solicitante_padrao = models.CharField("solicitante padrão", max_length=150, blank=True)
    cargo_padrao = models.CharField("cargo / unidade padrão", max_length=255, blank=True)
    orgao_padrao = models.ForeignKey(OrgaoResponsavel, verbose_name="órgão padrão",
                                     on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="+")
    servicos_sugeridos = models.ManyToManyField(Servico, verbose_name="serviços sugeridos",
                                                blank=True, related_name="+")

    class Meta(Catalogo.Meta):
        verbose_name = "tipo de evento"
        verbose_name_plural = "tipos de evento"
        constraints = [models.UniqueConstraint(Lower("nome"), name="eventos_tipo_nome")]

    @property
    def tem_modelo(self) -> bool:
        return bool(self.solicitante_padrao or self.cargo_padrao or self.orgao_padrao_id
                    or self.servicos_sugeridos.exists() or self.equipes_padrao.exists())


class TipoEventoEquipe(models.Model):
    """Equipe do modelo do tipo de evento, com a quantidade de servidores."""

    tipo_evento = models.ForeignKey(TipoEvento, on_delete=models.CASCADE,
                                    related_name="equipes_padrao")
    equipe = models.ForeignKey(Equipe, on_delete=models.CASCADE, related_name="+")
    quantidade = models.PositiveIntegerField("quantidade de servidores", null=True, blank=True)

    class Meta:
        ordering = ["equipe__nome"]
        verbose_name = "equipe do modelo"
        verbose_name_plural = "equipes do modelo"
        constraints = [models.UniqueConstraint(fields=["tipo_evento", "equipe"],
                                               name="eventos_tipo_equipe_unica")]

    def __str__(self) -> str:
        return f"{self.tipo_evento} — {self.equipe}"
