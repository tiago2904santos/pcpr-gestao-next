"""Página Numeração de ofícios (LP-32, D9): só o gestor; mostra o próximo número e o porquê,
valida o número inicial com mensagens que dizem como resolver e registra quem mudou."""

from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils import timezone

from gestao.viagens import linha_do_tempo, services
from gestao.viagens.models import LacunaNumeracao, NumeracaoAnual, Oficio

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db(transaction=True)
URL = "/viagens/oficios/numeracao/"


@pytest.fixture
def cenario():
    return cenario_completo()


@pytest.fixture
def gestor(client, cenario):
    client.force_login(cenario.usuarios["gestor"])
    return client


def test_endereco():
    assert reverse("viagens:numeracao") == URL


@pytest.mark.parametrize("perfil", ["operador", "consulta", "outra"])
def test_so_o_gestor_entra(client, cenario, perfil):
    client.force_login(cenario.usuarios[perfil])
    assert client.get(URL).status_code == 403
    assert client.post(URL, {"ano": 2026, "piso": 500}).status_code == 403


def test_mais_da_lista_so_para_o_gestor(client, cenario):
    client.force_login(cenario.usuarios["operador"])
    html = client.get(reverse("viagens:oficios")).content.decode()
    assert URL not in html and "barra-acoes__mais" not in html  # nunca um "Mais" vazio
    client.force_login(cenario.usuarios["gestor"])
    html = client.get(reverse("viagens:oficios")).content.decode()
    assert f'href="{URL}"' in html and "Numeração" in html
    assert "eProtocolo" not in html  # entra só quando existir (D10)


def test_mostra_o_proximo_e_de_onde_ele_vem(gestor, cenario):
    ano = timezone.localdate().year
    maior = max(Oficio.objects.filter(ano=ano).values_list("numero", flat=True))
    html = gestor.get(URL).content.decode()
    assert f"{maior + 1:02d}/{ano}" in html and "O último ocupado + 1" in html
    assert f"{ano + 1}" in html  # o próximo ano, para preparar a virada
    # Exclui um rascunho: o número dele volta e passa a ser o próximo.
    rascunho = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
    numero = rascunho.numero
    services.excluir_rascunho(rascunho, cenario.usuarios["operador"])
    html = gestor.get(URL).content.decode()
    assert "A menor lacuna livre" in html and f"{numero:02d}/{ano}" in html
    assert "o próximo a ser usado" in html


def test_salvar_piso_explica_o_efeito_e_nao_renumera(gestor):
    ano = timezone.localdate().year
    antes = list(Oficio.objects.filter(ano=ano).values_list("pk", "numero"))
    r = gestor.post(f"{URL}?ano={ano}", {"ano": ano, "piso": 500}, follow=True)
    html = r.content.decode()
    assert r.redirect_chain[-1][0] == f"{URL}?ano={ano}"
    assert (f"Número inicial de {ano} gravado: 500. O próximo ofício de {ano} será "
            f"500/{ano}.") in html
    assert NumeracaoAnual.objects.get(ano=ano).piso == 500
    assert list(Oficio.objects.filter(ano=ano).values_list("pk", "numero")) == antes


def test_piso_abaixo_do_ultimo_avisa_que_nada_muda(gestor):
    ano = timezone.localdate().year
    maior = max(Oficio.objects.filter(ano=ano).values_list("numero", flat=True))
    r = gestor.post(URL, {"ano": ano, "piso": 2}, follow=True)
    assert (f"Nada muda agora: o último número usado é {maior:02d}/{ano}, então o próximo "
            f"continua {maior + 1:02d}/{ano}.") in r.content.decode()


def test_lacuna_abaixo_do_piso_e_avisada(gestor, cenario):
    ano = timezone.localdate().year
    rascunho = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
    numero = rascunho.numero
    services.excluir_rascunho(rascunho, cenario.usuarios["operador"])
    assert LacunaNumeracao.objects.filter(ano=ano, numero=numero).exists()
    r = gestor.post(URL, {"ano": ano, "piso": 600}, follow=True)
    assert (f"A lacuna {numero:02d}/{ano} fica abaixo do piso e não será "
            "reaproveitada.") in r.content.decode()


def test_mesmo_piso_nao_grava(gestor):
    ano = timezone.localdate().year
    r = gestor.post(URL, {"ano": ano, "piso": 1}, follow=True)
    assert "já era 1; nada mudou" in r.content.decode()
    assert not NumeracaoAnual.objects.filter(ano=ano, piso__gt=1).exists()


@pytest.mark.parametrize(("piso", "mensagem"), [
    ("", "Informe o número inicial"),
    ("abc", "Use só algarismos"),
    ("0", "O número inicial começa em 1"),
    ("100000", "vai até 99999"),
])
def test_validacao_diz_como_resolver(gestor, piso, mensagem):
    ano = timezone.localdate().year
    r = gestor.post(URL, {"ano": ano, "piso": piso})
    html = r.content.decode()
    assert r.status_code == 422 and mensagem in html
    assert 'id="resumo-erros"' in html and 'aria-invalid="true"' in html


def test_ano_fora_da_faixa(gestor):
    r = gestor.post(URL, {"ano": "1999", "piso": "5"})
    assert r.status_code == 422 and "entre 2000 e 2100" in r.content.decode()


def test_ano_encerrado_nao_oferece_o_formulario(gestor):
    ano = timezone.localdate().year - 1
    Oficio.objects.filter(pk=Oficio.objects.order_by("pk").first().pk).update(ano=ano)
    html = gestor.get(f"{URL}?ano={ano}").content.decode()
    assert "já passou" in html and "Salvar número inicial" not in html


def test_historico_vem_da_trilha(cenario):
    ano = timezone.localdate().year
    services.definir_piso(cenario.usuarios["gestor"], ano, 300)
    services.definir_piso(cenario.usuarios["gestor"], ano, 400)
    mudancas = linha_do_tempo.do_piso(ano)
    assert [(m.de, m.para) for m in mudancas][:2] == [(300, 400), (1, 300)]


def test_consultas_fixas(gestor, django_assert_max_num_queries):
    with django_assert_max_num_queries(14):
        assert gestor.get(URL).status_code == 200
