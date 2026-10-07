"""Formulários do Ofício. Mensagens dizem o que fazer, não só o que está errado."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, cast

from django import forms
from django.db.models import Prefetch, Q
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
    TipoViagem,
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

from .dominio.numeracao import formatar_numero
from .models import Oficio, OrdemServico, PlanoTrabalho, Roteiro, TermoAutorizacao, Trecho
from .queries import trechos_de

FORM_ID = "form-oficio"


def _attrs(classe: str = "entrada", **extra) -> dict:
    return {"class": classe, **extra}


class FiltrosOficio(forms.Form):
    """Gaveta "Filtros" da lista de ofícios — o que a busca por texto não resolve.

    Destino, servidor, placa e número ficaram na busca de cima (ela já pergunta "é destino
    ou servidor?"); aqui ficam os cortes: período, data do ofício, ano do número, protocolo,
    veículo e valor de diárias (a ordem também mora na gaveta, mas é outro parâmetro).
    Tudo é opcional, e valor inválido é ignorado **sozinho** em vez de dar erro ou derrubar
    os outros — uma lista nunca deve recusar a busca de quem está procurando.
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
    # Ano do NÚMERO (≠ data do ofício: rascunho de dezembro emitido em janeiro). As opções
    # são os anos que existem na numeração; outro ano é ignorado.
    ano = forms.TypedChoiceField(label="Ano do número", required=False, coerce=int,
                                 empty_value=None, widget=Selecao(), choices=[("", "Qualquer")])
    protocolo = forms.CharField(label="Protocolo", required=False, max_length=20,
                                widget=forms.TextInput(attrs=_attrs(
                                    inputmode="numeric", placeholder="Dígitos do protocolo")))
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

    VEICULOS: dict[str, str] = dict(veiculo.choices)  # type: ignore[arg-type]

    def __init__(self, *args, form_id: str | None = None, anos: list[int] | None = None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ano"].choices = [("", "Qualquer")] + [  # type: ignore[attr-defined]
            (str(a), str(a)) for a in anos or []]
        for campo in self.fields.values():
            campo.widget.attrs["form"] = form_id or "filtros-oficios"

    @property
    def validos(self) -> dict:
        """Os filtros que valem: os campos inválidos ficam de fora, os outros continuam."""
        self.is_valid()
        return {chave: valor for chave, valor in self.cleaned_data.items()
                if valor not in (None, "")}

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
        validos = self.validos
        de, ate = validos.get(de_nome), validos.get(ate_nome)
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
        período (e a faixa de diárias) conta como um só, que é como quem filtra enxerga."""
        return len(self.fichas)

    @property
    def fichas(self) -> list[tuple[str, tuple[str, ...]]]:
        """Uma ficha por filtro valendo: o texto e os parâmetros que ela tira ao remover."""
        validos = self.validos
        fichas: list[tuple[str, tuple[str, ...]]] = []

        def faixa(de, ate, formato) -> str:
            if de is not None and ate is not None:
                return f"{formato(de)} a {formato(ate)}"
            return f"a partir de {formato(de)}" if de is not None else f"até {formato(ate)}"

        def data(d) -> str:
            return f"{d:%d/%m/%Y}"

        def moeda(v) -> str:
            inteiro, _, centavos = f"{v:,.2f}".partition(".")
            return f"R$ {inteiro.replace(',', '.')},{centavos}"

        for de, ate, rotulo, formato in (("saida_de", "saida_ate", "Saída", data),
                                         ("criacao_de", "criacao_ate", "Data do ofício", data)):
            if validos.get(de) or validos.get(ate):
                fichas.append((f"{rotulo}: {faixa(validos.get(de), validos.get(ate), formato)}",
                               (de, ate)))
        if validos.get("ano"):
            fichas.append((f"Ano do número: {validos['ano']}", ("ano",)))
        if validos.get("protocolo"):
            fichas.append((f"Protocolo: {validos['protocolo']}", ("protocolo",)))
        if validos.get("veiculo"):
            fichas.append((f"Veículo: {self.VEICULOS.get(validos['veiculo'], '')}",
                           ("veiculo",)))
        if "diarias_de" in validos or "diarias_ate" in validos:
            fichas.append((f"Diárias: {faixa(validos.get('diarias_de'), validos.get('diarias_ate'), moeda)}",  # noqa: E501
                           ("diarias_de", "diarias_ate")))
        return fichas


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
        fields = ["numero", "data_oficio", "protocolo", "marcador", "motivo", "custeio",
                  "custeio_instituicao", "tipo_transporte", "viatura", "transporte_meio",
                  "transporte_descricao",
                  "transporte_placa", "transporte_combustivel", "porte_arma",
                  "justificativa_modelo", "justificativa", "roteiro",
                  # Da pessoa não cadastrada basta o nome: o ofício e o protocolo de
                  # origem a identificam (CPF, RG, cargo e unidade estão lá).
                  "motorista_externo", "motorista_externo_servidor", "motorista_externo_nome",
                  "motorista_oficio_origem", "motorista_protocolo_origem"]
        widgets = {
            # O número já vem reservado ("Novo ofício" numera na hora); dá para trocar
            # enquanto é rascunho, quando a unidade precisa casar com outra numeração.
            "numero": forms.NumberInput(attrs=_attrs(inputmode="numeric", min="1",
                                                     required=False)),
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
            "transporte_meio": Selecao(),
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
            "motorista_oficio_origem": forms.TextInput(attrs=_attrs(
                inputmode="numeric", placeholder="Ex.: 15/2026")),
        }
        labels = {"motorista_externo": "Quem dirige",
                  "motorista_externo_nome": "Nome",
                  "motorista_oficio_origem": "Ofício de origem",
                  "motorista_protocolo_origem": "Protocolo do motorista",
                  "numero": "Número do ofício",
                  "motivo": "Motivo da viagem",
                  "justificativa_modelo": "Texto pronto da justificativa",
                  "viatura": "Viatura", "transporte_combustivel": "Combustível",
                  "transporte_meio": "Meio de transporte"}
        help_texts = {
            "numero": "Já vem preenchido; mude só se a numeração da unidade pedir.",
            "porte_arma": "Marque se os servidores transportarão arma de fogo.",
        }

    # Texto pronto do motivo: só ajuda a escrever (preenche o campo ao escolher); não é
    # gravado no ofício — o que vale é o texto do motivo.
    motivo_modelo = forms.ModelChoiceField(
        queryset=ModeloTexto.objects.none(), required=False, label="Texto pronto do motivo",
        empty_label="Escrever do zero", widget=SelecaoDeTexto())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # O número não é obrigatório no envio: quem não manda o campo fica com o que já tem.
        self.fields["numero"].required = False
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
        # Sem "Alguém da equipe": quem dirige pela equipe se marca na própria equipe. Aqui
        # só se diz QUEM é o de fora — abrir ou fechar o bloco é que liga e desliga o caso
        # (transporte.js devolve o campo a vazio ao fechar).
        cast(forms.ChoiceField, self.fields["motorista_externo"]).choices = [
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
        cast(forms.ChoiceField, self.fields["transporte_meio"]).choices = [
            ("", "Selecione o meio…"), *Oficio.MeioTransporte.choices]
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

    def clean_numero(self):
        """Número livre no ano do ofício. O banco tem a trava (ano+numero únicos); aqui a
        mensagem é de gente, e não de IntegrityError.

        Sem o campo no envio (salvamentos que não passam pela folha), fica o que o ofício
        já tem: o número nasce reservado e nunca deve voltar a vazio.
        """
        numero = self.cleaned_data.get("numero") or self.instance.numero
        if not numero:
            return numero
        ano = self.instance.ano
        if Oficio.objects.filter(ano=ano, numero=numero).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(
                f"O número {formatar_numero(numero, ano)} já é de outro ofício. "
                f"Escolha outro.")
        return numero

    def clean_protocolo(self):
        digitos = somente_digitos(self.cleaned_data.get("protocolo"))
        if digitos and len(digitos) != 9:
            raise forms.ValidationError(
                f"O protocolo tem 9 dígitos; você informou {len(digitos)}.")
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


class CampoEquipe(EscolhaMultiplaRemota):
    """A equipe, em qualquer tela que pede servidores: o mesmo componente da folha do ofício
    (viagens/oficios/_equipe.html) — "Adicionar servidor" com busca e o "+" de cadastrar,
    e embaixo um cartão por pessoa (iniciais, nome, cargo · unidade, X para tirar), na grade
    que fecha a linha (larguras_de_cartoes).

    No ofício a equipe grava na hora (HTMX); aqui cada cartão leva um
    <input type="hidden" name="..."> e vai junto com o formulário. `cadastrar` é o id do
    <dialog> de cadastro rápido de servidor (sem ele, não há "+").
    """

    template_name = "viagens/widgets/equipe.html"

    def __init__(self, *, fonte: str = "", rotulo: str = "Adicionar servidor",
                 rotulo_vazio: str = "Ninguém na equipe ainda.", cadastrar: str = "",
                 maximo: int = 0, motorista: bool = False,
                 attrs: dict[str, Any] | None = None):
        super().__init__(fonte=fonte, rotulo_vazio=rotulo_vazio,
                         placeholder="Nome, CPF ou RG — escolha na lista", attrs=attrs)
        self.rotulo, self.cadastrar, self.maximo = rotulo, cadastrar, maximo
        # Quem está aqui dirige (o "Quem dirige" do lote): a viatura dele entra sozinha.
        self.motorista = motorista

    def get_context(self, name, value, attrs):
        from .templatetags.viagens import larguras_de_cartoes
        contexto = super().get_context(name, value, attrs)
        consulta = getattr(self.choices, "queryset", None)
        escolhidos = contexto["widget"]["escolhidos"]
        if consulta is not None and escolhidos:
            por_id = {s.pk: s for s in consulta.filter(pk__in=[e["id"] for e in escolhidos])
                      .select_related("cargo", "unidade")}
            for e in escolhidos:
                s = por_id.get(e["id"])
                e["iniciais"] = getattr(s, "iniciais", "")
                e["titulo"] = getattr(s, "nome", e["titulo"])
                e["unidade"] = getattr(s, "unidade_id", "") or ""
        for e, largura in zip(escolhidos, larguras_de_cartoes(len(escolhidos)), strict=False):
            e["largura"] = largura
        contexto["widget"].update({
            "rotulo": self.rotulo, "cadastrar": self.cadastrar, "maximo": self.maximo,
            "motorista": self.motorista,
            "excluir": ",".join(str(e["id"]) for e in escolhidos)})
        return contexto


class CampoOficios(EscolhaMultiplaRemota):
    """Os ofícios que o documento junta (termo, OS, plano): o mesmo arranjo de "Adicionar
    servidor" — a busca na linha toda e, embaixo, um cartão por ofício (número, situação ·
    destinos · período, X para tirar). A busca só oferece os que se juntam aos já escolhidos
    (mesma viagem ou mesmo roteiro — `excluir` leva os escolhidos; vinculos.compativeis)."""

    template_name = "viagens/widgets/oficios.html"

    def __init__(self, *, fonte: str = "", rotulo: str = "Adicionar ofício",
                 rotulo_vazio: str = "Nenhum ofício vinculado.",
                 attrs: dict[str, Any] | None = None):
        super().__init__(fonte=fonte, rotulo_vazio=rotulo_vazio,
                         placeholder="Número (12/2026), destino ou servidor — escolha na lista",
                         attrs=attrs)
        self.rotulo = rotulo

    def get_context(self, name, value, attrs):
        from .templatetags.viagens import larguras_de_cartoes
        from .vinculos import resumo
        contexto = super().get_context(name, value, attrs)
        consulta = getattr(self.choices, "queryset", None)
        escolhidos = contexto["widget"]["escolhidos"]
        if consulta is not None and escolhidos:
            por_id = {o.pk: o for o in consulta.filter(pk__in=[e["id"] for e in escolhidos])
                      .prefetch_related(Prefetch("trechos", queryset=Trecho.objects
                                                 .select_related("destino").order_by("ordem")))}
            for e in escolhidos:
                if (o := por_id.get(e["id"])) is not None:
                    e["titulo"], e["meta"] = f"Ofício {o.numero_formatado}", resumo(o)
        for e, largura in zip(escolhidos, larguras_de_cartoes(len(escolhidos)), strict=False):
            e["largura"] = largura
        contexto["widget"].update({
            "rotulo": self.rotulo, "excluir": ",".join(str(e["id"]) for e in escolhidos)})
        return contexto


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

    # Os ofícios que o termo junta (da mesma viagem ou do mesmo roteiro): o termo une os
    # dados deles (termos.uniao_dos_oficios).
    oficios = forms.ModelMultipleChoiceField(
        label="Ofícios vinculados", queryset=Oficio.objects.none(), required=False)
    evento = forms.CharField(
        label="Evento", max_length=160, required=False, initial="PCPR na Comunidade",
        help_text="Sai no documento: “manifesto o interesse em participar do …”.",
        widget=forms.TextInput(attrs=_attrs(autocomplete="off")))
    destinos = CampoMunicipios(label="Destinos", required=False,
                               help_text="Em branco, valem os destinos do ofício.")
    # O período é um campo só na tela (<pc-data data-periodo>, o calendário que marca ida e
    # volta): estes dois levam as pontas, como os filtros de período da lista de ofícios.
    data_inicio = forms.DateField(label="Data inicial", required=False, input_formats=FORMATOS_DATA,
                                  widget=forms.HiddenInput(attrs={"data-periodo-de": ""}))
    data_fim = forms.DateField(label="Data final", required=False, input_formats=FORMATOS_DATA,
                               widget=forms.HiddenInput(attrs={"data-periodo-ate": ""}))
    servidores = forms.ModelMultipleChoiceField(
        label="Servidores", queryset=Servidor.objects.none(), required=False,
        help_text="Um termo por servidor. Em branco, vale a equipe do ofício.")
    viatura = forms.ModelChoiceField(label="Viatura", queryset=Viatura.objects.none(),
                                     required=False, empty_label="A do ofício (ou nenhuma)")

    def __init__(self, *args, oficios=None, fonte_oficios: str = "", fonte_servidores: str = "",
                 fonte_municipios: str = "", termo=None, **kwargs):
        super().__init__(*args, **kwargs)
        if oficios is not None and termo is not None:  # sempre da unidade do termo
            oficios = oficios.filter(unidade_id=termo.unidade_id)
        ligados = list(termo.oficios.values_list("pk", flat=True)) if termo else []
        campo_oficios = cast(forms.ModelMultipleChoiceField, self.fields["oficios"])
        campo_oficios.queryset = ((oficios if oficios is not None else Oficio.objects.none())
                                  | Oficio.objects.filter(pk__in=ligados)).distinct()
        campo_oficios.widget = CampoOficios(fonte=fonte_oficios)
        campo_oficios.widget.choices = campo_oficios.choices
        atuais = list(termo.servidores.values_list("pk", flat=True)) if termo else []
        servidores = cast(forms.ModelMultipleChoiceField, self.fields["servidores"])
        servidores.queryset = Servidor.objects.filter(Q(ativo=True) | Q(pk__in=atuais))
        servidores.widget = CampoEquipe(fonte=fonte_servidores, cadastrar="dialogo-servidor")
        servidores.widget.choices = servidores.choices
        self.fields["destinos"].widget.fonte = fonte_municipios
        viatura = cast(forms.ModelChoiceField, self.fields["viatura"])
        viatura.queryset = (Viatura.objects.filter(
            Q(ativo=True) | Q(pk=termo.viatura_id if termo else None)).order_by("placa")
            .select_related("combustivel", "unidade").prefetch_related("motoristas"))
        # A mesma escolha do ofício: sugeridas pela equipe, com os chips (transporte.js).
        viatura.widget = SelecaoDeViatura(attrs=_attrs("selecao"))
        viatura.widget.choices = viatura.choices
        # Com ofício, o que vem dele aparece sob cada campo ("Do ofício: …"): o vazio diz
        # isso, sem ajuda fixa que repita. Sem ofício, destino e data são obrigatórios.
        if self.is_bound:
            com_oficio = bool(cast(Any, self.data).getlist("oficios"))
        else:
            com_oficio = bool(self.initial.get("oficios") or (termo and termo.oficio_id))
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
        """As regras do serviço, com o erro no campo certo (todas de uma vez).

        Destino e período em branco não impedem gravar: o termo nasce rascunho e se grava
        sozinho enquanto é preenchido (os documentos aparecem já na primeira tela); o que
        falta vira pendência na conferência ("Falta destino", "Falta período")."""
        dados = super().clean() or {}
        inicio, fim = dados.get("data_inicio"), dados.get("data_fim")
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

    def periodo_texto(self) -> str:
        """O que o campo de período mostra: "13/10/2026 a 15/10/2026", ou só a ida."""
        def texto(campo):
            v = self[campo].value()
            return v.strftime("%d/%m/%Y") if hasattr(v, "strftime") else (v or "")
        de, ate = texto("data_inicio"), texto("data_fim")
        return f"{de} a {ate}" if de and ate else de

    @staticmethod
    def campos_dos_oficios(oficios) -> dict:
        """O que os ofícios põem nos campos do termo, unidos: destinos, período, equipe e
        viatura (termos.uniao_dos_oficios)."""
        from .termos import uniao_dos_oficios
        base = uniao_dos_oficios(list(oficios))
        inicio, fim = base["inicio"], base["fim"]
        return {"destinos": [str(m) for m in base["destinos"]], "data_inicio": inicio,
                "data_fim": fim if fim != inicio else None,
                "servidores": [s.pk for s in base["servidores"]],
                "viatura": base["viatura"].pk if base["viatura"] else None}

    @classmethod
    def campos_do_oficio(cls, oficio) -> dict:
        return cls.campos_dos_oficios([oficio])

    @classmethod
    def de(cls, termo, **kwargs):
        """O termo como está, com o que estiver em branco preenchido pelo ofício vinculado.

        Vincular um ofício copia dele destinos, período, equipe e viatura para os campos —
        a pessoa vê e ajusta valores de verdade, em vez de um "Do ofício: …" sob campos
        vazios. Termos antigos, gravados vazios para herdar, abrem já preenchidos.
        """
        from .termos import oficios_do_termo, versao_de
        oficios = oficios_do_termo(termo)
        destinos = [str(d.municipio) for d in termo.destinos.all()]
        inicio = termo.data_inicio
        fim = termo.data_fim if termo.data_fim != termo.data_inicio else None
        servidores = [s.pk for s in termo.servidores.all()]
        viatura = termo.viatura_id
        if oficios:
            of = cls.campos_dos_oficios(oficios)
            destinos = destinos or of["destinos"]
            if not inicio:
                inicio, fim = of["data_inicio"], of["data_fim"]
            servidores = servidores or of["servidores"]
            viatura = viatura or of["viatura"]
        return cls(termo=termo, initial={
            "versao": versao_de(termo), "oficios": [o.pk for o in oficios],
            "evento": termo.evento,
            "destinos": destinos, "data_inicio": inicio, "data_fim": fim,
            "servidores": servidores, "viatura": viatura}, **kwargs)


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
    # Período num campo só na tela (<pc-data data-periodo>, ida e volta no mesmo calendário),
    # como no termo: estes dois levam as pontas.
    data_inicio = forms.DateField(label="Data inicial", required=False, input_formats=FORMATOS_DATA,
                                  widget=forms.HiddenInput(attrs={"data-periodo-de": ""}))
    data_fim = forms.DateField(label="Data final", required=False, input_formats=FORMATOS_DATA,
                               widget=forms.HiddenInput(attrs={"data-periodo-ate": ""}))
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
        campo_oficios.widget = CampoOficios(fonte=fonte_oficios)
        campo_oficios.widget.choices = campo_oficios.choices
        atuais = list(ordem.servidores.values_list("pk", flat=True)) if ordem else []
        equipe = cast(forms.ModelMultipleChoiceField, self.fields["servidores"])
        equipe.queryset = Servidor.objects.filter(Q(ativo=True) | Q(pk__in=atuais))
        equipe.widget = CampoEquipe(fonte=fonte_servidores, cadastrar="dialogo-servidor")
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

    def periodo_texto(self) -> str:
        """O que o campo de período mostra: "13/10/2026 a 15/10/2026", ou só a ida."""
        def texto(campo):
            v = self[campo].value()
            return v.strftime("%d/%m/%Y") if hasattr(v, "strftime") else (v or "")
        de, ate = texto("data_inicio"), texto("data_fim")
        return f"{de} a {ate}" if de and ate else de

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
            "assinante": ordem.assinante_id}, **kwargs)

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
# Como o coordenador sai no documento (sem padrão: um padrão errado sairia sem aviso).
GENEROS = (("", "Escolha…"), ("M", "o Coordenador"), ("F", "a Coordenadora"))
# Quem coordena: do cadastro (busca) ou de fora dele (nome e cargo) — como "Quem dirige".
ORIGENS_COORDENADOR = (("cadastro", "Servidor cadastrado"), ("manual", "Pessoa não cadastrada"))
MAX_LINHAS_EFETIVO = 50


def _opcoes_de_horario(gravado: str) -> list[tuple[str, str]]:
    """Horário: os do catálogo; o gravado entra mesmo que tenha saído do catálogo."""
    faixas = list(HorarioAtendimento.objects.filter(ativo=True).values_list("nome", flat=True))
    if gravado and gravado not in faixas:
        faixas.insert(0, gravado)
    return [("", "Selecione um horário (opcional)"), *[(f, f) for f in faixas]]


class EfetivoEmLinhas:
    """O efetivo em linhas (`efetivo_unidade`, `efetivo_cargo`, `efetivo_quantidade`,
    repetidos), com o marcador `efetivo_presente` dizendo que o bloco estava na tela (tudo
    removido = vazio, não "não mexer") — na folha do plano e na janela de cada evento."""

    is_bound: bool
    data: Any
    unidades: list[Unidade]
    cargos: list[Cargo]
    erros_do_efetivo: list[str]

    def _carregar_unidades_e_cargos(self, usadas) -> None:
        """Ativos e os já usados (desativar um cargo não pode sumir com a linha)."""
        self.erros_do_efetivo = []
        self.unidades = list(Unidade.objects.filter(
            Q(ativo=True) | Q(pk__in=[u for u, _c in usadas if u])).order_by("sigla"))
        self.cargos = list(Cargo.objects.filter(
            Q(ativo=True) | Q(pk__in=[c for _u, c in usadas])).order_by("nome"))

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


class FormularioPlano(EfetivoEmLinhas, forms.Form):
    """Folha do plano de trabalho. O efetivo chega em linhas (EfetivoEmLinhas) e as
    atividades em caixas (`atividades_presente` diz que o bloco estava na tela)."""

    versao = forms.CharField(required=False, widget=forms.HiddenInput)
    oficios = forms.ModelMultipleChoiceField(
        label="Ofícios vinculados", queryset=Oficio.objects.none(), required=False)
    # Programas: mais de um, em caixas (como os tipos da viagem); "Outro" abre o texto ao lado.
    programas = forms.ModelMultipleChoiceField(
        label="Programa", queryset=ProgramaSolicitante.objects.none(), required=False,
        widget=CaixasDeEscolha())
    programa_outro = forms.BooleanField(label="Outro", required=False)
    programa_outros = forms.CharField(
        label="Outro programa", max_length=200, required=False,
        widget=forms.TextInput(attrs=_attrs(placeholder="Qual programa?")))
    # Período num campo só na tela (<pc-data data-periodo>, início e fim no mesmo
    # calendário), como no termo e na OS: estes dois levam as pontas.
    data_inicio = forms.DateField(label="Início do evento", required=False,
                                  input_formats=FORMATOS_DATA,
                                  widget=forms.HiddenInput(attrs={"data-periodo-de": ""}))
    data_fim = forms.DateField(label="Fim do evento", required=False, input_formats=FORMATOS_DATA,
                               widget=forms.HiddenInput(attrs={"data-periodo-ate": ""}))
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
    coordenador_adm_origem = forms.ChoiceField(label="Quem coordena",
                                               choices=ORIGENS_COORDENADOR, required=False,
                                               widget=Selecao())
    coordenador_op = forms.ModelChoiceField(
        label="Coordenador operacional", queryset=Servidor.objects.none(), required=False,
        widget=forms.HiddenInput(attrs={"data-valor-id": ""}))
    coordenador_op_nome = forms.CharField(label="Nome (fora do cadastro)", max_length=255,
                                          required=False, widget=forms.TextInput(attrs=_attrs()))
    coordenador_op_cargo = forms.CharField(label="Cargo (fora do cadastro)", max_length=120,
                                           required=False, widget=forms.TextInput(attrs=_attrs()))
    coordenador_op_genero = forms.ChoiceField(label="Como sai no documento", choices=GENEROS,
                                              required=False, widget=Selecao())
    coordenador_op_origem = forms.ChoiceField(label="Quem coordena",
                                              choices=ORIGENS_COORDENADOR, required=False,
                                              widget=Selecao())
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

    def __init__(self, *args, plano=None, oficios=None, unidade=None, fonte_oficios: str = "",
                 fonte_municipios: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.plano = plano
        ligados = list(plano.oficios.values_list("pk", flat=True)) if plano else []
        base = oficios if oficios is not None else Oficio.objects.none()
        if plano is not None:
            base = base.filter(unidade_id=plano.unidade_id)
        campo_oficios = cast(forms.ModelMultipleChoiceField, self.fields["oficios"])
        campo_oficios.queryset = (base | Oficio.objects.filter(pk__in=ligados)).distinct()
        campo_oficios.widget = CampoOficios(
            fonte=fonte_oficios, rotulo_vazio="Nenhum ofício vinculado (plano avulso).")
        campo_oficios.widget.choices = campo_oficios.choices
        self.fields["destinos"].widget.fonte = fonte_municipios
        atuais_programas = list(plano.programas.values_list("pk", flat=True)) if plano else []
        cast(forms.ModelMultipleChoiceField, self.fields["programas"]).queryset = (
            ProgramaSolicitante.objects.filter(Q(ativo=True) | Q(pk__in=atuais_programas))
            .order_by("nome"))
        cast(forms.ChoiceField, self.fields["horario"]).choices = _opcoes_de_horario(
            plano.horario if plano else "")
        for campo in ("coordenador_adm", "coordenador_op"):
            atual_id = getattr(plano, f"{campo}_id", None) if plano else None
            cast(forms.ModelChoiceField, self.fields[campo]).queryset = (
                Servidor.objects.filter(Q(ativo=True) | Q(pk=atual_id)).select_related("cargo"))
            # O cargo de quem é de fora do cadastro: escolhido do catálogo de cargos (com o
            # "+" para cadastrar); o texto gravado entra mesmo que não esteja lá.
            gravado = getattr(plano, f"{campo}_cargo", "") if plano else ""
            nomes = list(Cargo.objects.filter(ativo=True).order_by("nome")
                         .values_list("nome", flat=True))
            if gravado and gravado not in nomes:
                nomes.insert(0, gravado)
            self.fields[f"{campo}_cargo"].widget = Selecao(
                choices=[("", "Selecione o cargo"), *[(n, n) for n in nomes]])
        marcadas = list(plano.atividades.values_list("pk", flat=True)) if plano else []
        cast(forms.ModelMultipleChoiceField, self.fields["atividades"]).queryset = (
            AtividadePlano.objects.filter(Q(ativo=True) | Q(pk__in=marcadas)).order_by("nome"))
        self._carregar_unidades_e_cargos(
            list(plano.efetivo.values_list("unidade_id", "cargo_id")) if plano else [])

    def clean(self):
        dados = super().clean() or {}
        # "Outro" marcado pede o texto; desmarcado, o texto não vale.
        outro = dados.pop("programa_outro", False)
        dados["programa_outros"] = " ".join((dados.get("programa_outros") or "").split())
        if outro and not dados["programa_outros"]:
            self.add_error("programa_outros", "Informe o outro programa.")
        if not outro:
            dados["programa_outros"] = ""
        inicio, fim = dados.get("data_inicio"), dados.get("data_fim")
        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "A data final não pode ser anterior à data inicial.")
        if fim and not inicio:
            self.add_error("data_inicio", "Informe a data de ida.")
        saida, chegada = dados.get("saida_em"), dados.get("chegada_em")
        if saida and chegada and chegada <= saida:
            self.add_error("chegada_em", "A chegada na sede deve ser depois da saída.")
        # "Quem coordena" diz qual dos dois vale: a busca (o nome à mão sai) ou o nome e o
        # cargo (o servidor da busca sai). Sem a escolha na tela, os dois ficam como vieram.
        for qual in ("adm", "op"):
            origem = dados.pop(f"coordenador_{qual}_origem", "")
            if origem == "manual":
                dados[f"coordenador_{qual}"] = None
            elif origem == "cadastro":
                dados[f"coordenador_{qual}_nome"] = dados[f"coordenador_{qual}_cargo"] = ""
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
        programas = list(plano.programas.values_list("pk", flat=True)) or (
            [plano.programa_id] if plano.programa_id else [])
        inicial = {
            "versao": versao_de(plano), "oficios": [o.pk for o in plano.oficios.all()],
            "programas": programas, "programa_outro": bool(plano.programa_outros),
            "programa_outros": plano.programa_outros,
            "data_inicio": plano.data_inicio,
            "data_fim": plano.data_fim if plano.data_fim != plano.data_inicio else None,
            "horario": plano.horario,
            "destinos": [str(d.municipio) for d in plano.destinos.all()],
            "saida_em": timezone.localtime(plano.saida_em) if plano.saida_em else None,
            "chegada_em": timezone.localtime(plano.chegada_em) if plano.chegada_em else None,
            "atividades": [a.pk for a in plano.atividades.all()],
            "contextualizacao": plano.contextualizacao, "coordenacao": plano.coordenacao,
            "consideracoes": plano.consideracoes,
            "contextualizacao_original": plano.contextualizacao,
            "coordenacao_original": plano.coordenacao,
            "consideracoes_original": plano.consideracoes,
        }
        for qual in ("adm", "op"):
            for sufixo in ("", "_nome", "_cargo", "_genero"):
                valor = getattr(plano, f"coordenador_{qual}{sufixo}")
                inicial[f"coordenador_{qual}{sufixo}"] = (
                    valor.pk if sufixo == "" and valor is not None else valor)
            de_fora = (getattr(plano, f"coordenador_{qual}_id") is None
                       and bool(getattr(plano, f"coordenador_{qual}_nome")))
            inicial[f"coordenador_{qual}_origem"] = "manual" if de_fora else "cadastro"
        return cls(plano=plano, initial=inicial, **kwargs)

    def periodo_texto(self) -> str:
        """O que o campo de período mostra: "13/10/2026 a 15/10/2026", ou só o início."""
        def texto(campo):
            v = self[campo].value()
            return v.strftime("%d/%m/%Y") if hasattr(v, "strftime") else (v or "")
        de, ate = texto("data_inicio"), texto("data_fim")
        return f"{de} a {ate}" if de and ate else de

    @staticmethod
    def conjunto_padrao() -> list[int]:
        """As atividades do conjunto padrão (vêm marcadas no plano novo e são gravadas)."""
        padrao = PresetAtividades.objects.filter(padrao=True, ativo=True).first()
        return list(padrao.atividades.values_list("pk", flat=True)) if padrao else []


class FormularioEvento(EfetivoEmLinhas, forms.Form):
    """Um evento adicional do plano (a janela "Evento N"): o que muda de evento para evento —
    programa, período, horário, destinos, efetivo, deslocamento e atividades. Os
    coordenadores são do plano."""

    # Programas: vários, como na folha do plano (<pc-escolhas>); "Outro" abre o texto.
    programas = forms.ModelMultipleChoiceField(
        label="Programa", queryset=ProgramaSolicitante.objects.none(), required=False,
        widget=CaixasDeEscolha())
    programa_outro = forms.BooleanField(label="Outro", required=False)
    programa_outros = forms.CharField(label="Outro programa", max_length=200, required=False,
                                      widget=forms.TextInput(attrs=_attrs(
                                          placeholder="Qual programa?")))
    # Período num campo só na janela (<pc-data data-periodo>), como na folha do plano.
    data_inicio = forms.DateField(label="Início do evento", required=False,
                                  input_formats=FORMATOS_DATA,
                                  widget=forms.HiddenInput(attrs={"data-periodo-de": ""}))
    data_fim = forms.DateField(label="Fim do evento", required=False, input_formats=FORMATOS_DATA,
                               widget=forms.HiddenInput(attrs={"data-periodo-ate": ""}))
    horario = forms.ChoiceField(label="Horário de atendimento", required=False, widget=Selecao())
    destinos = CampoMunicipios(label="Destinos", required=False)
    saida_em = CampoDataHora(label="Saída da sede", required=False)
    chegada_em = CampoDataHora(label="Chegada na sede", required=False)
    atividades = forms.ModelMultipleChoiceField(
        label="Atividades", queryset=AtividadePlano.objects.none(), required=False,
        widget=CaixasDeEscolha())

    def __init__(self, *args, evento=None, fonte_municipios: str = "", **kwargs):
        # Ids próprios da janela (a folha também tem destinos, datas e programa).
        kwargs.setdefault("auto_id", "evento_%s")
        super().__init__(*args, **kwargs)
        self.evento = evento
        atuais = list(evento.programas.values_list("pk", flat=True)) if evento else []
        cast(forms.ModelMultipleChoiceField, self.fields["programas"]).queryset = (
            ProgramaSolicitante.objects.filter(Q(ativo=True) | Q(pk__in=atuais)).order_by("nome"))
        cast(forms.ChoiceField, self.fields["horario"]).choices = _opcoes_de_horario(
            evento.horario if evento else "")
        self.fields["destinos"].widget.fonte = fonte_municipios
        self._carregar_unidades_e_cargos(
            list(evento.efetivo.values_list("unidade_id", "cargo_id")) if evento else [])
        marcadas = list(evento.atividades.values_list("pk", flat=True)) if evento else []
        cast(forms.ModelMultipleChoiceField, self.fields["atividades"]).queryset = (
            AtividadePlano.objects.filter(Q(ativo=True) | Q(pk__in=marcadas)).order_by("nome"))

    def clean(self):
        dados = super().clean() or {}
        # "Outro" marcado pede o texto; desmarcado, o texto não vale (como na folha).
        outro = dados.pop("programa_outro", False)
        dados["programa_outros"] = " ".join((dados.get("programa_outros") or "").split())
        if outro and not dados["programa_outros"]:
            self.add_error("programa_outros", "Informe o outro programa.")
        if not outro:
            dados["programa_outros"] = ""
        inicio, fim = dados.get("data_inicio"), dados.get("data_fim")
        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "A data final não pode ser anterior à data inicial.")
        if fim and not inicio:
            self.add_error("data_inicio", "Informe o início do evento.")
        saida, chegada = dados.get("saida_em"), dados.get("chegada_em")
        if saida and chegada and chegada <= saida:
            self.add_error("chegada_em", "A chegada na sede deve ser depois da saída.")
        dados["efetivo"] = self._efetivo()
        if self.erros_do_efetivo:
            self.add_error(None, "Efetivo: " + " ".join(self.erros_do_efetivo))
        return dados

    def periodo_texto(self) -> str:
        """O que o campo de período mostra: "13/10/2026 a 15/10/2026", ou só o início."""
        def texto(campo):
            v = self[campo].value()
            return v.strftime("%d/%m/%Y") if hasattr(v, "strftime") else (v or "")
        de, ate = texto("data_inicio"), texto("data_fim")
        return f"{de} a {ate}" if de and ate else de

    def atividades_marcadas(self) -> set[str]:
        """As atividades marcadas (ids em texto), para os cartões da janela."""
        return {str(v) for v in (self["atividades"].value() or [])}

    def resumo_programas(self) -> str:
        """O que o botão de programas mostra antes do JavaScript (o mesmo resumo dele)."""
        marcados = {str(v) for v in (self["programas"].value() or [])}
        opcoes = cast(forms.ModelMultipleChoiceField, self.fields["programas"]).queryset
        nomes = [p.nome for p in (opcoes if opcoes is not None else []) if str(p.pk) in marcados]
        if self["programa_outro"].value():
            nomes.append(self["programa_outros"].value() or "Outro")
        return ", ".join(nomes)

    @classmethod
    def de(cls, evento, **kwargs):
        programas = list(evento.programas.values_list("pk", flat=True)) or (
            [evento.programa_id] if evento.programa_id else [])
        return cls(evento=evento, initial={
            "programas": programas, "programa_outro": bool(evento.programa_outros),
            "programa_outros": evento.programa_outros,
            "data_inicio": evento.data_inicio,
            "data_fim": evento.data_fim if evento.data_fim != evento.data_inicio else None,
            "horario": evento.horario,
            "destinos": [str(d.municipio) for d in evento.destinos.all()],
            "saida_em": timezone.localtime(evento.saida_em) if evento.saida_em else None,
            "chegada_em": timezone.localtime(evento.chegada_em) if evento.chegada_em else None,
            "atividades": [a.pk for a in evento.atividades.all()]}, **kwargs)


# ---------------------------------------------------------------- viagem (módulo 8)
class _OpcaoDocumento(forms.ModelMultipleChoiceField):
    """Um documento para vincular: o nome dele e o que ajuda a reconhecer (período)."""

    def label_from_instance(self, obj) -> str:
        from .viagem import resumo_do_documento
        return resumo_do_documento(obj)


class FormularioViagem(forms.Form):
    """Etapa 1 da viagem (referência): tipos (o título nasce deles), motivo, período,
    destinos na ordem da visita e os documentos vinculados (marcar vincula, desmarcar solta)."""

    versao = forms.CharField(required=False, widget=forms.HiddenInput)
    tipos = forms.ModelMultipleChoiceField(
        label="Tipo da viagem", queryset=TipoViagem.objects.none(), required=False,
        widget=CaixasDeEscolha(), help_text="O título da viagem nasce deles.")
    motivo = forms.CharField(
        label="Motivo", required=False, max_length=4000,
        widget=forms.Textarea(attrs={"class": "area-texto", "rows": 3,
                                     "placeholder": "Contextualize a atividade…"}),
        help_text="Vai para os documentos criados daqui (ofício, OS).")
    descricao = forms.CharField(
        label="Descrição/objetivo", required=False, max_length=4000,
        widget=forms.Textarea(attrs={"class": "area-texto", "rows": 2}))
    # Período num campo só na tela (<pc-data data-periodo>, início e fim no mesmo
    # calendário), como no termo, na OS e no plano: estes dois levam as pontas.
    data_inicio = forms.DateField(label="Início", required=False, input_formats=FORMATOS_DATA,
                                  widget=forms.HiddenInput(attrs={"data-periodo-de": ""}))
    data_fim = forms.DateField(label="Fim", required=False, input_formats=FORMATOS_DATA,
                               widget=forms.HiddenInput(attrs={"data-periodo-ate": ""}))
    destinos = CampoMunicipios(label="Destinos", required=False,
                               help_text="Na ordem da visita; o primeiro é o principal.")
    roteiros = _OpcaoDocumento(label="Roteiros", queryset=Roteiro.objects.none(),
                               required=False, widget=CaixasDeEscolha())
    oficios = _OpcaoDocumento(label="Ofícios", queryset=Oficio.objects.none(),
                              required=False, widget=CaixasDeEscolha())
    planos = _OpcaoDocumento(label="Planos de trabalho", queryset=PlanoTrabalho.objects.none(),
                             required=False, widget=CaixasDeEscolha())
    ordens = _OpcaoDocumento(label="Ordens de serviço", queryset=OrdemServico.objects.none(),
                             required=False, widget=CaixasDeEscolha())
    termos = _OpcaoDocumento(label="Termos de autorização",
                             queryset=TermoAutorizacao.objects.none(), required=False,
                             widget=CaixasDeEscolha())
    # Só grava os vínculos quando a seção veio no formulário (a lista pode estar fechada).
    vinculos_presentes = forms.BooleanField(required=False, widget=forms.HiddenInput)
    # Os documentos que a tela mostrou (por tipo): desmarcar solta só estes. Um documento
    # vinculado depois que a tela abriu (outra aba, "Novo …") não é solto por engano.
    conhecidos = forms.CharField(required=False, widget=forms.HiddenInput)

    def periodo_texto(self) -> str:
        """O que o campo de período mostra: "13/10/2026 a 15/10/2026", ou só o início."""
        def texto(campo):
            v = self[campo].value()
            return v.strftime("%d/%m/%Y") if hasattr(v, "strftime") else (v or "")
        de, ate = texto("data_inicio"), texto("data_fim")
        return f"{de} a {ate}" if de and ate else de

    def __init__(self, *args, viagem, fonte_municipios: str = "", **kwargs):
        from .viagem import candidatos
        super().__init__(*args, **kwargs)
        self._mostrados: dict[str, list[int]] = {}
        atuais = list(viagem.tipos.values_list("pk", flat=True))
        cast(forms.ModelMultipleChoiceField, self.fields["tipos"]).queryset = (
            TipoViagem.objects.filter(Q(ativo=True) | Q(pk__in=atuais)).order_by("nome"))
        self.fields["destinos"].widget.fonte = fonte_municipios
        for tipo, qs in candidatos(viagem).items():
            # Os desta viagem sempre; dos livres, os 40 mais recentes (lista curta, legível).
            ids = list(qs.filter(viagem=viagem).values_list("pk", flat=True))
            ids += list(qs.filter(viagem__isnull=True).values_list("pk", flat=True)[:40])
            campo = cast(forms.ModelMultipleChoiceField, self.fields[tipo])
            campo.queryset = qs.model.objects.filter(pk__in=ids).order_by(*qs.query.order_by)
            self._mostrados[tipo] = ids
        if not self.is_bound:
            self.initial["conhecidos"] = json.dumps(self._mostrados, separators=(",", ":"))

    def clean(self):
        dados = super().clean() or {}
        inicio, fim = dados.get("data_inicio"), dados.get("data_fim")
        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "A data final não pode ser anterior à data inicial.")
        return dados

    def vinculos(self) -> dict | None:
        """{tipo: (marcados, ids que a tela mostrou)} — ou None sem a seção."""
        if not self.cleaned_data.get("vinculos_presentes"):
            return None
        try:
            conhecidos = json.loads(self.cleaned_data.get("conhecidos") or "{}")
        except ValueError:
            conhecidos = {}
        saida = {}
        for t in ("roteiros", "oficios", "planos", "ordens", "termos"):
            ids = conhecidos.get(t) if isinstance(conhecidos, dict) else None
            lista = ids if isinstance(ids, list) else []
            mostrados = {int(i) for i in lista if str(i).isdecimal()}
            saida[t] = (list(self.cleaned_data.get(t) or []), mostrados)
        return saida


# ---------------------------------------------------------------- gerar documentos em lote
class FormularioLote(forms.Form):
    """Gerar documentos (referência): um cartão por ofício — equipe, quem dirige e em qual
    viatura — e o que sai junto (termos, OS, plano)."""

    termos = forms.BooleanField(label="Termos de autorização", required=False, initial=True,
                                help_text="Um por servidor, menos quem é da unidade emissora.")
    ordem = forms.BooleanField(label="Ordem de serviço", required=False, initial=True,
                               help_text="Com toda a equipe e os ofícios.")
    plano = forms.BooleanField(label="Plano de trabalho", required=False, initial=True,
                               help_text="Com o efetivo e os destinos dos ofícios.")

    def __init__(self, *args, quantidade: int = 1, fonte_servidores: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.quantidade = max(1, min(quantidade, 20))
        ativos = Servidor.objects.filter(ativo=True)
        viaturas = (Viatura.objects.filter(ativo=True).order_by("placa")
                    .select_related("combustivel", "unidade").prefetch_related("motoristas"))
        for i in range(self.quantidade):
            equipe = forms.ModelMultipleChoiceField(
                label="Equipe", queryset=ativos, required=False,
                widget=CampoEquipe(fonte=fonte_servidores, cadastrar="dialogo-servidor"))
            equipe.widget.choices = equipe.choices
            motorista = forms.ModelMultipleChoiceField(
                label="Quem dirige (opcional)", queryset=ativos, required=False,
                help_text="Fora da equipe, entra na deste ofício.",
                widget=CampoEquipe(fonte=fonte_servidores, rotulo="Quem dirige (opcional)",
                                   rotulo_vazio="Ninguém escolhido para dirigir.",
                                   cadastrar="dialogo-servidor", maximo=1, motorista=True))
            motorista.widget.choices = motorista.choices
            self.fields[f"equipe_{i}"] = equipe
            self.fields[f"motorista_{i}"] = motorista
            self.fields[f"viatura_{i}"] = forms.ModelChoiceField(
                label="Viatura", queryset=viaturas, required=False,
                empty_label="Sem viatura", widget=SelecaoDeViatura(attrs=_attrs("selecao")))

    def cartoes(self) -> list[dict]:
        return [{"n": i + 1, "equipe": self[f"equipe_{i}"], "motorista": self[f"motorista_{i}"],
                 "viatura": self[f"viatura_{i}"]} for i in range(self.quantidade)]

    def clean(self):
        dados = super().clean() or {}
        for i in range(self.quantidade):
            if len(dados.get(f"motorista_{i}") or []) > 1:
                self.add_error(f"motorista_{i}", "Escolha um motorista só.")
        return dados

    def equipes(self):
        from .viagem_lote import Equipe
        saida = []
        for i in range(self.quantidade):
            motoristas = list(self.cleaned_data.get(f"motorista_{i}") or [])
            saida.append(Equipe(servidores=list(self.cleaned_data.get(f"equipe_{i}") or []),
                                motorista=motoristas[0] if motoristas else None,
                                viatura=self.cleaned_data.get(f"viatura_{i}")))
        return saida


class FormularioRepetir(forms.Form):
    """Repetir viagem (referência): a data da nova edição e, se mudar, a cidade."""

    nova_data = forms.DateField(label="Data da nova edição", widget=EntradaData(),
                                input_formats=FORMATOS_DATA,
                                error_messages={"required": "Informe a data da nova edição."})
    nova_cidade = CampoMunicipio(label="Nova cidade (se mudar)", required=False,
                                 help_text="Em branco, a mesma. Números, protocolos e "
                                           "assinaturas não são copiados.")
