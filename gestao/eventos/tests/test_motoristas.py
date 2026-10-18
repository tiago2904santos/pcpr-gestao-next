"""Seleção de motorista por fonte canônica, sem acesso administrativo a servidores."""

from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from gestao.cadastros.models import Cargo, Servidor, Unidade
from gestao.eventos.forms import FORM_ID, FormularioSolicitacao
from gestao.eventos.models import Solicitacao

pytestmark = pytest.mark.django_db


def test_busca_ativa_limitada_com_identificacao_sem_conceder_crud(usuario, client):
    cargo = Cargo.objects.create(nome="Condutor sintético")
    unidade = Unidade.objects.create(nome="Unidade sintética de motoristas", sigla="MOT")
    Servidor.objects.bulk_create([
        Servidor(nome=f"Motorista sintético {i:03d}", cargo=cargo, unidade=unidade)
        for i in range(40)])
    Servidor.objects.create(nome="Motorista sintético inativo", cargo=cargo, ativo=False)
    client.force_login(usuario)
    url = reverse("eventos:buscar_motoristas")
    dados = client.get(url, {"q": "Condutor"}).json()["resultados"]
    assert len(dados) == 15
    assert dados[0]["meta"] == "Condutor sintético · MOT"
    assert not any("inativo" in dado["titulo"] for dado in dados)
    assert len(client.get(url, {"q": "MOT"}).json()["resultados"]) == 15
    assert not usuario.has_perm("cadastros.view_servidor")
    assert client.get(reverse("cadastros:servidores")).status_code == 403


def test_busca_respeita_solicitacao_e_nao_revela_outra(usuario, django_user_model, client):
    propria = Solicitacao.objects.create(criado_por=usuario, data_solicitacao=date.today())
    outro = django_user_model.objects.create_user("outro-motorista", "outro@teste.invalid")
    alheia = Solicitacao.objects.create(criado_por=outro, data_solicitacao=date.today())
    url = reverse("eventos:buscar_motoristas")
    assert Client().get(url).status_code == 302
    client.force_login(usuario)
    assert client.get(url, {"solicitacao": propria.pk}).status_code == 200
    assert client.get(url, {"solicitacao": alheia.pk}).status_code == 404
    assert client.get(url, {"solicitacao": "invalida"}).status_code == 404
    propria.status = Solicitacao.Status.ATENDIDA
    propria.save()
    assert client.get(url, {"solicitacao": propria.pk}).status_code == 403


def test_formulario_renderiza_so_atual_e_mantem_inativo_fora_de_15(
        usuario, django_assert_num_queries):
    Servidor.objects.bulk_create([Servidor(nome=f"Motorista volume {i:03d}") for i in range(40)])
    atual = Servidor.objects.create(nome="Z Motorista vinculado inativo", ativo=False)
    s = Solicitacao.objects.create(
        criado_por=usuario, data_solicitacao=date.today(), motorista=atual)
    form = FormularioSolicitacao(instance=s)
    with django_assert_num_queries(1):
        html = str(form["motorista"])
    assert html.count("<option") == 2 and atual.nome in html
    assert "Motorista volume" not in html
    assert f'form="{FORM_ID}"' in html and f"solicitacao={s.pk}" in html
    dados = {"data_solicitacao": "17/10/2026", "tipo_operacao": "diaria",
             "unidade_movel": "on", "motorista": atual.pk}
    assert FormularioSolicitacao(dados, instance=s).is_valid()
    novo = FormularioSolicitacao(dados)
    assert not novo.is_valid() and "motorista" in novo.errors
    outro = Servidor.objects.create(nome="Outro motorista inativo", ativo=False)
    form = FormularioSolicitacao({**dados, "motorista": outro.pk}, instance=s)
    assert not form.is_valid() and "motorista" in form.errors
