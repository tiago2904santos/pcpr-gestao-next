"""Coffee Break (ASCOM): os cadastros contratuais — fornecedor, contrato, termo aditivo, lote
e a configuração do ofício ao GAF (paridade com `coffee_break/models.py` da referência;
especificação em docs/migration/coffee-break.md). As solicitações (ordens de serviço) e o
fluxo de pagamento entram nas fatias seguintes (CB2+)."""

from __future__ import annotations

from datetime import date

from django.db import models
from django.db.models.functions import Lower

from . import dominio


class Carimbos(models.Model):
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Fornecedor(Carimbos):
    razao_social = models.CharField("razão social", max_length=200)
    nome_curto = models.CharField(
        "nome curto", max_length=60, blank=True,
        help_text="Vai no detalhamento do protocolo. Em branco, usa a razão social sem "
                  "LTDA/EIRELI/ME/EPP/S.A.")
    cnpj = models.CharField("CNPJ", max_length=14, blank=True)
    contato = models.CharField("contato", max_length=150, blank=True)
    telefone = models.CharField("telefone", max_length=30, blank=True)
    email = models.EmailField("e-mail", blank=True,
                              help_text="Para onde vão a ordem de serviço e a ordem bancária.")
    portal_certidao_municipal = models.URLField(
        "portal da certidão municipal", max_length=300, blank=True,
        help_text="Endereço da prefeitura da sede onde se emite a certidão municipal.")

    class Meta:
        ordering = ["razao_social"]
        verbose_name = "fornecedor"
        verbose_name_plural = "fornecedores"
        permissions = [("acessar_coffee", "Acessar o Coffee Break")]
        constraints = [
            models.UniqueConstraint(Lower("razao_social"), name="coffee_fornecedor_razao_unica"),
            models.UniqueConstraint(fields=["cnpj"], condition=~models.Q(cnpj=""),
                                    name="coffee_fornecedor_cnpj_unico"),
        ]

    def __str__(self) -> str:
        return self.razao_social

    @property
    def nome_para_documentos(self) -> str:
        return self.nome_curto.strip() or dominio.nome_curto(self.razao_social)

    @property
    def cnpj_formatado(self) -> str:
        return dominio.formatar_cnpj(self.cnpj)


class Contrato(Carimbos):
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.PROTECT, related_name="contratos")
    numero = models.CharField("número", max_length=30)
    numero_gms = models.CharField("número GMS", max_length=30, blank=True)
    termo_aditivo = models.CharField(
        "termo aditivo em vigor", max_length=30, blank=True,
        help_text="Número que os documentos citam. Os termos aditivos ficam na aba própria.")
    fiscal = models.CharField("fiscal do contrato", max_length=150, blank=True)
    cargo_fiscal = models.CharField("cargo do fiscal", max_length=120, blank=True,
                                    default="Agente de Polícia Judiciária")
    clausula_pagamento = models.CharField("cláusula do pagamento", max_length=120, blank=True,
                                          default="Cláusula Décima, item 10.2.6")
    arquivo = models.FileField("PDF do contrato", upload_to="coffee/contratos/%Y/", blank=True)
    vigencia_inicio = models.DateField("início da vigência", null=True, blank=True)
    vigencia_fim = models.DateField("fim da vigência", null=True, blank=True)
    vigencia_estimada = models.BooleanField(
        "vigência estimada", default=False,
        help_text="Marque quando o fim foi calculado pelo prazo (o termo aditivo confirma).")
    quantidade_contratada = models.PositiveIntegerField("quantidade contratada", null=True,
                                                        blank=True)
    valor_unitario = models.DecimalField("valor unitário", max_digits=12, decimal_places=4,
                                         null=True, blank=True)
    valor_total = models.DecimalField("valor total", max_digits=14, decimal_places=2, null=True,
                                      blank=True)
    antecedencia_minima_dias = models.PositiveSmallIntegerField(
        "antecedência mínima do pedido (dias)", default=2)
    objeto = models.TextField("objeto", blank=True)
    observacoes = models.TextField("observações", blank=True)

    class Meta:
        ordering = ["-vigencia_fim", "numero"]
        verbose_name = "contrato"
        verbose_name_plural = "contratos"
        constraints = [models.UniqueConstraint(fields=["numero"], name="coffee_contrato_numero"),
                       models.CheckConstraint(
                           condition=(models.Q(vigencia_inicio__isnull=True)
                                      | models.Q(vigencia_fim__isnull=True)
                                      | models.Q(vigencia_fim__gte=models.F("vigencia_inicio"))),
                           name="coffee_contrato_vigencia_valida")]

    def __str__(self) -> str:
        return f"Contrato {self.numero}"

    @property
    def referencia_documental(self) -> str:
        return dominio.referencia_documental(self.numero, self.numero_gms, self.termo_aditivo)

    def fim_efetivo(self) -> date | None:
        """O maior fim entre o contrato e os termos aditivos."""
        fins = [a.vigencia_fim for a in self.aditivos.all() if a.vigencia_fim]
        return dominio.fim_efetivo(self.vigencia_fim, fins)


class TermoAditivo(Carimbos):
    contrato = models.ForeignKey(Contrato, on_delete=models.PROTECT, related_name="aditivos")
    numero = models.CharField("número", max_length=30)
    arquivo = models.FileField("PDF do termo aditivo", upload_to="coffee/aditivos/%Y/",
                               blank=True)
    vigencia_inicio = models.DateField("início da vigência", null=True, blank=True)
    vigencia_fim = models.DateField("fim da vigência", null=True, blank=True)

    class Meta:
        ordering = ["contrato__numero", "vigencia_fim", "numero"]
        verbose_name = "termo aditivo"
        verbose_name_plural = "termos aditivos"
        constraints = [models.UniqueConstraint(fields=["contrato", "numero"],
                                               name="coffee_aditivo_numero_por_contrato")]

    def __str__(self) -> str:
        return f"Termo aditivo {self.numero} ({self.contrato})"


class Lote(Carimbos):
    contrato = models.ForeignKey(Contrato, on_delete=models.PROTECT, related_name="lotes")
    numero = models.PositiveIntegerField("número")
    exercicio = models.CharField("exercício", max_length=9, help_text="Ex.: 2026.")
    quantidade_total = models.PositiveIntegerField("quantidade total (unidades)")
    empenho = models.CharField("empenho", max_length=60, blank=True)
    valor_empenho = models.DecimalField("valor do empenho", max_digits=14, decimal_places=2,
                                        null=True, blank=True)
    municipios = models.ManyToManyField("cadastros.Municipio", blank=True, related_name="+",
                                        verbose_name="municípios abrangidos")
    municipios_texto = models.TextField("municípios (texto original)", blank=True)
    orientacoes = models.TextField("orientações", blank=True)
    especificacoes = models.TextField("especificações técnicas", blank=True)
    observacoes = models.TextField("observações", blank=True)
    ativo = models.BooleanField("lote vigente", default=True,
                                help_text="Só lotes vigentes recebem pedidos pelo município.")

    class Meta:
        ordering = ["-exercicio", "numero"]
        verbose_name = "lote"
        verbose_name_plural = "lotes"
        constraints = [
            models.UniqueConstraint(fields=["contrato", "numero", "exercicio"],
                                    name="coffee_lote_unico"),
            models.CheckConstraint(condition=models.Q(quantidade_total__gte=1),
                                   name="coffee_lote_quantidade_positiva"),
        ]

    def __str__(self) -> str:
        return f"Lote {self.numero} ({self.exercicio})"


class ConfiguracaoOficio(Carimbos):
    """Registro único: o que o ofício ao GAF, o protocolo e os e-mails ao fornecedor usam.
    Nasce com valores neutros (sem nomes de pessoas)."""

    vocativo = models.CharField("vocativo do ofício", max_length=150, blank=True,
                                default="Senhor(a) Diretor(a),")
    assinante = models.CharField("quem assina o ofício", max_length=150, blank=True)
    cargo_assinante = models.CharField("cargo de quem assina", max_length=150, blank=True)
    destinatario = models.TextField("destinatário (uma linha por linha)", blank=True)
    assunto_protocolo = models.CharField("assunto do protocolo", max_length=120, blank=True,
                                         default="LICITACAO")
    palavras_chave = models.CharField("palavras-chave do protocolo", max_length=200,
                                      blank=True, default="REGISTRO DE PRECO")
    destino_despacho = models.CharField("destino do despacho", max_length=120, blank=True,
                                        default="Ao GAF,")
    emails_ascom = models.CharField(
        "e-mail da ASCOM em cópia", max_length=500, blank=True,
        help_text="Vários separados por vírgula.")
    assunto_email_os = models.CharField(
        "assunto do e-mail da ordem de serviço", max_length=200, blank=True,
        default="Ordem de Serviço {numero} — {evento}")
    texto_email_os = models.TextField(
        "texto do e-mail da ordem de serviço", blank=True,
        default="Prezados,\n\nSegue a Ordem de Serviço {numero} para o evento {evento}, em "
                "{data} às {horario}, em {local}, para {quantidade} pessoas. Responsável pelo "
                "recebimento: {responsavel}.\n\nAtenciosamente,\nASCOM/PCPR")
    assunto_email_ob = models.CharField(
        "assunto do e-mail da ordem bancária", max_length=200, blank=True,
        default="Ordem bancária — Ordem de Serviço {numero}")
    texto_email_ob = models.TextField(
        "texto do e-mail da ordem bancária", blank=True,
        default="Prezados,\n\nInformamos o pagamento da nota fiscal {nota} referente à Ordem "
                "de Serviço {numero} ({evento}), pela ordem bancária {ordem_bancaria} de "
                "{data_ordem_bancaria}. Segue o comprovante.\n\nAtenciosamente,\nASCOM/PCPR")

    class Meta:
        verbose_name = "configuração do ofício"
        verbose_name_plural = "configuração do ofício"

    def __str__(self) -> str:
        return "Configuração do ofício e do protocolo"

    @classmethod
    def atual(cls) -> ConfiguracaoOficio:
        obj = cls.objects.order_by("pk").first()
        return obj if obj is not None else cls.objects.create()


# A solicitação mora em models_pedido.py; importada aqui para o Django registrar os modelos.
from .models_pedido import Movimento, Solicitacao, Via  # noqa: E402

__all__ = ["Carimbos", "ConfiguracaoOficio", "Contrato", "Fornecedor", "Lote", "Movimento",
           "Solicitacao", "TermoAditivo", "Via"]
