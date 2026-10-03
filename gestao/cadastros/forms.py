"""Formulários dos cadastros de apoio."""

from __future__ import annotations

from django import forms

from gestao.plataforma.widgets import Selecao

from .models import ModeloTexto
from .textos import TIPOS_EDITAVEIS


class FormularioTexto(forms.Form):
    tipo = forms.ChoiceField(
        label="Onde é usado",
        choices=[(t.value, t.label) for t in TIPOS_EDITAVEIS], widget=Selecao())
    nome = forms.CharField(
        label="Nome", max_length=120,
        help_text="Curto, para achar na lista. Ex.: “Apoio da Unidade Móvel”.",
        widget=forms.TextInput(attrs={"class": "entrada", "autocomplete": "off"}))
    ordem = forms.IntegerField(
        label="Ordem", min_value=0, max_value=32767, initial=100,
        help_text="Menor aparece primeiro.",
        widget=forms.NumberInput(attrs={"class": "entrada", "inputmode": "numeric"}))
    texto = forms.CharField(
        label="Texto", max_length=4000,
        help_text="Entra no campo exatamente como escrito; dá para ajustar depois de inserir.",
        widget=forms.Textarea(attrs={"class": "area-texto", "rows": 6}))

    @classmethod
    def de(cls, modelo: ModeloTexto) -> FormularioTexto:
        return cls(initial={"tipo": modelo.tipo, "nome": modelo.nome, "ordem": modelo.ordem,
                            "texto": modelo.texto})
