"""Widgets de formulário do design system: data, hora, data + hora e seleção.

Sem JavaScript são campos de texto/seleção comuns (dd/mm/aaaa, hh:mm, <select>). Com
JavaScript, os componentes <pc-data>, <pc-hora> e <pc-select> acrescentam calendário,
relógio e lista própria — nunca o seletor nativo do navegador.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django import forms
from django.utils import timezone

FORMATO_DATA = "%d/%m/%Y"
FORMATO_HORA = "%H:%M"
FORMATOS_DATA = [FORMATO_DATA, "%Y-%m-%d"]
FORMATOS_DATA_HORA = [f"{FORMATO_DATA} {FORMATO_HORA}", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"]


def _com(base: dict[str, str], attrs: dict[str, Any] | None) -> dict[str, Any]:
    return {"class": "entrada", **base, **(attrs or {})}


class EntradaData(forms.DateInput):
    """dd/mm/aaaa digitável (máscara) + calendário próprio (<pc-data>)."""

    template_name = "plataforma/widgets/data.html"

    def __init__(self, attrs: dict[str, Any] | None = None):
        super().__init__(attrs=_com({
            "inputmode": "numeric", "placeholder": "dd/mm/aaaa", "autocomplete": "off",
            "maxlength": "10", "data-mascara": "data"}, attrs), format=FORMATO_DATA)


class EntradaHora(forms.TimeInput):
    """hh:mm digitável (máscara) + relógio próprio (<pc-hora>)."""

    template_name = "plataforma/widgets/hora.html"

    def __init__(self, attrs: dict[str, Any] | None = None):
        super().__init__(attrs=_com({
            "inputmode": "numeric", "placeholder": "hh:mm", "autocomplete": "off",
            "maxlength": "5", "data-mascara": "hora"}, attrs), format=FORMATO_HORA)


class EntradaDataHora(forms.MultiWidget):
    """Data e hora lado a lado, como no sistema de referência. O valor continua sendo um
    único campo: `nome_0` (data) e `nome_1` (hora) chegam juntos como "dd/mm/aaaa hh:mm".
    Também aceita o envio antigo num campo só (`nome` = "aaaa-mm-ddThh:mm")."""

    template_name = "plataforma/widgets/data_hora.html"

    def __init__(self, attrs: dict[str, Any] | None = None):
        super().__init__([EntradaData(), EntradaHora()], attrs)

    def decompress(self, value: Any) -> list[Any]:
        if not value:
            return [None, None]
        if isinstance(value, str):  # reapresentação após erro: o texto como foi digitado
            for formato in FORMATOS_DATA_HORA:
                try:
                    value = datetime.strptime(value.strip(), formato)
                    break
                except ValueError:
                    continue
            else:
                partes = value.split(" ", 1)
                return [partes[0], partes[1] if len(partes) > 1 else ""]
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return [value.date(), value.time()]

    def get_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:
        contexto = super().get_context(name, value, attrs)
        base = contexto["widget"]["attrs"].get("id", "")
        contexto["widget"]["id_base"] = base
        if base:  # nome acessível: "<rótulo do campo> data" / "<rótulo do campo> hora"
            for sufixo, sub in zip(("data", "hora"), contexto["widget"]["subwidgets"],
                                   strict=True):
                sub["attrs"]["aria-labelledby"] = f"{base}-rotulo {base}-{sufixo}"
        return contexto

    def value_from_datadict(self, data, files, name: str) -> Any:
        if f"{name}_0" in data or f"{name}_1" in data:
            data_txt = (data.get(f"{name}_0") or "").strip()
            hora_txt = (data.get(f"{name}_1") or "").strip()
            return f"{data_txt} {hora_txt}".strip()
        return data.get(name)

    def value_omitted_from_data(self, data, files, name: str) -> bool:
        return name not in data and f"{name}_0" not in data and f"{name}_1" not in data


class Selecao(forms.Select):
    """<select> comum + lista própria (<pc-select>)."""

    template_name = "plataforma/widgets/selecao.html"

    def __init__(self, attrs: dict[str, Any] | None = None, choices=()):
        final = {**(attrs or {})}
        final["class"] = final.get("class") or "selecao"
        super().__init__(attrs=final, choices=choices)


class SelecaoDeTexto(Selecao):
    """Escolha de "texto pronto": cada opção leva o próprio texto em `data-texto`, para o
    componente `texto-pronto.js` preencher o campo ao escolher (sem ida ao servidor).

    Serve a qualquer modelo com atributo `texto` (motivo, justificativa, RT, despacho…).
    """

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcao = super().create_option(name, value, label, selected, index, subindex, attrs)
        instancia = getattr(value, "instance", None)
        texto = getattr(instancia, "texto", None)
        if texto:
            opcao["attrs"]["data-texto"] = texto
        return opcao


class EscolhaMultiplaRemota(forms.SelectMultiple):
    """Vários registros escolhidos por busca (<pc-multiescolha>): cada escolhido vira uma
    linha com um <input type="hidden"> do mesmo nome, e a busca consulta `fonte`
    (JSON [{id, titulo, meta}], o mesmo do <pc-combobox> remoto).

    Só os já escolhidos são desenhados (nunca a lista inteira de opções). Sem JavaScript, os
    escolhidos continuam sendo enviados; acrescentar pede JavaScript.
    """

    template_name = "plataforma/widgets/escolha_multipla.html"

    def __init__(self, *, fonte: str = "", rotulo_vazio: str = "Nada escolhido.",
                 placeholder: str = "", attrs: dict[str, Any] | None = None):
        super().__init__(attrs=attrs)
        self.fonte, self.rotulo_vazio, self.placeholder = fonte, rotulo_vazio, placeholder

    def get_context(self, name, value, attrs):
        # forms.Widget (e não SelectMultiple): não percorre todas as opções do campo.
        contexto = forms.Widget.get_context(self, name, value, attrs)
        consulta = getattr(self.choices, "queryset", None)
        if consulta is None:  # modo texto: o próprio valor é o que se mostra (ex.: "Cidade/UF")
            itens = [{"id": v, "titulo": v, "meta": ""} for v in contexto["widget"]["value"]]
        else:
            valores = [v for v in contexto["widget"]["value"]
                       if str(v).isascii() and str(v).isdecimal() and len(str(v)) <= 18]
            itens = [{"id": o.pk, "titulo": str(o), "meta": getattr(o, "descricao", "")}
                     for o in (consulta.filter(pk__in=valores) if valores else [])]
        contexto["widget"].update({
            "fonte": self.fonte, "rotulo_vazio": self.rotulo_vazio,
            "placeholder": self.placeholder, "escolhidos": itens})
        return contexto

    def format_value(self, value):
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            value = [value]
        return [str(getattr(v, "pk", v)) for v in value if v not in (None, "")]


class CaixasDeEscolha(forms.CheckboxSelectMultiple):
    """Vários itens de uma lista curta por caixas de seleção em grade (`.caixas`), com o
    desenho das caixas do design system. O rótulo do grupo é a `<legend>` de quem usa."""

    template_name = "plataforma/widgets/caixas.html"
