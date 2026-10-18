"""Dados da unidade: menu único, contexto explícito e escrita autorizada no backend."""

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from gestao.cadastros import services
from gestao.cadastros.forms import FormularioConfiguracao
from gestao.cadastros.models import (
    ConfiguracaoInstitucional,
    Lotacao,
    Servidor,
    SubstituicaoAssinante,
)
from gestao.identidade.models import Usuario

from . import test_crud
from .test_crud import _cliente

pytestmark = pytest.mark.django_db


base = test_crud.base


def test_menu_unico_imediatamente_apos_alterar_senha(base):
    html = _cliente(base["gestor"]).get(reverse("cadastros:indice")).content.decode()
    trecho = html[html.index('href="' + reverse("identidade:alterar_senha")):]
    from html.parser import HTMLParser

    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.links.append(dict(attrs).get("href"))

    links = Links()
    links.feed('<a ' + trecho)
    assert links.links[:2] == [reverse("identidade:alterar_senha"),
                              reverse("cadastros:configuracao")]
    assert html.count("Dados da unidade") == 1
    html = _cliente(base["consulta"]).get(reverse("cadastros:indice")).content.decode()
    assert "Dados da unidade" not in html


@pytest.mark.parametrize("metodo", ["get", "post"])
@pytest.mark.parametrize("unidade", ["outra", "²", "inexistente", ""])
def test_unidade_explicita_nao_autorizada_ou_invalida_e_404(base, metodo, unidade):
    valor = str(base["dpc"].pk) if unidade == "outra" else unidade
    cliente = _cliente(base["operador"])
    rota = reverse("cadastros:configuracao")
    if metodo == "get":
        resposta = cliente.get(rota, {"unidade": valor})
    else:
        resposta = cliente.post(rota, {"unidade": valor})
    assert resposta.status_code == 404
    assert not ConfiguracaoInstitucional.objects.exists()


def test_identificadores_divergentes_nao_gravam_na_unidade_errada(base):
    cliente = _cliente(base["gestor"])
    resposta = cliente.post(reverse("cadastros:configuracao") +
                            f"?unidade={base['dpc'].pk}", {"unidade": base["ascom"].pk})
    assert resposta.status_code == 404
    assert not ConfiguracaoInstitucional.objects.exists()


@pytest.mark.parametrize("rota", ["cadastros:configuracao", "cadastros:salvar_substituicao"])
def test_operador_nao_recebe_formulario_editavel_nem_com_post_invalido(base, rota):
    resposta = _cliente(base["operador"]).post(reverse(rota), {})
    assert resposta.status_code == 403
    assert not ConfiguracaoInstitucional.objects.exists()
    assert not SubstituicaoAssinante.objects.exists()


def test_gestor_local_nao_altera_outra_unidade_por_post(base):
    usuario = Usuario.objects.create_user("gestor-local", "local@pc.pr.gov.br", "senha-local-123")
    usuario.user_permissions.add(*Permission.objects.filter(codename__in=[
        "view_configuracaoinstitucional", "change_configuracaoinstitucional"]))
    Lotacao.objects.create(usuario=usuario, unidade=base["ascom"])
    cliente = _cliente(usuario)
    for rota in ("cadastros:configuracao", "cadastros:salvar_substituicao"):
        resposta = cliente.post(reverse(rota), {"unidade": base["dpc"].pk})
        assert resposta.status_code == 404
    assert not ConfiguracaoInstitucional.objects.exists()


def test_titular_inativo_permanece_identificado_sem_abrir_novas_escolhas(base):
    atual = Servidor.objects.create(nome="Titular inativo", ativo=False)
    outro = Servidor.objects.create(nome="Outro inativo", ativo=False)
    form = FormularioConfiguracao(config=ConfiguracaoInstitucional(assina_oficio=atual))
    assert atual in form.fields["assina_oficio"].queryset
    assert outro not in form.fields["assina_oficio"].queryset


def test_escolher_assinante_preserva_contas_e_permissoes(base):
    from gestao.cadastros.carga import garantir_municipios
    from gestao.cadastros.models import Municipio

    garantir_municipios()
    servidor = Servidor.objects.create(nome="Assinante sem conta", unidade=base["ascom"])
    contas = list(Usuario.objects.values_list("pk", "is_staff", "is_superuser"))
    grupos = list(Usuario.groups.through.objects.values_list("usuario_id", "group_id"))
    config = services.salvar_configuracao(
        base["gestor"], base["ascom"], assina_oficio=servidor,
        sede=Municipio.objects.get(nome="Curitiba", uf="PR"), nome_extenso="Unidade sintética")
    assert config.assina_oficio_id == servidor.pk
    assert list(Usuario.objects.values_list("pk", "is_staff", "is_superuser")) == contas
    assert list(Usuario.groups.through.objects.values_list("usuario_id", "group_id")) == grupos


def test_lotacao_inativa_continua_identificada_no_seletor(base):
    base["ascom"].ativo = False
    base["ascom"].save(update_fields=["ativo"])
    resposta = _cliente(base["gestor"]).get(reverse("cadastros:configuracao"))
    assert resposta.context["unidade"].pk == base["ascom"].pk
    assert base["ascom"] in resposta.context["unidades"]
    html = resposta.content.decode()
    assert f'value="{base["ascom"].pk}" selected' in html
    assert "(inativa)" in html


def test_busca_assinantes_limitada_ativa_com_metadados_e_cpf_mascarado(base):
    Servidor.objects.bulk_create([
        Servidor(nome=f"Assinante para pesquisa {i:03d}", unidade=base["ascom"],
                 cargo=base["agente"], cpf="52998224725" if i == 0 else "") for i in range(40)])
    Servidor.objects.create(nome="Assinante para pesquisa inativo", ativo=False)
    resposta = _cliente(base["operador"]).get(reverse("cadastros:buscar_assinantes"),
                                            {"unidade": base["ascom"].pk,
                                             "q": "Assinante para pesquisa"})
    assert resposta.status_code == 200
    opcoes = resposta.json()["resultados"]
    assert len(opcoes) == 15
    assert "Agente de Polícia Judiciária" in opcoes[0]["meta"]
    assert "ASCOM" in opcoes[0]["meta"]
    assert "CPF final 4725" in opcoes[0]["meta"]
    assert "52998224725" not in resposta.content.decode()
    assert not any("inativo" in o["titulo"] for o in opcoes)


@pytest.mark.parametrize("perfil,status", [("consulta", 403), ("operador", 404)])
def test_busca_assinantes_nao_abre_contexto_de_outra_unidade(base, perfil, status):
    resposta = _cliente(base[perfil]).get(reverse("cadastros:buscar_assinantes"),
                                         {"unidade": base["dpc"].pk, "q": "a"})
    assert resposta.status_code == status


def test_seletor_nao_renderiza_catalogo_inteiro_e_preserva_atual_fora_da_primeira_pagina(base):
    Servidor.objects.bulk_create([Servidor(nome=f"Servidor de volume {i:04d}") for i in range(400)])
    atual = Servidor.objects.create(nome="Z Titular fora da primeira página", ativo=False)
    config = ConfiguracaoInstitucional(unidade=base["ascom"], assina_oficio=atual)
    form = FormularioConfiguracao(config=config, initial={"assina_oficio": atual.pk})
    html = str(form["assina_oficio"])
    # Baseline reproduz o select anterior com o mesmo queryset e conteúdo sintético.
    from django import forms
    escolha = form.fields["assina_oficio"]
    escolha.widget = forms.Select(choices=escolha.choices)
    anterior = str(form["assina_oficio"])
    assert anterior.count("<option") == 402
    assert html.count("<option") == 2
    assert len(html) < len(anterior) / 10
    assert "Servidor de volume" not in html
    assert "Z Titular fora da primeira página" in html
    assert "A chefia (abaixo)" in html
    assert f"?unidade={base['ascom'].pk}&amp;q=" in html
