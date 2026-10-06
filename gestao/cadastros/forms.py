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

from gestao.plataforma.widgets import (
    CaixasDeEscolha,
    EntradaData,
    EntradaHora,
    EscolhaMultiplaRemota,
    Selecao,
)

from .models import (
    AtividadePlano,
    Cargo,
    Combustivel,
    ModeloTexto,
    Municipio,
    Servidor,
    SubstituicaoAssinante,
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
    formatar_telefone,
    normalizar_placa,
    normalizar_rg,
    placa_valida,
    somente_digitos,
    titulo,
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
TAMANHO_MAXIMO_MUNICIPIO = 120


def resolver_municipio(texto: str) -> Municipio:
    """Aceita "Cidade/UF", "Cidade - UF" ou "Cidade, UF" (sem diferenciar acentos/caixa)."""
    texto = (texto or "").strip()
    if len(texto) > TAMANHO_MAXIMO_MUNICIPIO:  # nome de município não passa disso
        raise forms.ValidationError("Informe a cidade e a UF, ex.: Arapongas/PR.",
                                    code="formato_municipio")
    # Linear (o ".+?" seguido de "\s*" era quadrático com muitos espaços).
    m = re.match(r"^(?P<nome>.*\S)\s*[/,-]\s*(?P<uf>[A-Za-z]{2})$", texto)
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
        kwargs.setdefault("max_length", TAMANHO_MAXIMO_MUNICIPIO)
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
        return titulo(self.cleaned_data["nome"])

    def clean_sigla(self) -> str:
        return espacos(self.cleaned_data["sigla"]).upper()

    @classmethod
    def de(cls, unidade: Unidade) -> FormularioUnidade:
        return cls(initial={"nome": unidade.nome, "sigla": unidade.sigla})


class FormularioCatalogo(forms.Form):
    """Cargo ou combustível: só o nome; o padrão se escolhe no menu da linha."""

    nome = forms.CharField(label="Nome", max_length=120, widget=_entrada())

    def clean_nome(self) -> str:
        return titulo(self.cleaned_data["nome"])

    @classmethod
    def de(cls, objeto) -> FormularioCatalogo:
        return cls(initial={"nome": objeto.nome})


# ---------------------------------------------------------------- servidor
class FormularioServidor(forms.Form):
    nome = forms.CharField(label="Nome completo", max_length=255,
                           widget=_entrada(autocomplete="name"))
    cargo = forms.ModelChoiceField(label="Cargo", queryset=Cargo.objects.none(),
                                   required=False, empty_label="Selecione (opcional)",
                                   widget=Selecao())
    # Declarados à mão: o modelo guarda só dígitos (11), mas digita-se com pontuação.
    cpf = forms.CharField(label="CPF", max_length=14, required=False,
                          widget=_entrada(inputmode="numeric", placeholder="000.000.000-00",
                                          **{"data-mascara": "cpf"}))
    rg = forms.CharField(label="RG", max_length=30, required=False,
                         widget=_entrada(placeholder="00.000.000-0",
                                         **{"data-mascara": "rg"}))
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
        nome = titulo(self.cleaned_data["nome"])
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
        """Em branco é "não possui RG": ninguém precisa escrever a frase.

        O cadastro guarda a marca, e não o vazio, para o documento poder dizer que a
        pessoa não tem RG em vez de deixar um espaço que parece esquecimento."""
        rg = normalizar_rg(self.cleaned_data["rg"])
        if not rg:
            return RG_NAO_POSSUI
        if rg != RG_NAO_POSSUI:
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
        return titulo(self.cleaned_data["modelo"])


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
    # A ordem continua no banco (`ModeloTexto.ordem`, padrão 100), mas não se digita: quem
    # cadastra pensa no nome, não num número de posição. `textos.salvar` sem `ordem` mantém
    # a que o registro já tem.
    texto = forms.CharField(
        label="Texto", max_length=4000,
        help_text="Entra no campo exatamente como escrito; dá para ajustar depois de inserir.",
        widget=forms.Textarea(attrs={"class": "area-texto", "rows": 6}))

    @classmethod
    def de(cls, modelo: ModeloTexto) -> FormularioTexto:
        return cls(initial={"tipo": modelo.tipo, "nome": modelo.nome,
                            "texto": modelo.texto})


# ---------------------------------------------------------------- configuração da unidade
class OpcaoServidor(forms.ModelChoiceField):
    def label_from_instance(self, obj) -> str:
        return f"{obj.nome} — {obj.descricao}" if obj.descricao else obj.nome


def _servidores(*atuais: int | None):
    return (Servidor.objects.filter(Q(ativo=True) | Q(pk__in=[a for a in atuais if a]))
            .select_related("cargo", "unidade").order_by("nome"))


class FormularioConfiguracao(forms.Form):
    """Dados da unidade emissora que entram nos documentos (cabeçalho, rodapé, quem assina,
    destinatário) e a antecedência que dispensa justificativa."""

    nome_extenso = forms.CharField(label="Nome da unidade no cabeçalho", max_length=160,
                                   widget=_entrada())
    sede = CampoMunicipio(label="Cidade sede",
                          help_text="Origem padrão das viagens e cidade da data do ofício.")
    cep = forms.CharField(label="CEP", max_length=9, required=False,
                          widget=_entrada(inputmode="numeric", placeholder="00000-000",
                                          **{"data-mascara": "cep"}))
    logradouro = forms.CharField(label="Logradouro", max_length=160, required=False,
                                 widget=_entrada(placeholder="Rua, avenida…"))
    numero = forms.CharField(label="Número", max_length=20, required=False, widget=_entrada())
    bairro = forms.CharField(label="Bairro", max_length=120, required=False, widget=_entrada())
    cidade_endereco = forms.CharField(label="Cidade", max_length=120, required=False,
                                      widget=_entrada())
    uf = forms.CharField(label="UF", max_length=2, required=False,
                         widget=_entrada(placeholder="PR"))
    email = forms.EmailField(label="E-mail", required=False,
                             widget=forms.EmailInput(attrs={"class": "entrada",
                                                            "autocomplete": "off"}))
    telefone = forms.CharField(label="Telefone", max_length=20, required=False,
                               widget=_entrada(inputmode="tel", placeholder="(00) 0000-0000",
                                               **{"data-mascara": "telefone"}))
    ramal = forms.CharField(label="Ramal", max_length=20, required=False, widget=_entrada())
    endereco_rodape = forms.CharField(
        label="Texto do rodapé", max_length=255, required=False,
        help_text="Como deve sair no rodapé. Em branco, é montado a partir do endereço acima.",
        widget=_entrada())
    assina_oficio = OpcaoServidor(
        label="Assina os ofícios", queryset=Servidor.objects.none(), required=False,
        empty_label="A chefia (abaixo)")
    assina_justificativa = OpcaoServidor(
        label="Assina as justificativas", queryset=Servidor.objects.none(), required=False,
        empty_label="A chefia (abaixo)")
    chefia_nome = forms.CharField(label="Chefia", max_length=150,
                                  help_text="Assina quando não há assinante escolhido.",
                                  widget=_entrada())
    chefia_cargo = forms.CharField(label="Cargo da chefia", max_length=150,
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
    delegado_geral_nome = forms.CharField(
        label="Delegado-Geral", max_length=120, required=False,
        help_text="Sai na Ordem de Serviço: “atribuições conferidas pelo Delegado-Geral …”.",
        widget=_entrada())
    # Plano de trabalho (referência: sem assinante, o plano sai sem nome — não cai na chefia).
    assina_plano = OpcaoServidor(
        label="Assina os planos de trabalho", queryset=Servidor.objects.none(), required=False,
        empty_label="Ninguém (o plano sai sem nome)")
    coordenador_plano = OpcaoServidor(
        label="Coordenador administrativo padrão", queryset=Servidor.objects.none(),
        required=False, empty_label="Nenhum",
        help_text="Sugerido em todo plano de trabalho novo.")
    sufixo_plano = forms.CharField(
        label="Sufixo da numeração do plano", max_length=20, required=False,
        help_text="Ex.: 07/2026/ASCOM. Em branco, vale a sigla da unidade.", widget=_entrada())

    SERVIDORES = ("assina_oficio", "assina_justificativa", "assina_plano", "coordenador_plano")

    def __init__(self, *args, config=None, **kwargs):
        super().__init__(*args, **kwargs)
        atuais = [getattr(config, f"{c}_id") for c in self.SERVIDORES] if config else []
        for campo in self.SERVIDORES:
            cast(forms.ModelChoiceField, self.fields[campo]).queryset = _servidores(*atuais)

    def clean_sufixo_plano(self) -> str:
        return espacos(self.cleaned_data["sufixo_plano"]).upper()

    @classmethod
    def de(cls, config) -> FormularioConfiguracao:
        from .services import CAMPOS_CONFIGURACAO
        inicial = {c: getattr(config, c) for c in CAMPOS_CONFIGURACAO
                   if c not in cls.SERVIDORES}
        for campo in cls.SERVIDORES:
            inicial[campo] = getattr(config, f"{campo}_id")
        inicial["sede"] = str(config.sede) if config.sede_id else ""
        cep = config.cep
        inicial["cep"] = f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else cep
        inicial["telefone"] = formatar_telefone(config.telefone)
        return cls(initial=inicial, config=config)

    def clean_cep(self) -> str:
        cep = somente_digitos(self.cleaned_data["cep"])
        if cep and len(cep) != 8:
            raise forms.ValidationError("O CEP tem 8 dígitos.")
        return cep

    def clean_telefone(self) -> str:
        telefone = somente_digitos(self.cleaned_data["telefone"])
        if telefone and len(telefone) not in (10, 11):
            raise forms.ValidationError("Informe o telefone com DDD (10 ou 11 dígitos).")
        return telefone

    def clean_uf(self) -> str:
        uf = espacos(self.cleaned_data["uf"]).upper()
        if uf and not (len(uf) == 2 and uf.isascii() and uf.isalpha()):
            raise forms.ValidationError("Informe a sigla do estado, ex.: PR.")
        return uf

    def clean(self):
        dados = super().clean() or {}
        for campo, valor in list(dados.items()):
            if isinstance(valor, str):
                dados[campo] = espacos(valor)
        return dados


class FormularioSubstituicao(forms.Form):
    """Substituto por período (férias, afastamento do titular)."""

    servidor = OpcaoServidor(label="Substituto", queryset=Servidor.objects.none(),
                             empty_label="Escolha o servidor")
    tipo = forms.ChoiceField(label="Documentos", widget=Selecao(),
                             choices=SubstituicaoAssinante.Tipo.choices)
    inicio = forms.DateField(label="Início", widget=EntradaData())
    fim = forms.DateField(label="Fim", required=False, widget=EntradaData(),
                          help_text="Em branco: até ser encerrada.")
    motivo = forms.CharField(label="Motivo", max_length=120, required=False,
                             widget=_entrada(placeholder="Ex.: férias do titular"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cast(forms.ModelChoiceField, self.fields["servidor"]).queryset = _servidores()

    def clean(self):
        dados = super().clean() or {}
        inicio, fim = dados.get("inicio"), dados.get("fim")
        if inicio and fim and fim < inicio:
            self.add_error("fim", "O fim não pode ser antes do início.")
        return dados


# ---------------------------------------------------------------- plano de trabalho
class FormularioPrograma(FormularioCatalogo):
    """Programa solicitante: gravado em maiúsculas, como na referência."""

    nome = forms.CharField(label="Programa", max_length=200, widget=_entrada())

    def clean_nome(self) -> str:
        return espacos(self.cleaned_data["nome"]).upper()


class FormularioHorario(forms.Form):
    """Horário de atendimento: início e fim digitados; grava "HH:MM até HH:MM"."""

    inicio = forms.TimeField(label="Horário de início", widget=EntradaHora(),
                             input_formats=["%H:%M"])
    fim = forms.TimeField(label="Horário de fim", widget=EntradaHora(), input_formats=["%H:%M"])

    def clean(self):
        dados = super().clean() or {}
        inicio, fim = dados.get("inicio"), dados.get("fim")
        if inicio and fim:
            if fim <= inicio:
                self.add_error("fim", "O fim precisa ser depois do início.")
            else:
                dados["nome"] = f"{inicio:%H:%M} até {fim:%H:%M}"
        return dados

    @property
    def cleaned_para_salvar(self) -> dict:
        return {"nome": self.cleaned_data["nome"]}

    @classmethod
    def de(cls, objeto) -> FormularioHorario:
        partes = objeto.nome.split(" até ")
        inicial = {"inicio": partes[0], "fim": partes[1]} if len(partes) == 2 else {}
        return cls(initial=inicial)


class FormularioAtividade(forms.Form):
    nome = forms.CharField(label="Atividade", max_length=255, widget=_entrada())
    meta = forms.CharField(label="Meta", widget=forms.Textarea(attrs={
        "class": "entrada area-texto", "rows": 3}),
        help_text="Sai em “Metas estabelecidas” de todo plano que marcar esta atividade.")
    recurso = forms.CharField(label="Recursos necessários", required=False,
                              widget=forms.Textarea(attrs={"class": "entrada area-texto",
                                                           "rows": 3}),
                              help_text="Opcional. Sai em “Recursos necessários”.")

    def clean_nome(self) -> str:
        return titulo(self.cleaned_data["nome"])

    def clean_meta(self) -> str:
        return self.cleaned_data["meta"].strip()

    def clean_recurso(self) -> str:
        return self.cleaned_data["recurso"].strip()

    @property
    def cleaned_para_salvar(self) -> dict:
        return dict(self.cleaned_data)

    @classmethod
    def de(cls, objeto) -> FormularioAtividade:
        return cls(initial={"nome": objeto.nome, "meta": objeto.meta, "recurso": objeto.recurso})


class FormularioPreset(forms.Form):
    nome = forms.CharField(label="Nome do conjunto", max_length=200, widget=_entrada())
    descricao = forms.CharField(label="Descrição", max_length=255, required=False,
                                widget=_entrada())
    atividades = forms.ModelMultipleChoiceField(
        label="Atividades", queryset=AtividadePlano.objects.none(), widget=CaixasDeEscolha(),
        error_messages={"required": "Selecione ao menos uma atividade."})
    padrao = forms.BooleanField(label="Usar como padrão", required=False,
                                help_text="Vem marcado em todo plano de trabalho novo.")

    def __init__(self, *args, atuais=(), **kwargs):
        super().__init__(*args, **kwargs)
        campo = cast(forms.ModelMultipleChoiceField, self.fields["atividades"])
        campo.queryset = AtividadePlano.objects.filter(
            Q(ativo=True) | Q(pk__in=list(atuais))).order_by("nome")

    def clean_nome(self) -> str:
        return espacos(self.cleaned_data["nome"]).upper()

    @property
    def cleaned_para_salvar(self) -> dict:
        return dict(self.cleaned_data)

    @classmethod
    def de(cls, objeto) -> FormularioPreset:
        atuais = [a.pk for a in objeto.atividades.all()]
        return cls(atuais=atuais, initial={"nome": objeto.nome, "descricao": objeto.descricao,
                                           "atividades": atuais, "padrao": objeto.padrao})


# ---------------------------------------------------------------- usuários do sistema
class FormularioUsuario(forms.Form):
    """Usuário do sistema (paridade com o cadastro de usuários da referência): nome, login,
    e-mail institucional, perfis, lotação e senha inicial (troca obrigatória no 1º acesso)."""

    nome = forms.CharField(label="Nome completo", max_length=150,
                           widget=_entrada(autocomplete="off"))
    login = forms.CharField(label="Usuário", max_length=60,
                            help_text="Usado para entrar no sistema (o e-mail também serve).",
                            widget=_entrada(autocapitalize="none", spellcheck="false"))
    email = forms.EmailField(label="E-mail institucional",
                             widget=forms.EmailInput(attrs={"class": "entrada",
                                                            "autocomplete": "off"}))
    papeis = forms.MultipleChoiceField(label="Perfis de acesso", required=False,
                                       widget=CaixasDeEscolha())
    unidade = OpcaoUnidade(label="Unidade de lotação", queryset=Unidade.objects.none(),
                           required=False, empty_label="Selecione",
                           help_text="Define os ofícios e documentos que a pessoa vê.")
    senha = forms.CharField(label="Senha inicial", required=False, strip=False,
                            widget=forms.PasswordInput(attrs={"class": "entrada",
                                                              "autocomplete": "new-password"}))
    confirmacao = forms.CharField(label="Confirmação da senha", required=False, strip=False,
                                  widget=forms.PasswordInput(attrs={
                                      "class": "entrada", "autocomplete": "new-password"}))

    def __init__(self, *args, instancia=None, **kwargs):
        from django.conf import settings

        from gestao.identidade.papeis import PAPEIS
        super().__init__(*args, **kwargs)
        self.instancia = instancia
        papeis = cast(forms.MultipleChoiceField, self.fields["papeis"])
        rotulos = {"OPERADOR_VIAGENS": "Operador de viagens",
                   "GESTOR_VIAGENS": "Gestor de viagens", "CONSULTA": "Consulta",
                   "ADMINISTRADOR": "Administrador"}
        papeis.choices = [(nome, rotulos.get(nome, nome)) for nome in PAPEIS]
        papeis.help_text = " · ".join(f"{rotulos.get(n, n)}: {p['descricao']}"
                                      for n, p in PAPEIS.items())
        lotacao = getattr(instancia, "lotacao", None) if instancia else None
        unidade = cast(forms.ModelChoiceField, self.fields["unidade"])
        unidade.queryset = _unidades(lotacao.unidade_id if lotacao else None)
        senha = self.fields["senha"]
        if instancia is not None:
            senha.label = "Nova senha"
            senha.help_text = "Deixe em branco para manter a senha atual."
        else:
            validadores = cast(list[dict], settings.AUTH_PASSWORD_VALIDATORS)
            minimo = next((v.get("OPTIONS", {}).get("min_length", 8) for v in validadores
                           if str(v["NAME"]).endswith("MinimumLengthValidator")), 8)
            senha.help_text = (f"Mínimo de {minimo} caracteres. A pessoa troca por uma só "
                               "dela no primeiro acesso.")

    @classmethod
    def de(cls, usuario) -> FormularioUsuario:
        lotacao = getattr(usuario, "lotacao", None)
        return cls(instancia=usuario, initial={
            "nome": usuario.nome, "login": usuario.login, "email": usuario.email,
            "papeis": list(usuario.groups.values_list("name", flat=True)),
            "unidade": lotacao.unidade_id if lotacao else None})

    def clean_nome(self) -> str:
        return titulo(self.cleaned_data["nome"])

    def clean_login(self) -> str:
        from gestao.identidade.models import Usuario
        login = self.cleaned_data["login"].strip()
        if not re.fullmatch(r"[\w.@+-]+", login):
            raise forms.ValidationError("Use só letras, números e . @ + - _ (sem espaços).")
        repetido = Usuario.objects.filter(login__iexact=login)
        if self.instancia is not None:
            repetido = repetido.exclude(pk=self.instancia.pk)
        if repetido.exists():
            raise forms.ValidationError("Já existe um usuário com este login.")
        return login

    def clean_email(self) -> str:
        from django.conf import settings

        from gestao.identidade.models import Usuario
        email = self.cleaned_data["email"].strip().lower()
        dominio = getattr(settings, "DOMINIO_EMAIL_INSTITUCIONAL", "")
        mantido = self.instancia is not None and self.instancia.email.lower() == email
        if dominio and not mantido and not email.endswith("@" + dominio):
            raise forms.ValidationError(f"Use o e-mail institucional (@{dominio}).")
        repetido = Usuario.objects.filter(email__iexact=email)
        if self.instancia is not None:
            repetido = repetido.exclude(pk=self.instancia.pk)
        if repetido.exists():
            raise forms.ValidationError("Já existe um usuário com este e-mail.")
        return email

    def clean(self):
        from django.contrib.auth import password_validation

        dados = super().clean() or {}
        senha, confirmacao = dados.get("senha") or "", dados.get("confirmacao") or ""
        if self.instancia is None and not senha:
            self.add_error("senha", "Defina a senha inicial do usuário.")
        elif senha or confirmacao:
            if senha != confirmacao:
                self.add_error("confirmacao", "As senhas não conferem.")
            else:
                try:
                    password_validation.validate_password(senha, self.instancia)
                except forms.ValidationError as exc:
                    self.add_error("senha", exc)
        return dados


def formularios_de_cadastro_rapido() -> dict[str, forms.Form]:
    """Os formulários dos diálogos de cadastro rápido (componentes/dialogos_cadastro.html):
    servidor e viatura, cadastrados sem sair da folha em qualquer tela que os escolhe."""
    from django.urls import reverse
    return {"form_servidor": FormularioServidor(),
            "form_viatura": FormularioViatura(
                fonte_motoristas=reverse("cadastros:buscar_servidores"))}
