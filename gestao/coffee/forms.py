"""Formulários dos cadastros do Coffee Break (CB1): validação como na referência (CNPJ de 14
dígitos, vigência, lote único, trava de versão) e PDF conferido pelo conteúdo."""

from __future__ import annotations

from typing import Any

from django import forms

from gestao.cadastros.models import Municipio
from gestao.plataforma.widgets import FORMATOS_DATA, EntradaData, Selecao

from . import dominio
from .models import ConfiguracaoOficio, Contrato, Fornecedor, Lote, TermoAditivo

TAMANHO_MAXIMO_PDF = 10 * 1024 * 1024
MSG_PDF = "Envie o arquivo em PDF."
MSG_PDF_GRANDE = "O PDF passa de 10 MB."


def versao_de(obj) -> str:
    return obj.atualizado_em.isoformat() if obj is not None and obj.pk and obj.atualizado_em \
        else ""


def _entrada(**attrs: Any) -> forms.TextInput:
    return forms.TextInput(attrs={"class": "entrada", "autocomplete": "off", **attrs})


def _texto(linhas: int = 3) -> forms.Textarea:
    return forms.Textarea(attrs={"class": "entrada", "rows": linhas})


def conferir_pdf(arquivo):
    """Só PDF de verdade (pelos primeiros bytes), até 10 MB."""
    if not arquivo or not hasattr(arquivo, "read"):
        return arquivo
    if getattr(arquivo, "size", 0) > TAMANHO_MAXIMO_PDF:
        raise forms.ValidationError(MSG_PDF_GRANDE)
    inicio = arquivo.read(5)
    arquivo.seek(0)
    if not str(getattr(arquivo, "name", "")).lower().endswith(".pdf") or inicio != b"%PDF-":
        raise forms.ValidationError(MSG_PDF)
    return arquivo


class CampoContrato(forms.ModelChoiceField):
    """O contrato com o fornecedor na escolha ("Contrato 45/2024 · Café & Cia")."""

    def label_from_instance(self, obj) -> str:
        return f"Contrato {obj.numero} · {obj.fornecedor.razao_social}"


def _campo_contrato() -> CampoContrato:
    return CampoContrato(queryset=Contrato.objects.select_related("fornecedor"),
                         label="Contrato")


class ComVersao(forms.ModelForm):
    """Trava de versão: o formulário leva o `atualizado_em` de quando a tela abriu."""

    versao = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial["versao"] = versao_de(self.instance)
        for nome, campo in self.fields.items():
            if isinstance(campo.widget, (forms.TextInput, forms.EmailInput, forms.URLInput,
                                         forms.NumberInput)):
                campo.widget.attrs.setdefault("class", "entrada")
                campo.widget.attrs.setdefault("autocomplete", "off")
            if isinstance(campo, forms.DateField):
                campo.widget = EntradaData()
                campo.input_formats = FORMATOS_DATA
            if isinstance(campo, forms.ModelChoiceField) and not isinstance(
                    campo, forms.ModelMultipleChoiceField):
                campo.widget = Selecao()
                campo.widget.choices = campo.choices
            if isinstance(campo, forms.DecimalField):
                # Vírgula decimal, como se digita aqui (o campo numérico do navegador não a
                # aceita).
                campo.localize = True
                campo.widget = forms.TextInput(attrs={"class": "entrada", "autocomplete": "off",
                                                      "inputmode": "decimal"})
                campo.widget.is_localized = True
            elif nome.startswith("quantidade") or nome.startswith("antecedencia"):
                campo.widget.attrs.setdefault("inputmode", "numeric")

    def clean(self):
        dados = super().clean()
        if self.instance.pk and (dados or {}).get("versao") != versao_de(self.instance):
            raise forms.ValidationError(dominio.MSG_VERSAO)
        return dados


class FormularioFornecedor(ComVersao):
    cnpj = forms.CharField(label="CNPJ", max_length=18, required=False,
                           widget=_entrada(inputmode="numeric", placeholder="00.000.000/0000-00"))

    class Meta:
        model = Fornecedor
        fields = ["razao_social", "nome_curto", "cnpj", "contato", "telefone", "email",
                  "portal_certidao_municipal"]

    def clean_razao_social(self) -> str:
        nome = " ".join((self.cleaned_data.get("razao_social") or "").split())
        if Fornecedor.objects.filter(razao_social__iexact=nome).exclude(
                pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe um fornecedor com esta razão social.")
        return nome

    def clean_cnpj(self) -> str:
        try:
            cnpj = dominio.normalizar_cnpj(self.cleaned_data.get("cnpj"))
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from None
        if cnpj and Fornecedor.objects.filter(cnpj=cnpj).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe um fornecedor com este CNPJ.")
        return cnpj


class FormularioContrato(ComVersao):
    class Meta:
        model = Contrato
        fields = ["fornecedor", "numero", "numero_gms", "termo_aditivo", "vigencia_inicio",
                  "vigencia_fim", "vigencia_estimada", "quantidade_contratada", "valor_unitario",
                  "valor_total", "antecedencia_minima_dias", "fiscal", "cargo_fiscal",
                  "clausula_pagamento", "arquivo", "objeto", "observacoes"]
        widgets = {"objeto": _texto(), "observacoes": _texto(2),
                   "arquivo": forms.ClearableFileInput(attrs={"accept": "application/pdf"})}

    def clean_numero(self) -> str:
        numero = (self.cleaned_data.get("numero") or "").strip()
        if Contrato.objects.filter(numero__iexact=numero).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe um contrato com este número.")
        return numero

    def clean_arquivo(self):
        return conferir_pdf(self.cleaned_data.get("arquivo"))

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("vigencia_inicio"), dados.get("vigencia_fim")
        if inicio and fim and fim < inicio:
            self.add_error("vigencia_fim", dominio.MSG_VIGENCIA)
        return dados


class FormularioAditivo(ComVersao):
    contrato = _campo_contrato()

    class Meta:
        model = TermoAditivo
        fields = ["contrato", "numero", "vigencia_inicio", "vigencia_fim", "arquivo"]
        widgets = {"arquivo": forms.ClearableFileInput(attrs={"accept": "application/pdf"})}

    def clean_arquivo(self):
        return conferir_pdf(self.cleaned_data.get("arquivo"))

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("vigencia_inicio"), dados.get("vigencia_fim")
        if inicio and fim and fim < inicio:
            self.add_error("vigencia_fim", dominio.MSG_VIGENCIA)
        contrato, numero = dados.get("contrato"), (dados.get("numero") or "").strip()
        if contrato and numero and TermoAditivo.objects.filter(
                contrato=contrato, numero__iexact=numero).exclude(pk=self.instance.pk).exists():
            self.add_error("numero", "Este contrato já tem um termo aditivo com este número.")
        return dados


class FormularioLote(ComVersao):
    contrato = _campo_contrato()
    lista_municipios = forms.CharField(
        label="Municípios abrangidos", required=False, widget=_texto(3),
        help_text="Nomes dos municípios do Paraná, separados por vírgula ou linha. Pedidos "
                  "desses municípios caem neste lote.")

    class Meta:
        model = Lote
        fields = ["contrato", "numero", "exercicio", "quantidade_total", "empenho",
                  "valor_empenho", "ativo", "orientacoes", "especificacoes", "observacoes"]
        widgets = {"orientacoes": _texto(), "especificacoes": _texto(), "observacoes": _texto(2)}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance.pk:
            self.initial["lista_municipios"] = ", ".join(
                m.nome for m in self.instance.municipios.order_by("nome"))
        self.municipios_resolvidos: list[Municipio] = []

    def clean_lista_municipios(self) -> str:
        texto = self.cleaned_data.get("lista_municipios") or ""
        nomes = dominio.separar_municipios(texto)
        do_parana = {dominio.chave_de_nome(m.nome): m
                     for m in Municipio.objects.filter(uf="PR").only("pk", "nome")}
        faltando = [n for n in nomes if dominio.chave_de_nome(n) not in do_parana]
        if faltando:
            raise forms.ValidationError(dominio.MSG_MUNICIPIOS.format(lista=", ".join(faltando)))
        self.municipios_resolvidos = [do_parana[dominio.chave_de_nome(n)] for n in nomes]
        return texto

    def clean(self):
        dados = super().clean()
        contrato, numero = dados.get("contrato"), dados.get("numero")
        exercicio = (dados.get("exercicio") or "").strip()
        if contrato and numero and exercicio and Lote.objects.filter(
                contrato=contrato, numero=numero, exercicio=exercicio).exclude(
                pk=self.instance.pk).exists():
            self.add_error("numero", f"O Lote {numero} ({exercicio}) deste contrato já existe.")
        total = dados.get("quantidade_total")
        if self.instance.pk and total:
            from .queries import consumido_por_lote
            consumido = consumido_por_lote([self.instance.pk]).get(self.instance.pk, 0)
            if total < consumido:
                self.add_error("quantidade_total", f"O lote já consumiu {consumido} unidades; "
                                                   "a capacidade não pode ficar abaixo disso.")
        return dados


class FormularioConfiguracao(ComVersao):
    class Meta:
        model = ConfiguracaoOficio
        fields = ["vocativo", "assinante", "cargo_assinante", "destinatario",
                  "destino_despacho", "assunto_protocolo", "palavras_chave", "emails_ascom",
                  "assunto_email_os", "texto_email_os", "assunto_email_ob", "texto_email_ob"]
        widgets = {"destinatario": _texto(4), "texto_email_os": _texto(6),
                   "texto_email_ob": _texto(6)}

    def clean_emails_ascom(self) -> str:
        validar = forms.EmailField().clean
        enderecos = [e.strip() for e in (self.cleaned_data.get("emails_ascom") or "").split(",")
                     if e.strip()]
        for e in enderecos:
            try:
                validar(e)
            except forms.ValidationError:
                raise forms.ValidationError(f"E-mail inválido: {e}") from None
        return ", ".join(enderecos)
