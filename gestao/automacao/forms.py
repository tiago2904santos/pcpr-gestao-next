"""Formulários das telas da automação (validação; as regras ficam nos serviços)."""

from __future__ import annotations

from typing import cast

from django import forms

from gestao.cadastros.models import Servidor

from . import dominio
from .models import ChaveAutomacao, ContatoVerificado


class FormularioContato(forms.Form):
    servidor: forms.ModelChoiceField[Servidor] = forms.ModelChoiceField(
        label="Servidor", queryset=None, empty_label="Escolha o servidor",
        help_text="Só aparecem servidores com telefone no cadastro e sem contato vigente.")

    def __init__(self, *args, servidores=None, **kwargs):
        super().__init__(*args, **kwargs)
        cast(forms.ModelChoiceField, self.fields["servidor"]).queryset = servidores


class FormularioOptin(forms.Form):
    origem = forms.ChoiceField(
        label="Como a pessoa concordou", choices=[
            (ContatoVerificado.OrigemOptin.FORMULARIO, "Assinou o termo de participação"),
            (ContatoVerificado.OrigemOptin.PRESENCIAL, "Concordou pessoalmente comigo")])
    confirmo = forms.BooleanField(
        label="Confirmo que a pessoa aceitou receber mensagens deste sistema de testes",
        required=True)


class FormularioRevogar(forms.Form):
    motivo = forms.CharField(label="Motivo", max_length=120,
                             help_text="Ex.: a pessoa pediu para sair do teste.")


class FormularioTestador(forms.Form):
    telefone = forms.CharField(
        label="WhatsApp do testador", max_length=20,
        help_text="Com DDD; o 55 do Brasil é colocado sozinho.",
        widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "off",
                                      "data-mascara": "telefone"}))
    descricao = forms.CharField(label="Quem é", max_length=120,
                                help_text="Ex.: Testador 1 — responsável pelo piloto.")
    valido_ate = forms.DateField(label="Vale até", required=False,
                                 help_text="Em branco: até alguém remover.",
                                 input_formats=["%d/%m/%Y", "%Y-%m-%d"])

    def clean_telefone(self) -> str:
        e164 = dominio.e164_do_brasil(self.cleaned_data["telefone"])
        if not e164:
            raise forms.ValidationError("Informe um celular brasileiro com DDD.")
        return e164


class FormularioChave(forms.Form):
    nome = forms.CharField(widget=forms.HiddenInput, max_length=80)
    estado = forms.ChoiceField(label="Estado", choices=[
        (ChaveAutomacao.Estado.DESLIGADA, "Desligada"), (ChaveAutomacao.Estado.LIGADA, "Ligada")])
    modo = forms.ChoiceField(label="Modo", choices=ChaveAutomacao.Modo.choices, required=False)
    motivo = forms.CharField(label="Motivo", max_length=255, required=False)


class FormularioResposta(forms.Form):
    texto = forms.CharField(label="Resposta", max_length=1000, widget=forms.Textarea(
        attrs={"rows": 4}), help_text="Sai pelo WhatsApp dentro da janela de 24 h da mensagem.")


class FormularioSimularResposta(forms.Form):
    texto = forms.CharField(label="Texto da mensagem", max_length=1000, required=False,
                            widget=forms.Textarea(attrs={"rows": 2}))
    arquivo = forms.FileField(label="Arquivo (comprovante fictício)", required=False,
                              help_text="PDF, JPG ou PNG de até 10 MB — use só arquivos de teste.")

    def clean(self):
        super().clean()
        dados = self.cleaned_data  # o que Form.clean devolve
        if not dados.get("texto") and not dados.get("arquivo"):
            raise forms.ValidationError("Escreva um texto ou escolha um arquivo.")
        return dados
