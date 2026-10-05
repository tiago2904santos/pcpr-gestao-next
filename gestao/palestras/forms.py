"""Formulários das palestras e eventos.

O município é "Cidade/UF" com a busca dos cadastros (funciona sem JavaScript); temas em
caixas; palestrantes por busca (vários). Telefone, CEP e protocolo são conferidos e
formatados pelo serviço (regras em `dominio`).
"""

from __future__ import annotations

from typing import Any, cast

from django import forms
from django.urls import reverse

from gestao.cadastros.forms import CampoMunicipio
from gestao.cadastros.models import Servidor
from gestao.plataforma.widgets import (
    FORMATOS_DATA,
    CaixasDeEscolha,
    EntradaData,
    EntradaHora,
    EscolhaMultiplaRemota,
    Selecao,
)

from . import dominio
from .models import Palestra, Palestrante, RespostaPadrao, Tema

FORM_ID = "form-palestra"


def _attrs(**extra: Any) -> dict[str, Any]:
    return {"class": "entrada", **extra}


def _texto(linhas: int, dica: str = "") -> forms.Textarea:
    return forms.Textarea(attrs=_attrs(rows=linhas, placeholder=dica))


class FormularioPalestra(forms.ModelForm):
    data_solicitacao = forms.DateField(label="Data da solicitação", input_formats=FORMATOS_DATA,
                                       widget=EntradaData())
    data_inicio_evento = forms.DateField(label="Data do evento", required=False,
                                         input_formats=FORMATOS_DATA, widget=EntradaData())
    data_fim_evento = forms.DateField(label="Fim do evento", required=False,
                                      input_formats=FORMATOS_DATA, widget=EntradaData(),
                                      help_text="Só se durar mais de um dia.")
    hora_inicio = forms.TimeField(label="Horário", required=False, widget=EntradaHora(),
                                  input_formats=["%H:%M"])
    municipio = CampoMunicipio(label="Município", required=False)

    class Meta:
        model = Palestra
        fields = ["data_solicitacao", "canal_solicitacao", "protocolo", "solicitante",
                  "telefone", "email", "assunto_email", "pedido_contato",
                  "informacoes_previas", "descricao", "evento", "data_inicio_evento",
                  "data_fim_evento", "hora_inicio", "municipio", "local", "endereco",
                  "bairro", "cep", "quantidade_publico", "temas", "palestrantes"]
        labels = {"canal_solicitacao": "Foi solicitado via", "evento": "Tipo de evento",
                  "quantidade_publico": "Quantidade de público", "email": "E-mail",
                  "assunto_email": "Assunto do e-mail", "pedido_contato": "Pedido/contato",
                  "local": "Local do evento"}
        widgets = {
            "canal_solicitacao": Selecao(), "evento": Selecao(),
            "solicitante": forms.TextInput(attrs=_attrs(
                autocomplete="off", list="solicitantes",
                placeholder="Escola, empresa, associação…")),
            "telefone": forms.TextInput(attrs=_attrs(inputmode="tel", autocomplete="off",
                                                     placeholder="(00) 00000-0000",
                                                     **{"data-mascara": "telefone"})),
            "email": forms.EmailInput(attrs=_attrs(autocomplete="off")),
            "protocolo": forms.TextInput(attrs=_attrs(inputmode="numeric", autocomplete="off",
                                                      placeholder="00.000.000-0",
                                                      **{"data-mascara": "protocolo"})),
            "assunto_email": forms.TextInput(attrs=_attrs(autocomplete="off")),
            "pedido_contato": _texto(3, "O que o solicitante pediu, como chegou."),
            "informacoes_previas": _texto(3),
            "descricao": _texto(3),
            "local": forms.TextInput(attrs=_attrs(autocomplete="off",
                                                  placeholder="Nome do lugar")),
            "endereco": forms.TextInput(attrs=_attrs(autocomplete="off",
                                                     placeholder="Rua, número, complemento")),
            "bairro": forms.TextInput(attrs=_attrs(autocomplete="off")),
            "cep": forms.TextInput(attrs=_attrs(inputmode="numeric", autocomplete="off",
                                                placeholder="00000-000",
                                                **{"data-mascara": "cep"})),
            "quantidade_publico": forms.NumberInput(attrs=_attrs(min="0", inputmode="numeric")),
            "temas": CaixasDeEscolha(),
        }
        help_texts = {"protocolo": "Só para pedidos que chegaram por protocolo."}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.municipio_id and not self.is_bound:
            m = self.instance.municipio
            self.initial["municipio"] = f"{m.nome}/{m.uf}"
        temas = cast(forms.ModelMultipleChoiceField, self.fields["temas"])
        temas.queryset = Tema.objects.order_by("nome")
        palestrantes = cast(forms.ModelMultipleChoiceField, self.fields["palestrantes"])
        palestrantes.queryset = Palestrante.objects.order_by("nome")
        palestrantes.widget = EscolhaMultiplaRemota(
            fonte=reverse("palestras:buscar_palestrantes"),
            rotulo_vazio="Nenhum palestrante escolhido.",
            placeholder="Buscar palestrante pelo nome…")
        palestrantes.widget.choices = palestrantes.choices
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("form", FORM_ID)

    def clean(self) -> dict[str, Any]:
        dados = super().clean() or {}
        for nome, regra in (("telefone", dominio.formatar_telefone),
                            ("cep", dominio.formatar_cep)):
            try:
                dados[nome] = regra(dados.get(nome))
            except dominio.RegraViolada as exc:
                self.add_error(nome, str(exc))
        try:
            dados["protocolo"] = dominio.formatar_protocolo(dados.get("canal_solicitacao") or "",
                                                            dados.get("protocolo"))
        except dominio.RegraViolada as exc:
            self.add_error("protocolo", str(exc))
        try:
            dominio.conferir_periodo(dados.get("data_inicio_evento"), dados.get("data_fim_evento"))
        except dominio.RegraViolada as exc:
            self.add_error(exc.campo, str(exc))
        return dados


class FormularioAndamento(forms.Form):
    novo_status = forms.ChoiceField(label="Novo status", choices=Palestra.Status.choices,
                                    widget=forms.RadioSelect)
    anotacao = forms.CharField(label="Andamento", required=False, max_length=4000,
                               widget=_texto(3, "O que aconteceu: contato feito, aguardando "
                                                "a escola, palestrante confirmado…"))
    data_evento = forms.DateField(label="Data do evento", required=False,
                                  input_formats=FORMATOS_DATA, widget=EntradaData())
    palestrante = forms.ModelChoiceField(label="Palestrante", required=False,
                                         queryset=Palestrante.objects.order_by("nome"),
                                         empty_label="Escolha o palestrante", widget=Selecao())
    quantidade_publico = forms.IntegerField(label="Quantidade de público", required=False,
                                            min_value=0, widget=forms.NumberInput(
                                                attrs=_attrs(min="0", inputmode="numeric")))


class FormularioResposta(forms.Form):
    resposta = forms.ModelChoiceField(label="Resposta padrão",
                                      queryset=RespostaPadrao.objects.order_by("tipo"),
                                      empty_label="Escolha a resposta", widget=Selecao())
    texto = forms.CharField(label="Texto enviado", max_length=8000,
                            widget=_texto(8, "Escolha uma resposta padrão para começar."))
    novo_status = forms.ChoiceField(label="Mudar o status para", required=False,
                                    choices=[("", "Não mudar"), *Palestra.Status.choices],
                                    widget=Selecao())


class FormularioPalestrante(forms.ModelForm):
    municipio = CampoMunicipio(label="Município", required=False)

    class Meta:
        model = Palestrante
        fields = ["nome", "servidor", "municipio", "divisao", "lotacao", "contato", "email",
                  "tema_abordagem"]
        labels = {"servidor": "Servidor no cadastro", "email": "E-mail"}
        widgets = {"servidor": Selecao()}
        help_texts = {"servidor": "Ligar ao cadastro de servidores ajuda a Agenda a avisar "
                                  "choque com viagens."}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        servidor = cast(forms.ModelChoiceField, self.fields["servidor"])
        servidor.queryset = Servidor.objects.filter(ativo=True).order_by("nome")
        servidor.empty_label = "Sem vínculo"
        if self.instance.pk and self.instance.municipio_id and not self.is_bound:
            m = self.instance.municipio
            self.initial["municipio"] = f"{m.nome}/{m.uf}"
        for campo in self.fields.values():
            if not isinstance(campo.widget, Selecao):
                campo.widget.attrs.setdefault("class", "entrada")
