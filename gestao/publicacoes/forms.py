"""Formulários do controle de publicações.

Horários aceitam a grafia da planilha ("17h03", "16h") além de "17:03". Uma unidade ainda
não cadastrada pode ser informada direto na pauta ("outra unidade"). Bitly, SESP e AEN são
Sim / Não / em branco, como na planilha.
"""

from __future__ import annotations

from datetime import time
from typing import Any, cast

from django import forms

from gestao.plataforma.widgets import FORMATOS_DATA, EntradaData, Selecao

from . import dominio
from .models import Integrante, Publicacao, UnidadeResponsavel

FORM_ID = "form-pauta"
SIM_NAO = [("", "—"), ("1", "Sim"), ("0", "Não")]


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


class CampoSimNao(forms.NullBooleanField):
    """Sim / Não / — com os valores "1" / "0" / "" (seleção do design system)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("required", False)
        kwargs.setdefault("widget", Selecao(choices=SIM_NAO))
        super().__init__(**kwargs)

    def to_python(self, value: Any) -> bool | None:  # type: ignore[override]
        if value in ("1", 1, True, "True", "true"):
            return True
        if value in ("0", 0, False, "False", "false"):
            return False
        return None

    def prepare_value(self, value: Any) -> str:
        if value in (True, "1", "True", "true"):
            return "1"
        if value in (False, "0", "False", "false"):
            return "0"
        return ""


class FormularioPauta(forms.ModelForm):
    data = forms.DateField(  # type: ignore[assignment]  # campo "data" do modelo
        label="Data da pauta", input_formats=FORMATOS_DATA, widget=EntradaData())
    inicio_pauta = CampoHora(label="Início da pauta")
    colocada_edicao = CampoHora(label="Colocada para edição")
    data_publicacao = forms.DateField(label="Data de publicação", required=False,
                                      input_formats=FORMATOS_DATA, widget=EntradaData())
    horario_publicacao = CampoHora(label="Horário de publicação")
    bitly_grupos = CampoSimNao(label="Bitly nos grupos")
    enviado_sesp = CampoSimNao(label="Enviado para a SESP")
    publicado_aen = CampoSimNao(label="Publicado na AEN")
    unidade_nova = forms.CharField(
        label="Outra unidade (não listada)", required=False, max_length=150,
        widget=forms.TextInput(attrs=_attrs(placeholder="Ex.: DP de Irati",
                                            autocomplete="off")),
        help_text="Só se a unidade ainda não estiver na lista: ela entra no cadastro.")

    class Meta:
        model = Publicacao
        fields = ["data", "jornalista", "unidade", "fonte", "inicio_pauta", "titulo",
                  "colocada_edicao", "data_publicacao", "horario_publicacao", "revisao",
                  "galeria_fotos", "bitly_grupos", "enviado_sesp", "publicado_aen",
                  "link_site", "link_aen"]
        labels = {"jornalista": "Jornalista", "unidade": "Unidade responsável",
                  "titulo": "Título da pauta", "fonte": "Fonte da pauta",
                  "revisao": "Revisão", "galeria_fotos": "Galeria de fotos",
                  "link_site": "Link no site da PCPR", "link_aen": "Link na AEN"}
        widgets = {
            "jornalista": Selecao(), "unidade": Selecao(), "revisao": Selecao(),
            "galeria_fotos": Selecao(),
            "titulo": forms.TextInput(attrs=_attrs(autocomplete="off",
                                                   placeholder="Como vai sair no site")),
            "fonte": forms.TextInput(attrs=_attrs(
                autocomplete="off", placeholder="Quem passou a informação")),
            "link_site": forms.URLInput(attrs=_attrs(placeholder="https://…",
                                                     inputmode="url")),
            "link_aen": forms.URLInput(attrs=_attrs(placeholder="https://…",
                                                    inputmode="url")),
        }
        help_texts = {"fonte": "Delegado, investigador ou assessoria."}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for nome, vazio in (("jornalista", "Quem cuida da pauta"), ("revisao", "Quem revisou"),
                            ("galeria_fotos", "Quem fez a galeria")):
            campo = cast(forms.ModelChoiceField, self.fields[nome])
            campo.queryset = Integrante.objects.order_by("nome")
            campo.empty_label = vazio
        unidade = cast(forms.ModelChoiceField, self.fields["unidade"])
        unidade.queryset = UnidadeResponsavel.objects.order_by("nome")
        unidade.empty_label = "Escolha a unidade"
        unidade.required = False
        for campo_form in self.fields.values():
            campo_form.widget.attrs.setdefault("form", FORM_ID)

    def clean(self) -> dict[str, Any]:
        dados = super().clean() or {}
        if not dados.get("unidade") and not (dados.get("unidade_nova") or "").strip():
            self.add_error("unidade", dominio.MSG_UNIDADE)
        try:
            dominio.conferir_datas(self.instance.status, dados.get("data"),
                                   dados.get("data_publicacao"))
        except dominio.RegraViolada as exc:
            self.add_error(exc.campo, str(exc))
        return dados


class FormularioAndamento(forms.Form):
    novo_status = forms.ChoiceField(label="Novo status", choices=Publicacao.Status.choices,
                                    widget=forms.RadioSelect)
    anotacao = forms.CharField(
        label="Andamento", required=False, max_length=4000,
        widget=forms.Textarea(attrs=_attrs(
            rows=3, placeholder="O que aconteceu: redação pronta, aguardando revisão, "
                                "publicada no site…")))
