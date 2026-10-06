"""Formulários da solicitação de evento.

O município é "Cidade/UF" com a busca dos cadastros (funciona sem JavaScript). Tipo,
órgão e unidade móvel mostram só os ativos — mais o que a solicitação já usa. Serviços e
equipes (com a quantidade) vêm em campos próprios, lidos pela view (`estrutura_do_post`).
A trava de versão recusa gravar por cima de quem salvou depois que a tela abriu.
"""

from __future__ import annotations

import re
from typing import Any, cast

from django import forms
from django.db.models import Q

from gestao.cadastros.forms import CampoMunicipio
from gestao.cadastros.models import Servidor
from gestao.plataforma.widgets import FORMATOS_DATA, EntradaData, Selecao

from .models import Equipe, OrgaoResponsavel, Servico, Solicitacao, TipoEvento, UnidadeMovel
from .solicitacoes import Estrutura

FORM_ID = "form-solicitacao"
MSG_VERSAO = ("Esta solicitação foi alterada por outra pessoa depois que você abriu a tela. "
              "Recarregue a página antes de salvar.")


def _attrs(**extra: Any) -> dict[str, Any]:
    return {"class": "entrada", **extra}


def versao_de(s: Solicitacao) -> str:
    return str(int(s.atualizado_em.timestamp() * 1_000_000)) if s.atualizado_em else ""


def _ativos(modelo, atual: int | None):
    return modelo.objects.filter(Q(ativo=True) | Q(pk=atual or 0)).order_by("nome")


class FormularioSolicitacao(forms.ModelForm):
    versao = forms.CharField(required=False, widget=forms.HiddenInput)
    data_solicitacao = forms.DateField(label="Data da solicitação", input_formats=FORMATOS_DATA,
                                       widget=EntradaData())
    data_inicio_evento = forms.DateField(label="Início do evento", required=False,
                                         input_formats=FORMATOS_DATA, widget=EntradaData())
    data_fim_evento = forms.DateField(label="Fim do evento", required=False,
                                      input_formats=FORMATOS_DATA, widget=EntradaData())
    municipio = CampoMunicipio(label="Município", required=False)

    class Meta:
        model = Solicitacao
        fields = ["data_solicitacao", "data_inicio_evento", "data_fim_evento", "municipio",
                  "tipo_evento", "solicitante_nome", "solicitante_cargo_unidade", "contato",
                  "orgao_responsavel", "local_evento", "endereco", "bairro", "cep",
                  "protocolo", "descricao_complementar", "tipo_operacao", "quantidade_cin",
                  "unidade_movel", "unidade_movel_designada", "motorista"]
        labels = {"solicitante_nome": "Quem pede", "orgao_responsavel": "Órgão responsável",
                  "local_evento": "Local do evento",
                  "quantidade_cin": "Quantidade de CIN agendadas",
                  "unidade_movel": "Vai unidade móvel",
                  "unidade_movel_designada": "Qual unidade móvel",
                  "descricao_complementar": "Descrição"}
        widgets = {
            "tipo_evento": Selecao(), "orgao_responsavel": Selecao(),
            "unidade_movel_designada": Selecao(), "motorista": Selecao(),
            "tipo_operacao": Selecao(),
            "solicitante_nome": forms.TextInput(attrs=_attrs(autocomplete="off",
                                                             list="solicitantes")),
            "solicitante_cargo_unidade": forms.TextInput(attrs=_attrs(autocomplete="off")),
            "contato": forms.TextInput(attrs=_attrs(autocomplete="off",
                                                    placeholder="Telefone ou e-mail")),
            "local_evento": forms.TextInput(attrs=_attrs(autocomplete="off",
                                                         placeholder="Nome do lugar")),
            "endereco": forms.TextInput(attrs=_attrs(autocomplete="off")),
            "bairro": forms.TextInput(attrs=_attrs(autocomplete="off")),
            "cep": forms.TextInput(attrs=_attrs(inputmode="numeric", autocomplete="off",
                                                placeholder="00000-000",
                                                **{"data-mascara": "cep"})),
            "protocolo": forms.TextInput(attrs=_attrs(inputmode="numeric", autocomplete="off",
                                                      placeholder="00.000.000-0",
                                                      **{"data-mascara": "protocolo"})),
            "descricao_complementar": forms.Textarea(attrs=_attrs(rows=3)),
            "quantidade_cin": forms.NumberInput(attrs=_attrs(min="0", inputmode="numeric")),
            "unidade_movel": forms.CheckboxInput(attrs={"role": "switch"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        inst = self.instance
        if inst.pk and inst.municipio_id and not self.is_bound:
            self.initial["municipio"] = f"{inst.municipio.nome}/{inst.municipio.uf}"
        if inst.pk and not self.is_bound:
            self.initial["versao"] = versao_de(inst)
        for nome, modelo, atual, vazio in (
                ("tipo_evento", TipoEvento, inst.tipo_evento_id, "Escolha o tipo"),
                ("orgao_responsavel", OrgaoResponsavel, inst.orgao_responsavel_id,
                 "Escolha o órgão"),
                ("unidade_movel_designada", UnidadeMovel, inst.unidade_movel_designada_id,
                 "A designar")):
            campo = cast(forms.ModelChoiceField, self.fields[nome])
            campo.queryset = _ativos(modelo, atual)
            campo.empty_label = vazio
        motorista = cast(forms.ModelChoiceField, self.fields["motorista"])
        motorista.queryset = Servidor.objects.filter(
            Q(ativo=True) | Q(pk=inst.motorista_id or 0)).order_by("nome")
        motorista.empty_label = "Sem motorista definido"
        for campo_form in self.fields.values():
            campo_form.widget.attrs.setdefault("form", FORM_ID)

    def clean(self) -> dict[str, Any]:
        dados = super().clean() or {}
        inst = self.instance
        if inst.pk and dados.get("versao") and dados["versao"] != versao_de(
                Solicitacao.objects.get(pk=inst.pk)):
            raise forms.ValidationError(MSG_VERSAO)
        return dados


QUANTIDADE_MAXIMA = 9999


def quantidade(texto: str | None) -> int | None:
    """Quantidade de servidores digitada: 1 a 9999, só algarismos (nada de "²")."""
    texto = (texto or "").strip()
    if not re.fullmatch(r"[0-9]{1,4}", texto):
        return None
    valor = int(texto)
    return valor if 1 <= valor <= QUANTIDADE_MAXIMA else None


def estrutura_do_post(post, solicitacao=None) -> tuple[Estrutura, list[str]]:
    """Serviços marcados (servico_<id>) e equipes marcadas com a quantidade
    (equipe_<id> + quantidade_equipe_<id>). Só os ativos, mais os que a solicitação já
    tem (como nos selects). Devolve a estrutura e os erros."""
    erros: list[str] = []
    atuais_s: set[int] = set()
    atuais_e: set[int] = set()
    if solicitacao is not None and solicitacao.pk:
        atuais_s = set(solicitacao.servicos.values_list("servico_id", flat=True))
        atuais_e = set(solicitacao.equipes.values_list("equipe_id", flat=True))
    servicos = {s.pk: (post.get(f"observacao_servico_{s.pk}") or "").strip()[:255]
                for s in Servico.objects.filter(Q(ativo=True) | Q(pk__in=atuais_s))
                if post.get(f"servico_{s.pk}")}
    equipes: dict[int, int | None] = {}
    for e in Equipe.objects.filter(Q(ativo=True) | Q(pk__in=atuais_e)):
        if not post.get(f"equipe_{e.pk}"):
            continue
        texto = (post.get(f"quantidade_equipe_{e.pk}") or "").strip()
        valor = quantidade(texto)
        if texto and valor is None:
            erros.append(f"Informe uma quantidade válida de servidores para {e.nome}.")
        equipes[e.pk] = valor
    return Estrutura(servicos=servicos, equipes=equipes), erros
