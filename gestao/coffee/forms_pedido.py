"""Formulário da solicitação de coffee break, etapa 1 (CB2): o evento e a ordem de serviço.
Com o financeiro iniciado, os dados do pedido e do evento ficam travados (referência)."""

from __future__ import annotations

import re

from django import forms
from django.utils import timezone

from gestao.cadastros.forms import CampoMunicipio
from gestao.plataforma.widgets import FORMATOS_DATA, EntradaData, EntradaHora

from . import dominio_pedido as regras

FORM_ID = "form-coffee"
TRAVADOS = ("municipio", "data_solicitacao", "numero", "descricao", "quantidade", "data_evento")
MSG_TRAVADOS = ("Os dados do pedido e do evento foram bloqueados porque a nota fiscal já foi "
                "registrada. Os dados da ordem de serviço continuam editáveis.")


def _entrada(**attrs) -> forms.TextInput:
    return forms.TextInput(attrs={"class": "entrada", "autocomplete": "off", "form": FORM_ID,
                                  **attrs})


def versao_de(s) -> str:
    return s.atualizado_em.isoformat() if s is not None and s.pk else ""


class FormularioSolicitacao(forms.Form):
    municipio = CampoMunicipio(label="Município do evento", help_text=(
        "Cidade/PR. O lote (e o fornecedor) vem do município."))
    data_solicitacao = forms.DateField(label="Data da solicitação", input_formats=FORMATOS_DATA,
                                       widget=EntradaData(attrs={"form": FORM_ID}))
    numero = forms.CharField(label="Nº da OS", required=False, max_length=20,
                             widget=_entrada(inputmode="numeric"),
                             help_text="Só a sequência; o ano vem da data da solicitação. Em "
                                       "branco, o próximo livre.")
    descricao = forms.CharField(label="Descrição do evento (objeto da OS)", max_length=1000,
                                widget=forms.Textarea(attrs={"class": "entrada", "rows": 2,
                                                             "form": FORM_ID}))
    quantidade = forms.IntegerField(label="Quantidade de pessoas", min_value=1,
                                    error_messages={"min_value": regras.MSG_QUANTIDADE},
                                    widget=forms.NumberInput(attrs={
                                        "class": "entrada", "inputmode": "numeric",
                                        "form": FORM_ID}))
    data_evento = forms.DateField(label="Data do evento", required=False,
                                  input_formats=FORMATOS_DATA,
                                  widget=EntradaData(attrs={"form": FORM_ID}))
    horario = forms.TimeField(label="Horário", required=False,
                              widget=EntradaHora(attrs={"form": FORM_ID}))
    local_entrega = forms.CharField(label="Local de entrega", required=False, max_length=255,
                                    widget=_entrada())
    endereco = forms.CharField(label="Endereço", required=False, max_length=255,
                               widget=_entrada())
    bairro = forms.CharField(label="Bairro", required=False, max_length=120, widget=_entrada())
    cep = forms.CharField(label="CEP", required=False, max_length=9,
                          widget=_entrada(inputmode="numeric", placeholder="00000-000",
                                          **{"data-mascara": "cep"}))
    responsavel = forms.CharField(label="Responsável pelo recebimento", required=False,
                                  max_length=200, widget=_entrada(),
                                  help_text="Nome e telefone de quem recebe no local.")
    retroativo = forms.BooleanField(
        label="Registro retroativo", required=False,
        widget=forms.CheckboxInput(attrs={"form": FORM_ID}),
        help_text="Marque quando o evento já aconteceu antes da data da solicitação.")
    justificativa = forms.CharField(label="Justificativa do registro retroativo",
                                    required=False, max_length=255, widget=_entrada())
    versao = forms.CharField(required=False, widget=forms.HiddenInput(attrs={"form": FORM_ID}))
    duplicada_de = forms.IntegerField(required=False,
                                      widget=forms.HiddenInput(attrs={"form": FORM_ID}))

    def __init__(self, *args, solicitacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.solicitacao = solicitacao
        self.fields["municipio"].widget.attrs["form"] = FORM_ID
        if not self.is_bound:
            self.initial.setdefault("data_solicitacao", timezone.localdate())
            if solicitacao is not None:
                for nome in ("data_solicitacao", "descricao", "quantidade", "data_evento",
                             "horario", "local_entrega", "endereco", "bairro", "cep",
                             "responsavel"):
                    self.initial[nome] = getattr(solicitacao, nome)
                self.initial["municipio"] = (f"{solicitacao.municipio.nome}/"
                                             f"{solicitacao.municipio.uf}")
                self.initial["numero"] = solicitacao.numero.partition("/")[0]
                self.initial["versao"] = versao_de(solicitacao)
        self.travado = bool(solicitacao is not None and solicitacao.financeiro_iniciado)
        if self.travado:
            for nome in TRAVADOS:
                self.fields[nome].disabled = True
                self.fields[nome].required = False
        if solicitacao is not None and solicitacao.bloqueada:
            for campo in self.fields.values():
                campo.disabled = True

    def clean_municipio(self):
        m = self.cleaned_data.get("municipio")
        if m is not None and m.uf != "PR":
            raise forms.ValidationError("Escolha um município do Paraná.")
        return m

    def clean_cep(self) -> str:
        cep = re.sub(r"\D", "", self.cleaned_data.get("cep") or "")
        if cep and len(cep) != 8:
            raise forms.ValidationError("O CEP tem 8 dígitos (00000-000).")
        return f"{cep[:5]}-{cep[5:]}" if cep else ""

    def clean(self):
        dados = super().clean() or {}
        s = self.solicitacao
        if s is not None and s.pk and dados.get("versao") != versao_de(s):
            raise forms.ValidationError(regras.MSG_VERSAO)
        if self.travado and s is not None:  # travados: valem os gravados
            for nome in TRAVADOS:
                dados[nome] = getattr(s, nome) if nome != "numero" else s.numero
        return dados
