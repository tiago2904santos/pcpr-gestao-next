"""Formulários do Ofício. Mensagens dizem o que fazer, não só o que está errado."""

from __future__ import annotations

import re
from datetime import datetime
from typing import cast

from django import forms
from django.contrib.postgres.lookups import Unaccent
from django.db.models import Value
from django.db.models.functions import Lower
from django.utils import timezone

from gestao.cadastros.models import Combustivel, ModeloTexto, Municipio, Viatura
from gestao.cadastros.validacoes import normalizar_placa, placa_valida, somente_digitos
from gestao.plataforma.widgets import (
    FORMATOS_DATA,
    FORMATOS_DATA_HORA,
    EntradaData,
    EntradaDataHora,
    Selecao,
)

from .models import Oficio
from .queries import trechos_de

FORM_ID = "form-oficio"


def _attrs(classe: str = "entrada", **extra) -> dict:
    return {"class": classe, **extra}


class AssociadoAoFormularioDoOficio:
    """Os campos ficam espalhados pelas seções da página e se ligam ao <form id="form-oficio">
    pelo atributo HTML `form` — assim a seção Equipe pode ter formulários próprios (HTMX)
    sem aninhar <form> (HTML inválido)."""

    def _associar(self) -> None:
        for campo in self.fields.values():  # type: ignore[attr-defined]
            campo.widget.attrs["form"] = FORM_ID


def resolver_municipio(texto: str) -> Municipio:
    """Aceita "Cidade/UF", "Cidade - UF" ou "Cidade, UF" (sem diferenciar acentos/caixa)."""
    texto = (texto or "").strip()
    m = re.match(r"^(?P<nome>.+?)\s*[/,-]\s*(?P<uf>[A-Za-z]{2})$", texto)
    if not m:
        raise forms.ValidationError(
            "Informe a cidade e a UF, ex.: Arapongas/PR.", code="formato_municipio")
    nome, uf = m.group("nome").strip(), m.group("uf").upper()
    candidatos = list(
        Municipio.objects.annotate(n=Unaccent(Lower("nome")))
        .filter(uf=uf, n=Unaccent(Lower(Value(nome))))[:2]
    )
    if len(candidatos) != 1:
        raise forms.ValidationError(
            f"Não encontramos “{nome}/{uf}” na lista oficial de municípios. Confira a grafia.",
            code="municipio_inexistente")
    return candidatos[0]


class CampoMunicipio(forms.CharField):
    """Texto "Cidade/UF" resolvido para Municipio (funciona sem JavaScript)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("widget", forms.TextInput(attrs=_attrs(
            placeholder="Cidade/UF", autocomplete="off", **{"data-municipio": ""})))
        super().__init__(**kwargs)

    def clean(self, value):
        value = super().clean(value)
        if not value:
            return None
        return resolver_municipio(value)


class CampoDataHora(forms.DateTimeField):
    def __init__(self, **kwargs):
        kwargs.setdefault("widget", EntradaDataHora())
        kwargs.setdefault("input_formats", FORMATOS_DATA_HORA)
        kwargs.setdefault("error_messages", {
            "invalid": "Informe data e hora, ex.: 08/10/2026 09:00.",
            "required": "Informe data e hora."})
        super().__init__(**kwargs)


class FormularioOficio(AssociadoAoFormularioDoOficio, forms.ModelForm):
    """Seções Dados, Transporte e Justificativa (equipe e roteiro têm formulários próprios)."""

    versao = forms.IntegerField(widget=forms.HiddenInput, required=False)
    protocolo = forms.CharField(
        label="Protocolo (eProtocolo)", required=False, max_length=14,
        help_text="Nove dígitos, com ou sem pontuação (ex.: 12.345.678-9).",
        # Sem placeholder: em cinza parecia valor preenchido (revisão de UX, QA-2); a ajuda
        # já mostra o formato.
        widget=forms.TextInput(attrs=_attrs(inputmode="numeric",
                                            **{"data-mascara": "protocolo"})),
    )

    class Meta:
        model = Oficio
        fields = ["data_oficio", "protocolo", "marcador", "motivo", "custeio",
                  "custeio_instituicao", "tipo_transporte", "viatura", "transporte_descricao",
                  "transporte_placa", "transporte_combustivel", "porte_arma",
                  "justificativa_modelo", "justificativa"]
        widgets = {
            "data_oficio": EntradaData(),
            "marcador": forms.RadioSelect,
            "motivo": forms.Textarea(attrs=_attrs("area-texto", rows=3,
                                                  placeholder="Ex.: Apoio e condução da Unidade "
                                                              "Móvel no evento Expoara.")),
            "custeio": forms.RadioSelect,
            "custeio_instituicao": forms.TextInput(attrs=_attrs()),
            "tipo_transporte": forms.RadioSelect,
            "viatura": forms.Select(attrs=_attrs("selecao")),
            "transporte_descricao": forms.TextInput(attrs=_attrs(
                placeholder="Ex.: Ônibus de linha, veículo cedido…")),
            "transporte_placa": forms.TextInput(attrs=_attrs(placeholder="Ex.: ABC1D23")),
            "transporte_combustivel": Selecao(),
            "justificativa_modelo": Selecao(),
            "justificativa": forms.Textarea(attrs=_attrs("area-texto", rows=5)),
        }
        labels = {"motivo": "Motivo da viagem", "justificativa_modelo": "Texto pronto",
                  "viatura": "Viatura", "transporte_combustivel": "Combustível"}
        help_texts = {
            "motivo": "Aparece no ofício exatamente como escrito.",
            "porte_arma": "Marque se os servidores transportarão arma de fogo.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        viatura = cast(forms.ModelChoiceField, self.fields["viatura"])
        viatura.queryset = Viatura.objects.filter(ativo=True).select_related("combustivel")
        viatura.empty_label = "Selecione a viatura…"
        combustivel = cast(forms.ModelChoiceField, self.fields["transporte_combustivel"])
        combustivel.queryset = Combustivel.objects.filter(ativo=True)
        combustivel.required = False
        combustivel.empty_label = "Selecione…"
        modelo = cast(forms.ModelChoiceField, self.fields["justificativa_modelo"])
        modelo.queryset = ModeloTexto.objects.filter(ativo=True,
                                                     tipo=ModeloTexto.Tipo.JUSTIFICATIVA)
        modelo.empty_label = "Escrever do zero"
        self.fields["porte_arma"].widget.attrs.update({"class": "", "role": "switch"})
        data = cast(forms.DateField, self.fields["data_oficio"])
        data.input_formats = FORMATOS_DATA
        data.error_messages["invalid"] = "Informe a data no formato dd/mm/aaaa, ex.: 08/10/2026."
        if self.instance.pk:
            self.fields["versao"].initial = self.instance.versao
            self.initial["protocolo"] = self.instance.protocolo_formatado
        self._associar()

    def clean_protocolo(self):
        digitos = somente_digitos(self.cleaned_data.get("protocolo"))
        if digitos and len(digitos) != 9:
            raise forms.ValidationError(
                f"O protocolo tem 9 dígitos; você informou {len(digitos)}.")
        return digitos

    def clean_transporte_placa(self):
        placa = normalizar_placa(self.cleaned_data.get("transporte_placa"))
        if placa and not placa_valida(placa):
            raise forms.ValidationError("Placa inválida. Use o formato ABC1234 ou ABC1D23.")
        return placa

    def clean(self):
        super().clean()
        dados = self.cleaned_data
        if (dados.get("custeio") == Oficio.Custeio.OUTRA_INSTITUICAO
                and not dados.get("custeio_instituicao")):
            self.add_error("custeio_instituicao", "Informe qual instituição custeia a viagem.")
        if dados.get("justificativa_modelo") and not (dados.get("justificativa") or "").strip():
            dados["justificativa"] = dados["justificativa_modelo"].texto
        return dados


class FormularioDestino(AssociadoAoFormularioDoOficio, forms.Form):
    cidade = CampoMunicipio(label="Cidade de destino")
    saida = CampoDataHora(label="Saída")
    chegada = CampoDataHora(label="Chegada")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._associar()

    def clean(self):
        super().clean()
        dados = self.cleaned_data
        if dados.get("saida") and dados.get("chegada") and dados["chegada"] <= dados["saida"]:
            self.add_error("chegada", "A chegada precisa ser depois da saída.")
        return dados


class FormularioRetorno(AssociadoAoFormularioDoOficio, forms.Form):
    saida = CampoDataHora(label="Saída para a sede")
    chegada = CampoDataHora(label="Chegada na sede")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._associar()

    def clean(self):
        super().clean()
        dados = self.cleaned_data
        if dados.get("saida") and dados.get("chegada") and dados["chegada"] <= dados["saida"]:
            self.add_error("chegada", "A chegada precisa ser depois da saída.")
        return dados


ConjuntoDestinos = forms.formset_factory(FormularioDestino, extra=0, min_num=1,
                                         validate_min=True, max_num=10, validate_max=True,
                                         can_delete=True)


def iniciais_do_roteiro(oficio: Oficio) -> tuple[list[dict], dict]:
    """Valores iniciais dos formulários de roteiro a partir dos trechos gravados."""
    trechos = trechos_de(oficio)

    def local(dt: datetime) -> str:
        return timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M")

    # O último trecho que chega à sede é o retorno; todos os anteriores (inclusive
    # passagens intermediárias pela sede, como no bate-volta) são "destinos".
    volta = trechos[-1] if trechos and trechos[-1].destino_id == oficio.sede_id else None
    ida = trechos[:-1] if volta else trechos
    destinos = [{"cidade": f"{t.destino.nome}/{t.destino.uf}", "saida": local(t.saida_em),
                 "chegada": local(t.chegada_em)} for t in ida] or [{}]
    retorno = {"saida": local(volta.saida_em), "chegada": local(volta.chegada_em)} if volta \
        else {}
    return destinos, retorno
