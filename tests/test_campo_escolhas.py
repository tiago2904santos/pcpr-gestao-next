"""Rótulos e erros de uma coleção não podem virar um checkbox simples."""
from django import forms
from django.template.loader import render_to_string

from gestao.plataforma.widgets import CaixasDeEscolha


class Formulario(forms.Form):
    papeis = forms.MultipleChoiceField(
        label="Perfis", choices=[("a", "Perfil A"), ("b", "Perfil B")],
        widget=CaixasDeEscolha, help_text="Escolha os perfis necessários.",
    )
    ativo = forms.BooleanField(label="Ativo", required=False)


def test_grupo_associa_erro_e_ajuda_sem_rotulo_envolvente():
    form = Formulario(data={})
    assert not form.is_valid()
    html = render_to_string("componentes/campo.html", {"campo": form["papeis"]})
    assert '<fieldset' in html and '<legend' in html
    assert 'aria-describedby="id_papeis-ajuda id_papeis-erro"' in html
    assert '<label class="escolha" for="id_papeis">' not in html
    assert html.count('type="checkbox"') == 2
    assert 'for="id_papeis_0"' in html and 'for="id_papeis_1"' in html


def test_checkbox_simples_conserva_rotulo():
    html = render_to_string("componentes/campo.html", {"campo": Formulario()["ativo"]})
    assert '<fieldset' not in html
    assert '<label class="escolha" for="id_ativo">' in html


def test_opcoes_desabilitadas_preservam_valor():
    form = Formulario(initial={"papeis": ["b"]})
    form.fields["papeis"].disabled = True
    html = render_to_string("componentes/campo.html", {"campo": form["papeis"]})
    assert html.count(' disabled') == 2
    assert 'value="b" id="id_papeis_1" checked disabled' in html
