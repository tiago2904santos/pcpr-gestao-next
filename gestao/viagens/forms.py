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
    EntradaHora,
    Selecao,
)

from .models import Oficio, Roteiro
from .queries import trechos_de

FORM_ID = "form-oficio"


def _attrs(classe: str = "entrada", **extra) -> dict:
    return {"class": classe, **extra}


class FiltrosOficio(forms.Form):
    """Gaveta "Mais filtros" da lista de ofícios — o que a busca por texto não resolve.

    Destino, servidor e número ficaram na busca de cima (ela já pergunta "é destino ou
    servidor?"); aqui ficam os cortes: período, protocolo, veículo e valor de diárias.
    Tudo é opcional, e valor inválido é ignorado em vez de dar erro — uma lista nunca deve
    recusar a busca de quem está procurando.
    """

    # O período é um campo só na tela (<pc-data data-periodo>): estes dois levam as pontas.
    saida_de = forms.DateField(required=False, input_formats=FORMATOS_DATA,
                               widget=forms.HiddenInput(attrs={"data-periodo-de": ""}))
    saida_ate = forms.DateField(required=False, input_formats=FORMATOS_DATA,
                                widget=forms.HiddenInput(attrs={"data-periodo-ate": ""}))
    protocolo = forms.CharField(label="Protocolo", required=False, max_length=20,
                                widget=forms.TextInput(attrs=_attrs(
                                    inputmode="numeric", placeholder="00.366.136-8")))
    veiculo = forms.ChoiceField(
        label="Veículo", required=False, widget=Selecao(),
        choices=[("", "Qualquer"), ("unidade_movel", "Unidade móvel"), ("onibus", "Ônibus"),
                 ("caminhao", "Caminhão"), ("van", "Van"),
                 ("caracterizada", "Viatura caracterizada"),
                 ("descaracterizada", "Viatura descaracterizada"),
                 ("sem", "Sem transporte")])
    diarias_de = forms.DecimalField(
        label="Diárias de", required=False, min_value=0, max_digits=10, decimal_places=2,
        localize=True, widget=forms.TextInput(attrs=_attrs(
            inputmode="decimal", placeholder="mínimo", **{"aria-label": "Diárias a partir de"})))
    diarias_ate = forms.DecimalField(
        label="até", required=False, min_value=0, max_digits=10, decimal_places=2,
        localize=True, widget=forms.TextInput(attrs=_attrs(
            inputmode="decimal", placeholder="máximo", **{"aria-label": "Diárias até"})))

    def __init__(self, *args, form_id: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["form"] = form_id or "filtros-oficios"

    def clean(self):
        dados = super().clean() or {}
        # Inverteu as pontas? Entende e segue, em vez de devolver erro.
        for menor, maior in (("saida_de", "saida_ate"), ("diarias_de", "diarias_ate")):
            a, b = dados.get(menor), dados.get(maior)
            if a is not None and b is not None and b < a:
                dados[menor], dados[maior] = b, a
        return dados

    @property
    def periodo_texto(self) -> str:
        """O que aparece no campo único do período."""
        if not self.is_valid():
            return ""
        de, ate = self.cleaned_data.get("saida_de"), self.cleaned_data.get("saida_ate")
        if not de:
            return ""
        return f"{de:%d/%m/%Y} a {ate:%d/%m/%Y}" if ate else f"{de:%d/%m/%Y}"

    @property
    def ativos(self) -> int:
        """Quantos filtros estão valendo — o número que aparece no botão da gaveta. O
        período conta como um só, que é como quem filtra enxerga."""
        if not self.is_valid():
            return 0
        dados = dict(self.cleaned_data)
        periodo = bool(dados.pop("saida_de", None) or dados.pop("saida_ate", None))
        return sum(1 for valor in dados.values() if valor not in (None, "")) + (1 if periodo else 0)


class AssociadoAoFormularioDoOficio:
    """Os campos ficam espalhados pelas seções da página e se ligam ao <form id="form-oficio">
    pelo atributo HTML `form` — assim a seção Equipe pode ter formulários próprios (HTMX)
    sem aninhar <form> (HTML inválido)."""

    form_id = FORM_ID

    def _associar(self) -> None:
        for campo in self.fields.values():  # type: ignore[attr-defined]
            campo.widget.attrs["form"] = self.form_id


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
        label="Protocolo", required=False, max_length=14,
        help_text="eProtocolo: nove dígitos (ex.: 12.345.678-9).",
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
                  "justificativa_modelo", "justificativa", "roteiro"]
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
            "roteiro": forms.HiddenInput,
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
        # Roteiro de origem: só roteiros da unidade do ofício (o vínculo vem de "Usar roteiro").
        roteiro = cast(forms.ModelChoiceField, self.fields["roteiro"])
        roteiro.queryset = Roteiro.objects.filter(unidade_id=self.instance.unidade_id)
        roteiro.required = False
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


UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB",
       "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]


def _minutos_hhmm(minutos: int | None) -> str:
    if minutos is None:
        return ""
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


class CampoDuracao(forms.CharField):
    """Duração "hh:mm" (ex.: 04:30) → minutos. Vazio = calcular/sugerir automaticamente."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("widget", forms.TextInput(attrs=_attrs(
            inputmode="numeric", placeholder="hh:mm", autocomplete="off", maxlength="5",
            **{"data-mascara": "hora"})))
        super().__init__(**kwargs)

    def to_python(self, value):
        texto = (super().to_python(value) or "").strip()
        if not texto:
            return None
        m = re.match(r"^(\d{1,2}):?(\d{2})$", texto)
        if not m or int(m.group(2)) > 59:
            raise forms.ValidationError("Informe a duração em horas e minutos, ex.: 04:30.")
        return int(m.group(1)) * 60 + int(m.group(2))

    def prepare_value(self, value):
        return _minutos_hhmm(value) if isinstance(value, int) else value


class CampoUF(forms.ChoiceField):
    """Estado da parada: filtra a busca de municípios e confere a escolha."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("label", "UF")
        kwargs.setdefault("choices", [("", "UF")] + [(uf, uf) for uf in UFS])
        kwargs.setdefault("widget", Selecao(attrs={"data-uf": ""}))
        super().__init__(**kwargs)


class _ParadaBase(AssociadoAoFormularioDoOficio, forms.Form):
    def __init__(self, *args, form_id: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_id = form_id or FORM_ID
        if "cidade" in self.fields and not self.initial.get("uf"):
            texto = str(self.initial.get("cidade") or "")
            if "/" in texto:
                self.initial["uf"] = texto.rsplit("/", 1)[1].strip().upper()[:2]
        self._associar()

    def clean(self):
        super().clean()
        dados = self.cleaned_data
        uf, cidade = dados.get("uf"), dados.get("cidade")
        if uf and cidade and cidade.uf != uf:
            self.add_error("cidade", f"Escolha um município de {uf} (ou mude a UF).")
        return dados


class FormularioSede(_ParadaBase):
    """Sede (origem e volta da viagem): pode ser trocada no ofício e no roteiro."""

    uf = CampoUF()
    cidade = CampoMunicipio(label="Sede (origem da viagem)")


class FormularioDestino(_ParadaBase):
    uf = CampoUF()
    cidade = CampoMunicipio(label="Cidade de destino")
    saida = CampoDataHora(label="Saída")
    tempo_viagem = CampoDuracao(label="Tempo de viagem")
    tempo_adicional = CampoDuracao(label="Tempo adicional")


class FormularioRetorno(_ParadaBase):
    saida = CampoDataHora(label="Saída para a sede")
    tempo_viagem = CampoDuracao(label="Tempo de viagem")
    tempo_adicional = CampoDuracao(label="Tempo adicional")


class _ConjuntoDestinosBase(forms.BaseFormSet):
    """Ordem (arrastar e soltar) e remoção como campos ligados ao <form> da página."""

    def add_fields(self, form, index):
        super().add_fields(form, index)
        form_id = self.form_kwargs.get("form_id") or FORM_ID
        form.fields["ORDER"].widget = forms.HiddenInput(attrs={"data-ordem": "",
                                                               "form": form_id})
        form.fields["DELETE"].widget.attrs.update({"data-remover": "", "form": form_id})


ConjuntoDestinos = forms.formset_factory(
    FormularioDestino, formset=_ConjuntoDestinosBase, extra=0, min_num=1, validate_min=True,
    max_num=10, validate_max=True, can_delete=True, can_order=True)


FORM_ID_ROTEIRO = "form-roteiro"


class CampoDia(forms.DateField):
    def __init__(self, **kwargs):
        kwargs.setdefault("widget", EntradaData())
        kwargs.setdefault("input_formats", FORMATOS_DATA)
        kwargs.setdefault("error_messages", {
            "invalid": "Informe a data no formato dd/mm/aaaa.", "required": "Informe a data."})
        super().__init__(**kwargs)


class CampoHora(forms.TimeField):
    def __init__(self, **kwargs):
        kwargs.setdefault("widget", EntradaHora())
        kwargs.setdefault("input_formats", ["%H:%M", "%H:%M:%S"])
        kwargs.setdefault("error_messages", {
            "invalid": "Informe a hora no formato hh:mm.", "required": "Informe a hora."})
        super().__init__(**kwargs)


class FormularioBateVolta(_ParadaBase):
    """Um bate-volta: um destino visitado todo dia de um período, com os mesmos horários.
    Especificação: docs/superpowers/specs/2026-10-02-bate-volta-design.md"""

    uf = CampoUF()
    cidade = CampoMunicipio(label="Destino")
    dia_inicial = CampoDia(label="Primeiro dia")
    dia_final = CampoDia(label="Último dia")
    hora_saida = CampoHora(label="Hora de saída")
    hora_volta = CampoHora(label="Hora da volta")

    def clean(self):
        dados = super().clean()
        inicial, final = dados.get("dia_inicial"), dados.get("dia_final")
        saida, volta = dados.get("hora_saida"), dados.get("hora_volta")
        if inicial and final and final < inicial:
            self.add_error("dia_final", "O último dia não pode ser antes do primeiro.")
        if saida and volta and volta <= saida:
            self.add_error("hora_volta", "A volta é no mesmo dia: informe uma hora depois "
                                         "da saída.")
        return dados


ConjuntoBateVoltas = forms.formset_factory(
    FormularioBateVolta, formset=_ConjuntoDestinosBase, extra=0, min_num=1, validate_min=True,
    max_num=10, validate_max=True, can_delete=True, can_order=True)


class FormularioRoteiro(AssociadoAoFormularioDoOficio, forms.ModelForm):
    """O roteiro cadastrado é só o itinerário (formulários acima): a tela não pede mais nada.
    As diárias são estimadas para um servidor; o ofício usa a equipe dele."""

    form_id = FORM_ID_ROTEIRO

    class Meta:
        model = Roteiro
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._associar()


def iniciais_do_roteiro(oficio: Oficio) -> tuple[list[dict], dict]:
    """Valores iniciais dos formulários de roteiro a partir dos trechos gravados."""
    return iniciais_de_trechos(trechos_de(oficio), oficio.sede_id)


def iniciais_de_trechos(trechos, sede_id: int | None) -> tuple[list[dict], dict]:
    """Trechos gravados (do ofício ou de um roteiro cadastrado) → iniciais do itinerário.
    Trechos antigos (sem tempos gravados) viram tempo de viagem = chegada − saída."""
    trechos = list(trechos)

    def local(dt: datetime) -> str:
        return timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M")

    def tempos(t) -> dict:
        adicional = t.tempo_adicional_min or 0
        viagem = t.tempo_viagem_min
        if viagem is None:
            viagem = max(0, int((t.chegada_em - t.saida_em).total_seconds() // 60) - adicional)
        return {"saida": local(t.saida_em), "tempo_viagem": _minutos_hhmm(viagem),
                "tempo_adicional": _minutos_hhmm(adicional), "chegada": local(t.chegada_em),
                "km": t.distancia_km}

    # O último trecho que chega à sede é o retorno; todos os anteriores (inclusive
    # passagens intermediárias pela sede, como no bate-volta) são "destinos".
    volta = trechos[-1] if trechos and trechos[-1].destino_id == sede_id else None
    ida = trechos[:-1] if volta else trechos
    destinos = [{"cidade": f"{t.destino.nome}/{t.destino.uf}", "uf": t.destino.uf,
                 "ORDER": i, **tempos(t)} for i, t in enumerate(ida, start=1)] or [{}]
    retorno = tempos(volta) if volta else {}
    return destinos, retorno
