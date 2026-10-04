"""Formulários do Ofício. Mensagens dizem o que fazer, não só o que está errado."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, cast

from django import forms
from django.db.models import Q
from django.utils import timezone

from gestao.cadastros.forms import CampoMunicipio, resolver_municipio
from gestao.cadastros.models import (
    AtividadePlano,
    Cargo,
    Combustivel,
    HorarioAtendimento,
    ModeloTexto,
    PresetAtividades,
    ProgramaSolicitante,
    Servidor,
    Unidade,
    Viatura,
)
from gestao.cadastros.validacoes import normalizar_placa, placa_valida, somente_digitos
from gestao.plataforma.widgets import (
    FORMATOS_DATA,
    FORMATOS_DATA_HORA,
    CaixasDeEscolha,
    EntradaData,
    EntradaDataHora,
    EntradaHora,
    EscolhaMultiplaRemota,
    Selecao,
    SelecaoDeTexto,
)

from .models import Oficio, OrdemServico, Roteiro
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
    # Data do ofício ("criação" na referência: lá o campo data_criacao É a data do ofício).
    criacao_de = forms.DateField(required=False, input_formats=FORMATOS_DATA,
                                 widget=forms.HiddenInput(attrs={"data-periodo-de": ""}))
    criacao_ate = forms.DateField(required=False, input_formats=FORMATOS_DATA,
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
        for menor, maior in (("saida_de", "saida_ate"), ("criacao_de", "criacao_ate"),
                             ("diarias_de", "diarias_ate")):
            a, b = dados.get(menor), dados.get(maior)
            if a is not None and b is not None and b < a:
                dados[menor], dados[maior] = b, a
        return dados

    def _texto_do_periodo(self, de_nome: str, ate_nome: str) -> str:
        if not self.is_valid():
            return ""
        de, ate = self.cleaned_data.get(de_nome), self.cleaned_data.get(ate_nome)
        if not de:
            return ""
        return f"{de:%d/%m/%Y} a {ate:%d/%m/%Y}" if ate else f"{de:%d/%m/%Y}"

    @property
    def periodo_texto(self) -> str:
        """O que aparece no campo único do período de saída."""
        return self._texto_do_periodo("saida_de", "saida_ate")

    @property
    def periodo_criacao_texto(self) -> str:
        """O que aparece no campo único do período da data do ofício."""
        return self._texto_do_periodo("criacao_de", "criacao_ate")

    @property
    def ativos(self) -> int:
        """Quantos filtros estão valendo — o número que aparece no botão da gaveta. O
        período conta como um só, que é como quem filtra enxerga."""
        if not self.is_valid():
            return 0
        dados = dict(self.cleaned_data)
        periodos = 0
        for de, ate in (("saida_de", "saida_ate"), ("criacao_de", "criacao_ate")):
            # pop dos dois sempre (um `or` deixaria a outra ponta contando sozinha)
            pontas = [dados.pop(de, None), dados.pop(ate, None)]
            periodos += 1 if any(pontas) else 0
        return sum(1 for valor in dados.values() if valor not in (None, "")) + periodos


class AssociadoAoFormularioDoOficio:
    """Os campos ficam espalhados pelas seções da página e se ligam ao <form id="form-oficio">
    pelo atributo HTML `form` — assim a seção Equipe pode ter formulários próprios (HTMX)
    sem aninhar <form> (HTML inválido)."""

    form_id = FORM_ID

    def _associar(self) -> None:
        for campo in self.fields.values():  # type: ignore[attr-defined]
            campo.widget.attrs["form"] = self.form_id


class CampoDataHora(forms.DateTimeField):
    def __init__(self, **kwargs):
        kwargs.setdefault("widget", EntradaDataHora())
        kwargs.setdefault("input_formats", FORMATOS_DATA_HORA)
        kwargs.setdefault("error_messages", {
            "invalid": "Informe data e hora, ex.: 08/10/2026 09:00.",
            "required": "Informe data e hora."})
        super().__init__(**kwargs)


class SelecaoDeViatura(forms.Select):
    """<select> de viaturas com o que a folha precisa para sugerir e escolher sozinha:
    unidade, sigla, motoristas habituais e a linha de detalhe de cada opção."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcao = super().create_option(name, value, label, selected, index, subindex, attrs)
        # ModelChoiceIteratorValue traz a instância: nenhuma consulta a mais por opção.
        viatura: Viatura | None = getattr(value, "instance", None)
        if viatura is not None:
            sigla = viatura.unidade.sigla if viatura.unidade is not None else ""
            opcao["attrs"].update({
                "data-unidade": str(viatura.unidade_id or ""),
                "data-sigla": sigla,
                "data-motoristas": " ".join(str(m.pk) for m in viatura.motoristas.all()),
                "data-nomes": "|".join(m.nome.split()[0] for m in viatura.motoristas.all()),
                "data-meta": " · ".join(p for p in (
                    getattr(viatura.combustivel, "nome", ""),
                    viatura.get_tipo_display(), sigla) if p),
            })
        return opcao


class FormularioOficio(AssociadoAoFormularioDoOficio, forms.ModelForm):
    """Seções Dados, Transporte e Justificativa (equipe e roteiro têm formulários próprios)."""

    versao = forms.IntegerField(widget=forms.HiddenInput, required=False)
    # Digitados com pontuação (14 e 12 caracteres); a limpeza deixa só os dígitos (11 e 9).
    motorista_externo_cpf = forms.CharField(
        label="CPF", required=False, max_length=14,
        widget=forms.TextInput(attrs=_attrs(inputmode="numeric", **{"data-mascara": "cpf"})))
    motorista_protocolo_origem = forms.CharField(
        label="Protocolo de origem", required=False, max_length=14,
        widget=forms.TextInput(attrs=_attrs(inputmode="numeric",
                                            **{"data-mascara": "protocolo"})))
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
                  "justificativa_modelo", "justificativa", "roteiro",
                  "motorista_externo", "motorista_externo_servidor", "motorista_externo_nome",
                  "motorista_externo_rg", "motorista_externo_cpf", "motorista_externo_cargo",
                  "motorista_externo_unidade", "motorista_externo_observacao",
                  "motorista_oficio_origem", "motorista_protocolo_origem"]
        widgets = {
            "data_oficio": EntradaData(),
            # Escolhas como seleção, na altura dos campos ao lado (a mesma peça do "Texto
            # pronto", do "Ordenar por" da lista e da UF da folha do roteiro).
            "marcador": Selecao(),
            "motivo": forms.Textarea(attrs=_attrs("area-texto", rows=3,
                                                  placeholder="Ex.: Apoio e condução da Unidade "
                                                              "Móvel no evento Expoara.")),
            "custeio": Selecao(),
            "custeio_instituicao": forms.TextInput(attrs=_attrs()),
            "tipo_transporte": Selecao(),
            "viatura": SelecaoDeViatura(attrs=_attrs("selecao")),
            "transporte_descricao": forms.TextInput(attrs=_attrs(
                placeholder="Ex.: Ônibus de linha, veículo cedido…")),
            "transporte_placa": forms.TextInput(attrs=_attrs(placeholder="Ex.: ABC1D23")),
            "transporte_combustivel": Selecao(),
            "justificativa_modelo": SelecaoDeTexto(),
            "justificativa": forms.Textarea(attrs=_attrs("area-texto", rows=5)),
            "roteiro": forms.HiddenInput,
            "motorista_externo": Selecao(),
            # O id vem do <pc-combobox> remoto (busca de servidores), no campo oculto.
            "motorista_externo_servidor": forms.HiddenInput(attrs={"data-valor-id": ""}),
            "motorista_externo_nome": forms.TextInput(attrs=_attrs(autocomplete="off")),
            "motorista_externo_rg": forms.TextInput(attrs=_attrs(inputmode="numeric")),
            "motorista_externo_cargo": forms.TextInput(attrs=_attrs()),
            "motorista_externo_unidade": forms.TextInput(attrs=_attrs()),
            "motorista_externo_observacao": forms.Textarea(attrs=_attrs("area-texto", rows=2)),
            "motorista_oficio_origem": forms.TextInput(attrs=_attrs(
                inputmode="numeric", placeholder="Ex.: 15/2026")),
        }
        labels = {"motorista_externo": "Quem dirige",
                  "motorista_externo_nome": "Nome", "motorista_externo_rg": "RG",
                  "motorista_externo_cpf": "CPF", "motorista_externo_cargo": "Cargo",
                  "motorista_externo_unidade": "Unidade",
                  "motorista_externo_observacao": "Observação",
                  "motorista_oficio_origem": "Ofício de origem",
                  "motorista_protocolo_origem": "Protocolo do motorista",
                  "motivo": "Motivo da viagem",
                  "justificativa_modelo": "Texto pronto da justificativa",
                  "viatura": "Viatura", "transporte_combustivel": "Combustível"}
        help_texts = {
            "motivo": "Aparece no ofício exatamente como escrito.",
            "porte_arma": "Marque se os servidores transportarão arma de fogo.",
        }

    # Texto pronto do motivo: só ajuda a escrever (preenche o campo ao escolher); não é
    # gravado no ofício — o que vale é o texto do motivo.
    motivo_modelo = forms.ModelChoiceField(
        queryset=ModeloTexto.objects.none(), required=False, label="Texto pronto do motivo",
        empty_label="Escrever do zero", widget=SelecaoDeTexto())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cast(forms.ModelChoiceField, self.fields["motivo_modelo"]).queryset = (
            ModeloTexto.objects.filter(ativo=True, tipo=ModeloTexto.Tipo.MOTIVO))
        # Na folha, as escolhas levam o nome curto — o rótulo completo do modelo (com a
        # explicação entre parênteses) é para o documento e cortaria no campo. A mesma
        # decisão da janela de resumo (`custeio_curto`).
        cast(forms.ChoiceField, self.fields["marcador"]).choices = [
            (Oficio.Marcador.NENHUM, "Autorização"),
            (Oficio.Marcador.RETIFICADO, "Retificado"),
            (Oficio.Marcador.COMPLEMENTAR, "Complementar"),
        ]
        cast(forms.ChoiceField, self.fields["custeio"]).choices = [
            (Oficio.Custeio.UNIDADE, "Unidade"),
            (Oficio.Custeio.OUTRA_INSTITUICAO, "Outra instituição"),
            (Oficio.Custeio.ONUS_LIMITADO, "Ônus limitados"),
        ]
        cast(forms.ChoiceField, self.fields["motorista_externo"]).choices = [
            (Oficio.MotoristaExterno.NENHUM, "Alguém da equipe"),
            (Oficio.MotoristaExterno.SERVIDOR, "Servidor de outro ofício"),
            (Oficio.MotoristaExterno.MANUAL, "Pessoa não cadastrada"),
        ]
        servidor_externo = cast(forms.ModelChoiceField, self.fields["motorista_externo_servidor"])
        # Ativos, mais o que o rascunho já usa: desativar um cadastro (em Cadastros) não
        # pode travar a gravação de quem já o escolheu.
        inst = self.instance
        servidor_externo.queryset = Servidor.objects.filter(
            Q(ativo=True) | Q(pk=inst.motorista_externo_servidor_id))
        servidor_externo.required = False
        cast(forms.ChoiceField, self.fields["tipo_transporte"]).choices = [
            (Oficio.TipoTransporte.VIATURA, "Viatura oficial"),
            (Oficio.TipoTransporte.OUTRO, "Outro meio"),
        ]
        viatura = cast(forms.ModelChoiceField, self.fields["viatura"])
        viatura.queryset = (Viatura.objects.filter(Q(ativo=True) | Q(pk=inst.viatura_id))
                            .select_related("combustivel", "unidade")
                            .prefetch_related("motoristas"))
        viatura.empty_label = "Selecione a viatura…"
        combustivel = cast(forms.ModelChoiceField, self.fields["transporte_combustivel"])
        combustivel.queryset = Combustivel.objects.filter(
            Q(ativo=True) | Q(pk=inst.transporte_combustivel_id))
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
            p = self.instance.motorista_protocolo_origem
            if len(p) == 9:
                self.initial["motorista_protocolo_origem"] = f"{p[:2]}.{p[2:5]}.{p[5:8]}-{p[8]}"
        self._associar()

    def clean_protocolo(self):
        digitos = somente_digitos(self.cleaned_data.get("protocolo"))
        if digitos and len(digitos) != 9:
            raise forms.ValidationError(
                f"O protocolo tem 9 dígitos; você informou {len(digitos)}.")
        return digitos

    def clean_motorista_externo_cpf(self):
        digitos = somente_digitos(self.cleaned_data.get("motorista_externo_cpf"))
        if digitos and len(digitos) != 11:
            raise forms.ValidationError(f"O CPF tem 11 dígitos; você informou {len(digitos)}.")
        return digitos

    def clean_motorista_protocolo_origem(self):
        digitos = somente_digitos(self.cleaned_data.get("motorista_protocolo_origem"))
        if digitos and len(digitos) != 9:
            raise forms.ValidationError(
                f"O protocolo tem 9 dígitos; você informou {len(digitos)}.")
        return digitos

    def clean_motorista_oficio_origem(self):
        return "".join((self.cleaned_data.get("motorista_oficio_origem") or "").split())

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
        # Sem JavaScript, escolher o texto pronto com o campo vazio é o que preenche o campo.
        if dados.get("justificativa_modelo") and not (dados.get("justificativa") or "").strip():
            dados["justificativa"] = dados["justificativa_modelo"].texto
        if dados.get("motivo_modelo") and not (dados.get("motivo") or "").strip():
            dados["motivo"] = dados["motivo_modelo"].texto
        dados.pop("motivo_modelo", None)
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


class FormularioJustificativa(forms.Form):
    """Escrever/editar a justificativa pela lista de justificativas (D6). O texto é o do
    ofício — não existe cópia; gravar aqui grava no ofício."""

    justificativa_modelo = forms.ModelChoiceField(
        queryset=ModeloTexto.objects.none(), required=False,
        label="Texto pronto da justificativa", empty_label="Escrever do zero",
        widget=SelecaoDeTexto())
    justificativa = forms.CharField(
        label="Justificativa", required=False, max_length=4000,
        widget=forms.Textarea(attrs=_attrs("area-texto", rows=6)))
    versao = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cast(forms.ModelChoiceField, self.fields["justificativa_modelo"]).queryset = (
            ModeloTexto.objects.filter(ativo=True, tipo=ModeloTexto.Tipo.JUSTIFICATIVA))

    def clean(self):
        dados = super().clean() or {}
        if dados.get("justificativa_modelo") and not (dados.get("justificativa") or "").strip():
            dados["justificativa"] = dados["justificativa_modelo"].texto
        dados["justificativa"] = " ".join((dados.get("justificativa") or "").split(" ")).strip()
        return dados


# ---------------------------------------------------------------- termos de autorização
MAX_DESTINOS_TERMO = 30
MAX_SERVIDORES_TERMO = 50


class CampoMunicipios(forms.Field):
    """Vários "Cidade/UF" (escolhidos por busca), resolvidos para Municipio na ordem."""

    def __init__(self, **kwargs):
        kwargs.setdefault("widget", EscolhaMultiplaRemota(
            rotulo_vazio="Nenhum destino escolhido.", placeholder="Cidade…"))
        super().__init__(**kwargs)

    def to_python(self, value):
        if not value:
            return []
        if isinstance(value, str):
            value = [value]
        textos = [str(v) for v in value if str(v).strip()]
        if len(textos) > MAX_DESTINOS_TERMO:  # corta antes de consultar (cada um é uma busca)
            raise forms.ValidationError(f"No máximo {MAX_DESTINOS_TERMO} destinos.")
        return [resolver_municipio(v) for v in textos]

    def prepare_value(self, value):
        return [str(m) if hasattr(m, "uf") else m for m in (value or [])]


class FormularioTermo(forms.Form):
    """Cadastro do termo. Em branco, destinos, período, servidores e viatura vêm do ofício
    (referência: "herdados"); sem ofício, destino e data são obrigatórios (o serviço confere)."""

    # Versão que a tela abriu (gravar por cima de outra pessoa é recusado).
    versao = forms.CharField(required=False, widget=forms.HiddenInput)

    oficio = forms.ModelChoiceField(
        label="Ofício vinculado", queryset=Oficio.objects.none(), required=False,
        widget=forms.HiddenInput(attrs={"data-valor-id": ""}))
    evento = forms.CharField(
        label="Evento", max_length=160, required=False, initial="PCPR na Comunidade",
        help_text="Sai no documento: “manifesto o interesse em participar do …”.",
        widget=forms.TextInput(attrs=_attrs(autocomplete="off")))
    destinos = CampoMunicipios(label="Destinos", required=False,
                               help_text="Em branco, valem os destinos do ofício.")
    data_inicio = forms.DateField(label="Data inicial", required=False, widget=EntradaData(),
                                  input_formats=FORMATOS_DATA)
    data_fim = forms.DateField(label="Data final", required=False, widget=EntradaData(),
                               input_formats=FORMATOS_DATA,
                               help_text="Um dia só: deixe em branco.")
    servidores = forms.ModelMultipleChoiceField(
        label="Servidores", queryset=Servidor.objects.none(), required=False,
        help_text="Um termo por servidor. Em branco, vale a equipe do ofício.")
    viatura = forms.ModelChoiceField(label="Viatura", queryset=Viatura.objects.none(),
                                     required=False, empty_label="A do ofício (ou nenhuma)")

    def __init__(self, *args, oficios=None, fonte_servidores: str = "",
                 fonte_municipios: str = "", termo=None, **kwargs):
        super().__init__(*args, **kwargs)
        if oficios is not None and termo is not None:  # sempre da unidade do termo
            oficios = oficios.filter(unidade_id=termo.unidade_id)
        cast(forms.ModelChoiceField, self.fields["oficio"]).queryset = (
            oficios if oficios is not None else Oficio.objects.none())
        atuais = list(termo.servidores.values_list("pk", flat=True)) if termo else []
        servidores = cast(forms.ModelMultipleChoiceField, self.fields["servidores"])
        servidores.queryset = Servidor.objects.filter(Q(ativo=True) | Q(pk__in=atuais))
        servidores.widget = EscolhaMultiplaRemota(
            fonte=fonte_servidores, rotulo_vazio="Nenhum servidor escolhido.",
            placeholder="Nome, cargo ou CPF…")
        servidores.widget.choices = servidores.choices
        self.fields["destinos"].widget.fonte = fonte_municipios
        viatura = cast(forms.ModelChoiceField, self.fields["viatura"])
        viatura.queryset = Viatura.objects.filter(
            Q(ativo=True) | Q(pk=termo.viatura_id if termo else None)).order_by("placa")
        # Com ofício, o que vem dele aparece sob cada campo ("Do ofício: …"): o vazio diz
        # isso, sem ajuda fixa que repita. Sem ofício, destino e data são obrigatórios.
        if self.is_bound:
            com_oficio = bool(self.data.get("oficio"))
        else:
            com_oficio = bool(self.initial.get("oficio") or (termo and termo.oficio_id))
        destinos = self.fields["destinos"]
        if com_oficio:
            destinos.help_text = ""
            destinos.widget.rotulo_vazio = "Nenhum escolhido aqui: valem os do ofício."
            servidores.help_text = "Um termo por servidor."
            servidores.widget.rotulo_vazio = "Nenhum escolhido aqui: vale a equipe do ofício."
        else:
            destinos.help_text = "Obrigatório sem ofício vinculado."
            servidores.help_text = "Um termo por servidor; sem servidor, sai só o genérico."

    def clean(self):
        """As regras do serviço, com o erro no campo certo (todas de uma vez)."""
        from .termos import _do_oficio
        dados = super().clean() or {}
        oficio = dados.get("oficio")
        destinos_oficio, inicio_oficio, _ = _do_oficio(oficio) if oficio else ([], None, None)
        if not dados.get("destinos") and not destinos_oficio and "destinos" not in self.errors:
            self.add_error("destinos", "Informe o destino ou escolha um ofício com roteiro.")
        inicio, fim = dados.get("data_inicio"), dados.get("data_fim")
        if not inicio and not inicio_oficio and "data_inicio" not in self.errors:
            self.add_error("data_inicio", "Informe a data ou escolha um ofício com período.")
        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "A data final não pode ser anterior à inicial.")
        if fim and not inicio:
            self.add_error("data_inicio", "Informe a data inicial.")
        return dados

    def clean_servidores(self):
        servidores = self.cleaned_data["servidores"]
        if len(servidores) > MAX_SERVIDORES_TERMO:
            raise forms.ValidationError(f"No máximo {MAX_SERVIDORES_TERMO} servidores por termo.")
        return servidores

    @classmethod
    def de(cls, termo, **kwargs):
        from .termos import versao_de
        return cls(termo=termo, initial={
            "versao": versao_de(termo),
            "oficio": termo.oficio_id, "evento": termo.evento,
            "destinos": [str(d.municipio) for d in termo.destinos.all()],
            "data_inicio": termo.data_inicio,
            "data_fim": termo.data_fim if termo.data_fim != termo.data_inicio else None,
            "servidores": [s.pk for s in termo.servidores.all()],
            "viatura": termo.viatura_id}, **kwargs)


# ---------------------------------------------------------------- ordens de serviço
class FormularioOrdem(forms.Form):
    """Cadastro da OS. Ligada a ofícios, a OS copia deles o que ficar em branco (destinos,
    período, equipe, motivo); nos tipos com função, cada um da equipe recebe a sua."""

    versao = forms.CharField(required=False, widget=forms.HiddenInput)

    oficios = forms.ModelMultipleChoiceField(
        label="Ofícios vinculados", queryset=Oficio.objects.none(), required=False,
        help_text="")  # a nota do cartão explica o que vem dos ofícios
    tipo = forms.ChoiceField(label="Tipo de necessidade", choices=OrdemServico.TIPOS,
                             widget=Selecao(),
                             help_text="Muda o texto do documento (referência, justificativas "
                                       "e atribuições da equipe).")
    destinos = CampoMunicipios(label="Destinos", required=False)
    data_inicio = forms.DateField(label="Data inicial", required=False, widget=EntradaData(),
                                  input_formats=FORMATOS_DATA)
    data_fim = forms.DateField(label="Data final", required=False, widget=EntradaData(),
                               input_formats=FORMATOS_DATA,
                               help_text="Um dia só: deixe em branco.")
    servidores = forms.ModelMultipleChoiceField(label="Equipe", queryset=Servidor.objects.none(),
                                                required=False)
    motivo_modelo = forms.ModelChoiceField(
        queryset=ModeloTexto.objects.none(), required=False, label="Texto pronto do motivo",
        empty_label="Escrever do zero", widget=SelecaoDeTexto())
    motivo = forms.CharField(
        label="Motivo", required=False, max_length=4000,
        help_text="Completa a frase “… para realizar ___.”",
        widget=forms.Textarea(attrs=_attrs("area-texto", rows=3)))
    assinante = forms.ModelChoiceField(
        label="Quem assina esta OS", queryset=Servidor.objects.none(), required=False,
        empty_label="O da configuração (substituto do período ou chefia)")
    data_documento = forms.DateField(
        label="Data do documento", required=False, widget=EntradaData(),
        input_formats=FORMATOS_DATA,
        help_text="Em branco, a da primeira geração.")

    def __init__(self, *args, oficios=None, ordem=None, fonte_oficios: str = "",
                 fonte_servidores: str = "", fonte_municipios: str = "", unidade=None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.ordem = ordem
        unidade_id = ordem.unidade_id if ordem else getattr(unidade, "pk", None)
        ligados = list(ordem.oficios.values_list("pk", flat=True)) if ordem else []
        base = oficios if oficios is not None else Oficio.objects.none()
        if ordem is not None:
            base = base.filter(unidade_id=ordem.unidade_id)
        campo_oficios = cast(forms.ModelMultipleChoiceField, self.fields["oficios"])
        campo_oficios.queryset = (base | Oficio.objects.filter(pk__in=ligados)).distinct()
        campo_oficios.widget = EscolhaMultiplaRemota(
            fonte=fonte_oficios, rotulo_vazio="Nenhum ofício vinculado.",
            placeholder="Número (12/2026), destino ou servidor…")
        campo_oficios.widget.choices = campo_oficios.choices
        atuais = list(ordem.servidores.values_list("pk", flat=True)) if ordem else []
        equipe = cast(forms.ModelMultipleChoiceField, self.fields["servidores"])
        equipe.queryset = Servidor.objects.filter(Q(ativo=True) | Q(pk__in=atuais))
        equipe.widget = EscolhaMultiplaRemota(fonte=fonte_servidores,
                                              rotulo_vazio="Nenhum servidor na equipe.",
                                              placeholder="Nome, cargo ou CPF…")
        equipe.widget.choices = equipe.choices
        self.fields["destinos"].widget.fonte = fonte_municipios
        cast(forms.ModelChoiceField, self.fields["motivo_modelo"]).queryset = (
            ModeloTexto.objects.filter(ativo=True, tipo=ModeloTexto.Tipo.MOTIVO))
        # Quem assina: servidores ativos da unidade da OS (o assinante atual continua).
        assinante = cast(forms.ModelChoiceField, self.fields["assinante"])
        assinante.queryset = Servidor.objects.filter(
            Q(ativo=True, unidade_id=unidade_id)
            | Q(pk=ordem.assinante_id if ordem else None)).order_by("nome")
        # Funções da equipe (tipos com função): um campo por servidor já gravado na OS.
        self.campos_de_funcao: list[tuple[Servidor, str]] = []
        tipo = (self.data.get("tipo") if self.is_bound else None) or (
            ordem.tipo if ordem else "padrao")
        from .dominio.ordem_servico import (
            EFEITO_DO_TIPO,
            FRASE_DO_MOTIVO,
            FUNCOES,
            FUNCOES_DO_TIPO,
        )
        self.fields["tipo"].help_text = EFEITO_DO_TIPO.get(tipo, "")
        self.fields["motivo"].help_text = (f"Completa a frase “{FRASE_DO_MOTIVO.get(tipo, '')}” "
                                           "(sem ponto final; a inicial vira minúscula).")
        permitidas = FUNCOES_DO_TIPO.get(tipo)
        if ordem is not None and permitidas:
            opcoes = [("", "Sem função")] + [(c, r) for c, r in FUNCOES if c in permitidas]
            for s in ordem.servidores.select_related("cargo").order_by("nome"):
                nome = f"funcao_{s.pk}"
                rotulo = s.nome  # o cargo já está no cartão da pessoa, logo acima
                self.fields[nome] = forms.ChoiceField(
                    label=rotulo, choices=opcoes, required=False, widget=Selecao(),
                    initial=(ordem.funcoes or {}).get(str(s.pk), ""))
                self.campos_de_funcao.append((s, nome))

    @property
    def funcoes_da_equipe(self):
        """Os campos de função já ligados ao formulário (para o template)."""
        return [self[nome] for _s, nome in self.campos_de_funcao]

    @property
    def tipo_com_funcao(self) -> bool:
        from .dominio.ordem_servico import FUNCOES_DO_TIPO
        return (self["tipo"].value() or "padrao") in FUNCOES_DO_TIPO

    @classmethod
    def de(cls, ordem, **kwargs):
        from .ordens import versao_de
        return cls(ordem=ordem, initial={
            "versao": versao_de(ordem),
            "oficios": [o.pk for o in ordem.oficios.all()], "tipo": ordem.tipo,
            "destinos": [str(d.municipio) for d in ordem.destinos.all()],
            "data_inicio": ordem.data_inicio,
            "data_fim": ordem.data_fim if ordem.data_fim != ordem.data_inicio else None,
            "servidores": [s.pk for s in ordem.servidores.all()], "motivo": ordem.motivo,
            "assinante": ordem.assinante_id, "data_documento": ordem.data_documento}, **kwargs)

    def clean(self):
        dados = super().clean() or {}
        inicio, fim = dados.get("data_inicio"), dados.get("data_fim")
        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "A data final não pode ser anterior à inicial.")
        if fim and not inicio:
            self.add_error("data_inicio", "Informe a data inicial.")
        if dados.get("motivo_modelo") and not (dados.get("motivo") or "").strip():
            dados["motivo"] = dados["motivo_modelo"].texto
        dados.pop("motivo_modelo", None)
        # Sem campos de função na tela (OS nova, tipo sem função), as gravadas ficam.
        funcoes = {str(s.pk): dados.get(nome) for s, nome in self.campos_de_funcao
                   if dados.get(nome)}
        for _s, nome in self.campos_de_funcao:
            dados.pop(nome, None)
        dados["funcoes"] = funcoes if self.campos_de_funcao else None
        return dados


# ---------------------------------------------------------------- planos de trabalho
OUTRO_PROGRAMA = "outro"
# Como o coordenador sai no documento (sem padrão: um padrão errado sairia sem aviso).
GENEROS = (("", "Escolha…"), ("M", "o Coordenador"), ("F", "a Coordenadora"))
MAX_LINHAS_EFETIVO = 50


def _opcoes_de_programa(atual_id) -> list[tuple[str, str]]:
    """Programa: os do catálogo (ativos e o atual), "Outro" e vazio."""
    programas = ProgramaSolicitante.objects.filter(Q(ativo=True) | Q(pk=atual_id))
    return [("", "Selecione um programa (opcional)"), (OUTRO_PROGRAMA, "Outro"),
            *[(str(pr.pk), pr.nome) for pr in programas]]


def _opcoes_de_horario(gravado: str) -> list[tuple[str, str]]:
    """Horário: os do catálogo; o gravado entra mesmo que tenha saído do catálogo."""
    faixas = list(HorarioAtendimento.objects.filter(ativo=True).values_list("nome", flat=True))
    if gravado and gravado not in faixas:
        faixas.insert(0, gravado)
    return [("", "Selecione um horário (opcional)"), *[(f, f) for f in faixas]]


def _limpar_programa(form: forms.Form, dados: dict) -> None:
    """Programa do catálogo, "Outro" (com o texto) ou nenhum — as mensagens da referência."""
    escolha = dados.pop("programa", "") or ""
    outros = " ".join((dados.get("programa_outros") or "").split())
    dados["programa"] = None
    if escolha and escolha != OUTRO_PROGRAMA:
        dados["programa"] = ProgramaSolicitante.objects.filter(pk=escolha).first()
        if dados["programa"] is None:
            form.add_error("programa", "Selecione um programa válido.")
        dados["programa_outros"] = ""
    elif escolha == OUTRO_PROGRAMA and not outros:
        form.add_error("programa_outros", "Informe o outro programa.")


class FormularioPlano(forms.Form):
    """Folha do plano de trabalho. O efetivo chega em linhas (`efetivo_unidade`,
    `efetivo_cargo`, `efetivo_quantidade`, repetidos) e as atividades em caixas; os
    marcadores `efetivo_presente`/`atividades_presente` dizem que o bloco estava na tela
    (tudo removido = vazio, não "não mexer")."""

    versao = forms.CharField(required=False, widget=forms.HiddenInput)
    oficios = forms.ModelMultipleChoiceField(
        label="Ofícios vinculados", queryset=Oficio.objects.none(), required=False)
    programa = forms.ChoiceField(label="Programa", required=False, widget=Selecao())
    programa_outros = forms.CharField(
        label="Outro programa", max_length=200, required=False,
        widget=forms.TextInput(attrs=_attrs(placeholder="Informe o programa quando não estiver "
                                                        "na lista")))
    data_inicio = forms.DateField(label="Início do evento", required=False,
                                  widget=EntradaData(), input_formats=FORMATOS_DATA)
    data_fim = forms.DateField(label="Fim do evento", required=False, widget=EntradaData(),
                               input_formats=FORMATOS_DATA,
                               help_text="Um dia só: deixe em branco. O deslocamento fica no "
                                         "cartão 2.")
    horario = forms.ChoiceField(label="Horário de atendimento", required=False, widget=Selecao())
    destinos = CampoMunicipios(label="Destinos", required=False,
                               help_text="O primeiro é o principal (entra nas diárias).")
    coordenador_adm = forms.ModelChoiceField(
        label="Coordenador administrativo", queryset=Servidor.objects.none(), required=False,
        widget=forms.HiddenInput(attrs={"data-valor-id": ""}))
    coordenador_adm_nome = forms.CharField(label="Nome (fora do cadastro)", max_length=255,
                                           required=False, widget=forms.TextInput(attrs=_attrs()))
    coordenador_adm_cargo = forms.CharField(label="Cargo (fora do cadastro)", max_length=120,
                                            required=False, widget=forms.TextInput(attrs=_attrs()))
    coordenador_adm_genero = forms.ChoiceField(label="Como sai no documento", choices=GENEROS,
                                               required=False, widget=Selecao())
    coordenador_op = forms.ModelChoiceField(
        label="Coordenador operacional", queryset=Servidor.objects.none(), required=False,
        widget=forms.HiddenInput(attrs={"data-valor-id": ""}))
    coordenador_op_nome = forms.CharField(label="Nome (fora do cadastro)", max_length=255,
                                          required=False, widget=forms.TextInput(attrs=_attrs()))
    coordenador_op_cargo = forms.CharField(label="Cargo (fora do cadastro)", max_length=120,
                                           required=False, widget=forms.TextInput(attrs=_attrs()))
    coordenador_op_genero = forms.ChoiceField(label="Como sai no documento", choices=GENEROS,
                                              required=False, widget=Selecao())
    saida_em = CampoDataHora(label="Saída da sede", required=False)
    chegada_em = CampoDataHora(label="Chegada na sede", required=False)
    atividades = forms.ModelMultipleChoiceField(
        label="Atividades", queryset=AtividadePlano.objects.none(), required=False,
        widget=CaixasDeEscolha())
    contextualizacao = forms.CharField(
        label="Breve contextualização", required=False, max_length=6000,
        help_text="Apagar o texto volta ao automático (feito do programa e do destino).",
        widget=forms.Textarea(attrs=_attrs("area-texto", rows=6)))
    coordenacao = forms.CharField(
        label="Coordenador do evento", required=False, max_length=4000,
        help_text="Apagar o texto volta ao automático (feito dos coordenadores).",
        widget=forms.Textarea(attrs=_attrs("area-texto", rows=5)))
    consideracoes = forms.CharField(
        label="Considerações finais", required=False, max_length=4000,
        help_text="Apagar o texto volta ao automático (feito do destino).",
        widget=forms.Textarea(attrs=_attrs("area-texto", rows=4)))
    # O texto como a tela o mostrou: igual ao enviado, a pessoa não mexeu (o automático
    # segue se refazendo); diferente, vale a regra de "voltar ao automático" do serviço.
    contextualizacao_original = forms.CharField(required=False, widget=forms.HiddenInput)
    coordenacao_original = forms.CharField(required=False, widget=forms.HiddenInput)
    consideracoes_original = forms.CharField(required=False, widget=forms.HiddenInput)
    assinante = forms.ModelChoiceField(
        label="Quem assina este plano", queryset=Servidor.objects.none(), required=False,
        empty_label="O da configuração (substituto do período ou o assinante dos planos)")
    data_documento = forms.DateField(label="Data do documento", required=False,
                                     widget=EntradaData(), input_formats=FORMATOS_DATA)

    def __init__(self, *args, plano=None, oficios=None, unidade=None, fonte_oficios: str = "",
                 fonte_municipios: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.plano = plano
        self.erros_do_efetivo: list[str] = []
        unidade_id = plano.unidade_id if plano else getattr(unidade, "pk", None)
        ligados = list(plano.oficios.values_list("pk", flat=True)) if plano else []
        base = oficios if oficios is not None else Oficio.objects.none()
        if plano is not None:
            base = base.filter(unidade_id=plano.unidade_id)
        campo_oficios = cast(forms.ModelMultipleChoiceField, self.fields["oficios"])
        campo_oficios.queryset = (base | Oficio.objects.filter(pk__in=ligados)).distinct()
        campo_oficios.widget = EscolhaMultiplaRemota(
            fonte=fonte_oficios, rotulo_vazio="Nenhum ofício vinculado (plano avulso).",
            placeholder="Número (12/2026), destino ou servidor…")
        campo_oficios.widget.choices = campo_oficios.choices
        self.fields["destinos"].widget.fonte = fonte_municipios
        cast(forms.ChoiceField, self.fields["programa"]).choices = _opcoes_de_programa(
            plano.programa_id if plano else None)
        cast(forms.ChoiceField, self.fields["horario"]).choices = _opcoes_de_horario(
            plano.horario if plano else "")
        for campo in ("coordenador_adm", "coordenador_op"):
            atual_id = getattr(plano, f"{campo}_id", None) if plano else None
            cast(forms.ModelChoiceField, self.fields[campo]).queryset = (
                Servidor.objects.filter(Q(ativo=True) | Q(pk=atual_id)).select_related("cargo"))
        assinante = cast(forms.ModelChoiceField, self.fields["assinante"])
        assinante.queryset = Servidor.objects.filter(
            Q(ativo=True, unidade_id=unidade_id)
            | Q(pk=plano.assinante_id if plano else None)).order_by("nome")
        marcadas = list(plano.atividades.values_list("pk", flat=True)) if plano else []
        cast(forms.ModelMultipleChoiceField, self.fields["atividades"]).queryset = (
            AtividadePlano.objects.filter(Q(ativo=True) | Q(pk__in=marcadas)).order_by("nome"))
        # Ativos e os já usados neste plano (desativar um cargo não pode sumir com a linha).
        usadas = list(plano.efetivo.values_list("unidade_id", "cargo_id")) if plano else []
        self.unidades = list(Unidade.objects.filter(
            Q(ativo=True) | Q(pk__in=[u for u, _c in usadas if u])).order_by("sigla"))
        self.cargos = list(Cargo.objects.filter(
            Q(ativo=True) | Q(pk__in=[c for _u, c in usadas])).order_by("nome"))

    # ------------------------------------------------------------ efetivo em linhas
    def linhas_informadas(self) -> list[dict]:
        """As linhas como vieram (para redesenhar a tela com erro)."""
        if not self.is_bound:
            return []
        dados = cast(Any, self.data)  # QueryDict (vários valores por nome)
        unidades = dados.getlist("efetivo_unidade")
        cargos = dados.getlist("efetivo_cargo")
        quantidades = dados.getlist("efetivo_quantidade")
        total = min(max(len(unidades), len(cargos), len(quantidades)), MAX_LINHAS_EFETIVO + 1)
        def item(lista, i):
            return (lista[i] if i < len(lista) else "").strip()
        return [{"unidade": item(unidades, i), "cargo": item(cargos, i),
                 "quantidade": item(quantidades, i)} for i in range(total)]

    def _efetivo(self):
        from .planos import LinhaInformada
        if not self.is_bound or "efetivo_presente" not in self.data:
            return None  # o bloco não estava na tela: não mexe
        cargos = {str(c.pk): c for c in self.cargos}
        unidades = {str(u.pk): u for u in self.unidades}
        informadas = self.linhas_informadas()
        if len(informadas) > MAX_LINHAS_EFETIVO:
            self.erros_do_efetivo.append(f"No máximo {MAX_LINHAS_EFETIVO} linhas.")
            informadas = informadas[:MAX_LINHAS_EFETIVO]
        linhas = []
        for i, linha in enumerate(informadas, start=1):
            if not linha["unidade"] and not linha["cargo"]:
                continue  # linha em branco (a quantidade 1 que vem de fábrica não conta)
            if not linha["cargo"]:
                self.erros_do_efetivo.append(f"Linha {i}: selecione o cargo.")
                continue
            if linha["cargo"] not in cargos:
                self.erros_do_efetivo.append(f"Linha {i}: cargo inválido.")
                continue
            if linha["unidade"] and linha["unidade"] not in unidades:
                self.erros_do_efetivo.append(f"Linha {i}: unidade inválida.")
                continue
            qtd = linha["quantidade"]
            if not (qtd.isascii() and qtd.isdecimal()) or not 1 <= int(qtd) <= 999:
                self.erros_do_efetivo.append(f"Linha {i}: informe a quantidade (1 a 999).")
                continue
            linhas.append(LinhaInformada(cargo=cargos[linha["cargo"]], quantidade=int(qtd),
                                         unidade=unidades.get(linha["unidade"])))
        return linhas

    def clean(self):
        dados = super().clean() or {}
        _limpar_programa(self, dados)
        inicio, fim = dados.get("data_inicio"), dados.get("data_fim")
        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "A data final não pode ser anterior à data inicial.")
        if fim and not inicio:
            self.add_error("data_inicio", "Informe a data de ida.")
        saida, chegada = dados.get("saida_em"), dados.get("chegada_em")
        if saida and chegada and chegada <= saida:
            self.add_error("chegada_em", "A chegada na sede deve ser depois da saída.")
        dados["efetivo"] = self._efetivo()
        if self.erros_do_efetivo:
            self.add_error(None, "Efetivo: " + " ".join(self.erros_do_efetivo))
        if self.is_bound and "atividades_presente" not in self.data:
            dados["atividades"] = None  # as caixas não estavam na tela: não mexe
        for campo in ("contextualizacao", "coordenacao", "consideracoes"):
            original = dados.pop(f"{campo}_original", None)
            if self.is_bound and campo not in self.data:
                dados[campo] = None
            elif original is not None and (dados.get(campo) or "").strip() == original.strip():
                dados[campo] = None  # não mexeu: o automático continua valendo
        return dados

    @classmethod
    def de(cls, plano, **kwargs):
        from .planos import versao_de
        programa = str(plano.programa_id) if plano.programa_id else (
            OUTRO_PROGRAMA if plano.programa_outros else "")
        inicial = {
            "versao": versao_de(plano), "oficios": [o.pk for o in plano.oficios.all()],
            "programa": programa, "programa_outros": plano.programa_outros,
            "data_inicio": plano.data_inicio,
            "data_fim": plano.data_fim if plano.data_fim != plano.data_inicio else None,
            "horario": plano.horario,
            "destinos": [str(d.municipio) for d in plano.destinos.all()],
            "saida_em": timezone.localtime(plano.saida_em) if plano.saida_em else None,
            "chegada_em": timezone.localtime(plano.chegada_em) if plano.chegada_em else None,
            "atividades": [a.pk for a in plano.atividades.all()],
            "contextualizacao": plano.contextualizacao, "coordenacao": plano.coordenacao,
            "consideracoes": plano.consideracoes, "assinante": plano.assinante_id,
            "contextualizacao_original": plano.contextualizacao,
            "coordenacao_original": plano.coordenacao,
            "consideracoes_original": plano.consideracoes,
            "data_documento": plano.data_documento,
        }
        for qual in ("adm", "op"):
            for sufixo in ("", "_nome", "_cargo", "_genero"):
                valor = getattr(plano, f"coordenador_{qual}{sufixo}")
                inicial[f"coordenador_{qual}{sufixo}"] = (
                    valor.pk if sufixo == "" and valor is not None else valor)
        return cls(plano=plano, initial=inicial, **kwargs)

    @staticmethod
    def conjunto_padrao() -> list[int]:
        """As atividades do conjunto padrão (vêm marcadas no plano novo e são gravadas)."""
        padrao = PresetAtividades.objects.filter(padrao=True, ativo=True).first()
        return list(padrao.atividades.values_list("pk", flat=True)) if padrao else []


class FormularioEvento(forms.Form):
    """Um evento adicional do plano (a janela "Evento N"): o que muda de evento para evento —
    programa, período, horário, destinos, coordenador operacional e atividades."""

    programa = forms.ChoiceField(label="Programa", required=False, widget=Selecao())
    programa_outros = forms.CharField(label="Outro programa", max_length=200, required=False,
                                      widget=forms.TextInput(attrs=_attrs()))
    data_inicio = forms.DateField(label="Início do evento", required=False,
                                  widget=EntradaData(), input_formats=FORMATOS_DATA)
    data_fim = forms.DateField(label="Fim do evento", required=False, widget=EntradaData(),
                               input_formats=FORMATOS_DATA, help_text="Um dia só: deixe em branco.")
    horario = forms.ChoiceField(label="Horário de atendimento", required=False, widget=Selecao())
    destinos = CampoMunicipios(label="Destinos", required=False)
    coordenador_op = forms.ModelChoiceField(
        label="Coordenador operacional", queryset=Servidor.objects.none(), required=False,
        widget=forms.HiddenInput(attrs={"data-valor-id": ""}))
    coordenador_op_nome = forms.CharField(label="Nome (fora do cadastro)", max_length=255,
                                          required=False, widget=forms.TextInput(attrs=_attrs()))
    coordenador_op_cargo = forms.CharField(label="Cargo (fora do cadastro)", max_length=120,
                                           required=False, widget=forms.TextInput(attrs=_attrs()))
    coordenador_op_genero = forms.ChoiceField(label="Como sai no documento", choices=GENEROS,
                                              required=False, widget=Selecao())
    atividades = forms.ModelMultipleChoiceField(
        label="Atividades", queryset=AtividadePlano.objects.none(), required=False,
        widget=CaixasDeEscolha())

    def __init__(self, *args, evento=None, fonte_municipios: str = "", **kwargs):
        # Ids próprios da janela (a folha também tem destinos, datas e programa).
        kwargs.setdefault("auto_id", "evento_%s")
        super().__init__(*args, **kwargs)
        self.evento = evento
        cast(forms.ChoiceField, self.fields["programa"]).choices = _opcoes_de_programa(
            evento.programa_id if evento else None)
        cast(forms.ChoiceField, self.fields["horario"]).choices = _opcoes_de_horario(
            evento.horario if evento else "")
        self.fields["destinos"].widget.fonte = fonte_municipios
        atual = evento.coordenador_op_id if evento else None
        cast(forms.ModelChoiceField, self.fields["coordenador_op"]).queryset = (
            Servidor.objects.filter(Q(ativo=True) | Q(pk=atual)).select_related("cargo"))
        marcadas = list(evento.atividades.values_list("pk", flat=True)) if evento else []
        cast(forms.ModelMultipleChoiceField, self.fields["atividades"]).queryset = (
            AtividadePlano.objects.filter(Q(ativo=True) | Q(pk__in=marcadas)).order_by("nome"))

    def clean(self):
        dados = super().clean() or {}
        _limpar_programa(self, dados)
        inicio, fim = dados.get("data_inicio"), dados.get("data_fim")
        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "A data final não pode ser anterior à data inicial.")
        if fim and not inicio:
            self.add_error("data_inicio", "Informe o início do evento.")
        return dados

    @classmethod
    def de(cls, evento, **kwargs):
        programa = str(evento.programa_id) if evento.programa_id else (
            OUTRO_PROGRAMA if evento.programa_outros else "")
        return cls(evento=evento, initial={
            "programa": programa, "programa_outros": evento.programa_outros,
            "data_inicio": evento.data_inicio,
            "data_fim": evento.data_fim if evento.data_fim != evento.data_inicio else None,
            "horario": evento.horario,
            "destinos": [str(d.municipio) for d in evento.destinos.all()],
            "coordenador_op": evento.coordenador_op_id,
            "coordenador_op_nome": evento.coordenador_op_nome,
            "coordenador_op_cargo": evento.coordenador_op_cargo,
            "coordenador_op_genero": evento.coordenador_op_genero,
            "atividades": [a.pk for a in evento.atividades.all()]}, **kwargs)
