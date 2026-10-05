"""Formulários do atendimento à imprensa.

Horários aceitam "17h03", "16h" ou "17:03" (como na planilha). Um veículo ainda não
cadastrado pode ser informado direto no atendimento ("outro veículo").
"""

from __future__ import annotations

from datetime import time
from typing import Any, cast

from django import forms

from gestao.plataforma.widgets import FORMATOS_DATA, EntradaData, Selecao

from . import dominio
from .models import Atendimento, Integrante, Veiculo

FORM_ID = "form-atendimento"


def _attrs(**extra: Any) -> dict[str, Any]:
    return {"class": "entrada", **extra}


class CampoHora(forms.CharField):
    """Hora escrita à mão: "17h03", "16h", "17:03"."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("required", False)
        kwargs.setdefault("max_length", 8)
        kwargs.setdefault("widget", forms.TextInput(attrs=_attrs(
            placeholder="hh:mm", inputmode="numeric", autocomplete="off")))
        super().__init__(**kwargs)

    def prepare_value(self, value: Any) -> Any:
        return value.strftime("%H:%M") if isinstance(value, time) else value

    def clean(self, value: Any) -> time | None:
        texto = super().clean(value)
        if not texto:
            return None
        hora = dominio.ler_hora(texto)
        if hora is None:
            raise forms.ValidationError("Use hh:mm (ex.: 17:03 ou 17h03).")
        return hora


class FormularioAtendimento(forms.ModelForm):
    data = forms.DateField(  # type: ignore[assignment]  # campo "data" do modelo
        label="Data do pedido", input_formats=FORMATOS_DATA, widget=EntradaData())
    horario = CampoHora(label="Horário do pedido")
    deadline = forms.DateField(label="Deadline / veiculação", required=False,
                               input_formats=FORMATOS_DATA, widget=EntradaData(),
                               help_text="Até quando o veículo precisa da resposta.")
    horario_resposta = CampoHora(label="Horário da resposta")
    veiculo_novo = forms.CharField(
        label="Outro veículo (não listado)", required=False, max_length=150,
        widget=forms.TextInput(attrs=_attrs(placeholder="Ex.: Rádio Clube",
                                            autocomplete="off")),
        help_text="Só se o veículo ainda não estiver na lista: ele entra no cadastro.")

    class Meta:
        model = Atendimento
        fields = ["data", "horario", "jornalista", "veiculo", "contato", "pedido",
                  "responsavel", "deadline", "horario_resposta", "responsavel_resposta",
                  "fonte", "inicio_pedido", "final_pedido", "resposta"]
        labels = {"fonte": "Fontes", "resposta": "Resposta enviada"}
        widgets = {
            "jornalista": forms.TextInput(attrs=_attrs(autocomplete="off",
                                                       placeholder="Nome de quem pediu",
                                                       list="jornalistas")),
            "contato": forms.TextInput(attrs=_attrs(placeholder="Telefone ou e-mail",
                                                    autocomplete="off")),
            "veiculo": Selecao(),
            "responsavel": Selecao(),
            "responsavel_resposta": Selecao(),
            "pedido": forms.Textarea(attrs=_attrs(
                rows=4, placeholder="O que o jornalista pediu, com os dados do caso.")),
            "fonte": forms.Textarea(attrs=_attrs(rows=4,
                                                 placeholder="Del. Fulano\n\nAscom DPCAP")),
            "inicio_pedido": forms.Textarea(attrs=_attrs(rows=4, placeholder="09h12\n\n09h40")),
            "final_pedido": forms.Textarea(attrs=_attrs(rows=4, placeholder="09h30\n\n10h05")),
            "resposta": forms.Textarea(attrs=_attrs(rows=6,
                                                    placeholder="Texto enviado ao jornalista.")),
        }
        help_texts = {
            "fonte": "Uma fonte por bloco, separados por uma linha em branco.",
            "inicio_pedido": "Quando cada fonte foi acionada, na mesma ordem.",
            "final_pedido": "Quando cada fonte respondeu, na mesma ordem.",
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        veiculo = cast(forms.ModelChoiceField, self.fields["veiculo"])
        veiculo.queryset = Veiculo.objects.order_by("nome")
        veiculo.empty_label = "Escolha o veículo"
        for nome, vazio in (("responsavel", "Quem atendeu"),
                            ("responsavel_resposta", "Quem respondeu")):
            campo = cast(forms.ModelChoiceField, self.fields[nome])
            campo.queryset = Integrante.objects.order_by("nome")
            campo.empty_label = vazio
        for campo_form in self.fields.values():
            campo_form.widget.attrs.setdefault("form", FORM_ID)

    def clean(self) -> dict[str, Any]:
        dados = super().clean() or {}
        if erro := dominio.conferir_deadline(dados.get("data"), dados.get("deadline")):
            self.add_error("deadline", erro)
        return dados


class FormularioAndamento(forms.Form):
    nova_situacao = forms.ChoiceField(label="Nova situação",
                                      choices=Atendimento.Situacao.choices,
                                      widget=forms.RadioSelect)
    anotacao = forms.CharField(
        label="Andamento", required=False, max_length=4000,
        widget=forms.Textarea(attrs=_attrs(
            rows=3, placeholder="O que aconteceu: fonte acionada, aguardando o delegado, "
                                "resposta enviada…")))
