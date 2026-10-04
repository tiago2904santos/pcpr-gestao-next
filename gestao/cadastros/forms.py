"""Formulários dos cadastros de apoio.

Validam e normalizam (o erro aparece no campo certo); quem grava é `services.py`.
Os limites seguem a referência: CPF com dígito verificador, placa antiga ou Mercosul,
telefone com DDD (10 ou 11 dígitos), RG livre (só letras e números) ou "não possui".
"""

from __future__ import annotations

import re
from typing import cast

from django import forms
from django.contrib.postgres.lookups import Unaccent
from django.db.models import Q, Value
from django.db.models.functions import Lower

from gestao.plataforma.widgets import EntradaData, EscolhaMultiplaRemota, Selecao

from .models import (
    Cargo,
    Combustivel,
    ModeloTexto,
    Municipio,
    Servidor,
    TabelaDiaria,
    Unidade,
    Viatura,
)
from .services import DIARIA_MINIMA
from .textos import TIPOS_EDITAVEIS
from .validacoes import (
    RG_NAO_POSSUI,
    cpf_valido,
    espacos,
    normalizar_placa,
    normalizar_rg,
    placa_valida,
    somente_digitos,
)


def _entrada(**attrs) -> forms.TextInput:
    return forms.TextInput(attrs={"class": "entrada", "autocomplete": "off", **attrs})


class OpcaoUnidade(forms.ModelChoiceField):
    """Unidade escolhida pela sigla ou pelo nome (a busca do campo acha os dois)."""

    def label_from_instance(self, obj) -> str:
        return f"{obj.sigla} — {obj.nome}" if obj.sigla else obj.nome


def _unidades(atual: int | None = None):
    return Unidade.objects.filter(Q(ativo=True) | Q(pk=atual)).order_by("sigla", "nome")


# ---------------------------------------------------------------- município
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
        kwargs.setdefault("widget", forms.TextInput(attrs={
            "class": "entrada", "placeholder": "Cidade/UF", "autocomplete": "off",
            "data-municipio": ""}))
        super().__init__(**kwargs)

    def clean(self, value):
        value = super().clean(value)
        if not value:
            return None
        return resolver_municipio(value)



# ---------------------------------------------------------------- unidade, cargo, combustível
class FormularioUnidade(forms.Form):
    nome = forms.CharField(label="Nome", max_length=255, widget=_entrada())
    sigla = forms.CharField(label="Sigla", max_length=50, required=False,
                            help_text="Como aparece nas listas. Ex.: ASCOM.",
                            widget=_entrada())

    def clean_nome(self) -> str:
        return espacos(self.cleaned_data["nome"])

    def clean_sigla(self) -> str:
        return espacos(self.cleaned_data["sigla"]).upper()

    @classmethod
    def de(cls, unidade: Unidade) -> FormularioUnidade:
        return cls(initial={"nome": unidade.nome, "sigla": unidade.sigla})


class FormularioCatalogo(forms.Form):
    """Cargo ou combustível: só o nome; o padrão se escolhe no menu da linha."""

    nome = forms.CharField(label="Nome", max_length=120, widget=_entrada())

    def clean_nome(self) -> str:
        return espacos(self.cleaned_data["nome"])

    @classmethod
    def de(cls, objeto) -> FormularioCatalogo:
        return cls(initial={"nome": objeto.nome})


# ---------------------------------------------------------------- servidor
class FormularioServidor(forms.Form):
    nome = forms.CharField(label="Nome completo", max_length=255,
                           widget=_entrada(autocomplete="name"))
    cargo = forms.ModelChoiceField(label="Cargo", queryset=Cargo.objects.none(),
                                   required=False, empty_label="Selecione (opcional)",
                                   help_text="Não achou? Salve sem cargo e complete depois.",
                                   widget=Selecao())
    # Declarados à mão: o modelo guarda só dígitos (11), mas digita-se com pontuação.
    cpf = forms.CharField(label="CPF", max_length=14, required=False,
                          widget=_entrada(inputmode="numeric", placeholder="000.000.000-00",
                                          **{"data-mascara": "cpf"}))
    rg = forms.CharField(label="RG", max_length=30, required=False,
                         help_text="Sem RG: escreva “não possui”.",
                         widget=_entrada(placeholder="00.000.000-0"))
    telefone = forms.CharField(label="Telefone", max_length=20, required=False,
                               widget=_entrada(inputmode="tel", autocomplete="tel",
                                               placeholder="(00) 00000-0000",
                                               **{"data-mascara": "telefone"}))
    unidade = OpcaoUnidade(label="Unidade de lotação", queryset=Unidade.objects.none(),
                           required=False, empty_label="Selecione (opcional)")

    def __init__(self, *args, instancia: Servidor | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instancia = instancia
        atual_cargo = instancia.cargo_id if instancia else None
        cargo = cast(forms.ModelChoiceField, self.fields["cargo"])
        cargo.queryset = Cargo.objects.filter(Q(ativo=True) | Q(pk=atual_cargo))
        unidade = cast(forms.ModelChoiceField, self.fields["unidade"])
        unidade.queryset = _unidades(instancia.unidade_id if instancia else None)
        if instancia is None and not self.is_bound:
            padrao = Cargo.objects.filter(padrao=True, ativo=True).first()
            if padrao:  # o cargo padrão já vem escolhido no servidor novo (referência)
                self.initial.setdefault("cargo", padrao.pk)

    @classmethod
    def de(cls, servidor: Servidor) -> FormularioServidor:
        return cls(instancia=servidor, initial={
            "nome": servidor.nome, "cargo": servidor.cargo_id, "cpf": servidor.cpf_formatado,
            "rg": servidor.rg, "telefone": servidor.telefone_formatado,
            "unidade": servidor.unidade_id})

    def _outro(self, **filtro) -> Servidor | None:
        outros = Servidor.objects.filter(**filtro)
        if self.instancia is not None:
            outros = outros.exclude(pk=self.instancia.pk)
        return outros.first()

    def _repetido(self, documento: str, **filtro) -> None:
        """Diz onde está o cadastro que já existe — inclusive se está inativo (a pessoa
        procurou na aba Ativos e não achou)."""
        outro = self._outro(**filtro)
        if outro is None:
            return
        onde = " (inativo: reative-o na aba Inativos)" if not outro.ativo else ""
        raise forms.ValidationError(f"Já existe um servidor com este {documento}: "
                                    f"{outro.nome}{onde}.")

    def clean_nome(self) -> str:
        nome = espacos(self.cleaned_data["nome"])
        self._repetido("nome", nome__iexact=nome)
        return nome

    def clean_cpf(self) -> str:
        cpf = somente_digitos(self.cleaned_data["cpf"])
        if not cpf:
            return ""
        if len(cpf) != 11:
            raise forms.ValidationError("O CPF tem 11 dígitos.")
        # O dígito verificador só é conferido quando o CPF muda: um cadastro antigo com CPF
        # que não confere (ex.: dados DEMO, fictícios de propósito) continua editável.
        mudou = self.instancia is None or cpf != self.instancia.cpf
        if mudou and not cpf_valido(cpf):
            raise forms.ValidationError("CPF inválido: confira os dígitos.")
        self._repetido("CPF", cpf=cpf)
        return cpf

    def clean_rg(self) -> str:
        rg = normalizar_rg(self.cleaned_data["rg"])
        if rg and rg != RG_NAO_POSSUI:
            self._repetido("RG", rg=rg)
        return rg

    def clean_telefone(self) -> str:
        telefone = somente_digitos(self.cleaned_data["telefone"])
        if not telefone:
            return ""
        if len(telefone) not in (10, 11):
            raise forms.ValidationError("Informe o telefone com DDD (10 ou 11 dígitos).")
        self._repetido("telefone", telefone=telefone)
        return telefone


# ---------------------------------------------------------------- viatura
class FormularioViatura(forms.Form):
    placa = forms.CharField(label="Placa", max_length=10,
                            help_text="Formato antigo (ABC1234) ou Mercosul (ABC1D23).",
                            widget=_entrada(placeholder="ABC1D23",
                                            **{"data-mascara": "placa"}))
    modelo = forms.CharField(label="Modelo", max_length=120, required=False, widget=_entrada())
    tipo = forms.ChoiceField(label="Tipo", choices=Viatura.Tipo.choices, required=False,
                             widget=Selecao())
    combustivel = forms.ModelChoiceField(label="Combustível",
                                         queryset=Combustivel.objects.none(), required=False,
                                         empty_label="Selecione (opcional)", widget=Selecao())
    unidade = OpcaoUnidade(label="Unidade", queryset=Unidade.objects.none(), required=False,
                           empty_label="Selecione (opcional)")
    motoristas = forms.ModelMultipleChoiceField(
        label="Motoristas habituais", queryset=Servidor.objects.all(), required=False,
        help_text="Ao marcar um deles como motorista no ofício, esta viatura é escolhida.")

    def __init__(self, *args, instancia: Viatura | None = None, fonte_motoristas: str = "",
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.instancia = instancia
        combustivel = cast(forms.ModelChoiceField, self.fields["combustivel"])
        combustivel.queryset = Combustivel.objects.filter(
            Q(ativo=True) | Q(pk=instancia.combustivel_id if instancia else None))
        unidade = cast(forms.ModelChoiceField, self.fields["unidade"])
        unidade.queryset = _unidades(instancia.unidade_id if instancia else None)
        motoristas = cast(forms.ModelMultipleChoiceField, self.fields["motoristas"])
        atuais = list(instancia.motoristas.values_list("pk", flat=True)) if instancia else []
        motoristas.queryset = Servidor.objects.filter(Q(ativo=True) | Q(pk__in=atuais))
        motoristas.widget = EscolhaMultiplaRemota(
            fonte=fonte_motoristas, rotulo_vazio="Nenhum motorista escolhido.",
            placeholder="Nome, cargo ou CPF…")
        motoristas.widget.choices = motoristas.choices  # o widget acha os escolhidos por aqui
        if instancia is None and not self.is_bound:
            self.initial.setdefault("tipo", Viatura.Tipo.DESCARACTERIZADA)
            padrao = Combustivel.objects.filter(padrao=True, ativo=True).first()
            if padrao:  # o combustível padrão já vem escolhido na viatura nova
                self.initial.setdefault("combustivel", padrao.pk)

    @classmethod
    def de(cls, viatura: Viatura, **kwargs) -> FormularioViatura:
        return cls(instancia=viatura, initial={
            "placa": viatura.placa_formatada, "modelo": viatura.modelo, "tipo": viatura.tipo,
            "combustivel": viatura.combustivel_id, "unidade": viatura.unidade_id,
            "motoristas": [m.pk for m in viatura.motoristas.all()]}, **kwargs)

    def clean_placa(self) -> str:
        placa = normalizar_placa(self.cleaned_data["placa"])
        if not placa_valida(placa):
            raise forms.ValidationError("Placa inválida. Use o formato ABC1234 ou ABC1D23.")
        outras = Viatura.objects.filter(placa=placa)
        if self.instancia is not None:
            outras = outras.exclude(pk=self.instancia.pk)
        if (outra := outras.first()) is not None:
            onde = " (inativa: reative-a na aba Inativas)" if not outra.ativo else ""
            raise forms.ValidationError(f"Já existe uma viatura com esta placa{onde}.")
        return placa

    def clean_modelo(self) -> str:
        return espacos(self.cleaned_data["modelo"])


# ---------------------------------------------------------------- tabela de diárias
class FormularioVigencia(forms.Form):
    faixa = forms.ChoiceField(label="Faixa", choices=TabelaDiaria.Faixa.choices,
                              widget=Selecao())
    vigente_desde = forms.DateField(label="Vigente a partir de", widget=EntradaData(),
                                    help_text="Viagens com saída a partir desta data usam "
                                              "este valor.")
    valor_24h = forms.DecimalField(
        label="Diária de 24 horas", max_digits=10, decimal_places=2, min_value=DIARIA_MINIMA,
        widget=forms.NumberInput(attrs={"class": "entrada", "step": "0.01",
                                        "min": str(DIARIA_MINIMA), "inputmode": "decimal",
                                        "data-diaria-base": ""}),
        # "%%": a mensagem passa por formatação com %(limit_value)s.
        error_messages={"min_value": "Valor muito baixo: o percentual de 15%% ficaria zerado."})
    norma = forms.CharField(label="Norma de referência", max_length=200, required=False,
                            help_text="Ex.: decreto ou resolução que fixou o valor.",
                            widget=_entrada())

    @classmethod
    def de(cls, vigencia: TabelaDiaria) -> FormularioVigencia:
        return cls(initial={"faixa": vigencia.faixa, "vigente_desde": vigencia.vigente_desde,
                            "valor_24h": vigencia.valor_24h, "norma": vigencia.norma})


# ---------------------------------------------------------------- textos prontos
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


# ---------------------------------------------------------------- configuração da unidade
class FormularioConfiguracao(forms.Form):
    """Dados da unidade emissora que entram nos documentos (cabeçalho, rodapé, quem assina,
    destinatário) e a antecedência que dispensa justificativa."""

    nome_extenso = forms.CharField(label="Nome da unidade no cabeçalho", max_length=160,
                                   widget=_entrada())
    sede = CampoMunicipio(label="Cidade sede",
                          help_text="Origem padrão das viagens e cidade da data do ofício.")
    endereco_rodape = forms.CharField(
        label="Endereço no rodapé", max_length=255,
        help_text="Endereço, CEP, telefone e e-mail como devem sair no rodapé.",
        widget=_entrada())
    chefia_nome = forms.CharField(label="Quem assina (chefia)", max_length=150,
                                  widget=_entrada())
    chefia_cargo = forms.CharField(label="Cargo de quem assina", max_length=150,
                                   widget=_entrada())
    destinatario_tratamento = forms.CharField(label="Tratamento", max_length=40,
                                              help_text="Ex.: Exmo. Sr, Exma. Sra.",
                                              widget=_entrada())
    destinatario_nome = forms.CharField(label="Destinatário", max_length=150,
                                        widget=_entrada())
    destinatario_cargo = forms.CharField(label="Cargo do destinatário", max_length=150,
                                         widget=_entrada())
    destinatario_orgao = forms.CharField(label="Órgão de destino", max_length=160,
                                         widget=_entrada())
    destinatario_cidade = forms.CharField(label="Cidade do destinatário", max_length=80,
                                          widget=_entrada())
    prazo_justificativa_dias = forms.IntegerField(
        label="Antecedência mínima (dias)", min_value=0, max_value=365,
        help_text="Viagem com esta antecedência ou menos exige justificativa.",
        widget=forms.NumberInput(attrs={"class": "entrada", "inputmode": "numeric"}))

    @classmethod
    def de(cls, config) -> FormularioConfiguracao:
        from .services import CAMPOS_CONFIGURACAO
        inicial = {c: getattr(config, c) for c in CAMPOS_CONFIGURACAO}
        inicial["sede"] = str(config.sede) if config.sede_id else ""
        return cls(initial=inicial)

    def clean(self):
        dados = super().clean() or {}
        for campo, valor in list(dados.items()):
            if isinstance(valor, str):
                dados[campo] = espacos(valor)
        return dados
