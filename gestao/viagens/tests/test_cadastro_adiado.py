"""Folha leve e GET autorizado dos mesmos formulários de cadastro rápido."""

from __future__ import annotations

import re

import pytest
from django.urls import reverse

from gestao.viagens.models import Documento, Historico, Oficio

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def cenario():
    return cenario_completo()


def test_folha_nao_monta_formularios_fechados(client, cenario, monkeypatch):
    from gestao.viagens import views

    def proibido(*args, **kwargs):
        pytest.fail("A folha inicial não deve montar formulários de cadastro fechados.")

    monkeypatch.setattr(views, "FormularioServidor", proibido)
    monkeypatch.setattr(views, "FormularioViatura", proibido)
    client.force_login(cenario.usuarios["operador"])
    resposta = client.get(reverse("viagens:editar", args=[cenario.ids["oficio_rascunho"]]))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    janela = re.search(r'<dialog id="dialogo-servidor".*?</dialog>', html, re.S)
    assert janela and "data-cadastro-url=" in janela[0]
    assert "<form" not in janela[0]


def test_get_cadastros_reutiliza_formularios_sem_escrever_negocio(client, cenario):
    client.force_login(cenario.usuarios["operador"])
    pk = cenario.ids["oficio_rascunho"]
    antes = (Oficio.objects.get(pk=pk).versao, Historico.objects.count(),
             Documento.objects.count())
    resposta = client.get(reverse("viagens:editar", args=[pk]), {"cadastros": "1"})
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert html.count("<dialog ") == 5
    assert html.count("data-cadastro-rapido") == 5
    assert 'name="cpf"' in html and 'name="rg"' in html
    assert 'data-nome="motoristas"' in html and 'data-envio-url=' in html
    assert reverse("viagens:adicionar_viajante", args=[pk]) in html
    assert (Oficio.objects.get(pk=pk).versao, Historico.objects.count(),
            Documento.objects.count()) == antes


@pytest.mark.parametrize("perfil,outra_unidade,esperado", [
    ("consulta", False, 302), ("operador", True, 404), ("outra", False, 404),
])
def test_cadastro_adiado_aplica_escopo_e_edicao(client, cenario, perfil,
                                            outra_unidade, esperado):
    client.force_login(cenario.usuarios[perfil])
    pk = cenario.ids["oficio_outra_unidade" if outra_unidade else "oficio_rascunho"]
    resposta = client.get(reverse("viagens:editar", args=[pk]), {"cadastros": "1"})
    assert resposta.status_code == esperado
    assert b'data-cadastro-rapido' not in resposta.content
