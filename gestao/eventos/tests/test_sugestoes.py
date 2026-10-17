"""Sugestões da solicitação: pelo tipo (o modelo; sem ele, o que se repete nas últimas do
tipo, com a quantidade mais comum) e pelos solicitantes de antes (nomes juntados, dados do
último pedido)."""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from gestao.eventos import solicitacoes, sugestoes
from gestao.eventos.models import Equipe, Servico, TipoEvento

from .test_solicitacoes import _completa, _usuario

pytestmark = pytest.mark.django_db


@pytest.fixture
def ana():
    return _usuario("ana")


def _pedido(usuario, tipo, servicos, equipes, **extra):
    s = solicitacoes.criar(usuario, _completa(tipo_evento=tipo, **extra), solicitacoes.Estrutura(
        servicos={Servico.objects.get(nome=n).pk: "" for n in servicos},
        equipes={Equipe.objects.get(nome=n).pk: q for n, q in equipes.items()}))
    solicitacoes.enviar(usuario, s.pk)
    return s


def test_tipo_sem_modelo_sugere_o_que_se_repete(ana):
    tipo = TipoEvento.objects.get(nome="Feira")
    tipo.servicos_sugeridos.clear()
    tipo.equipes_padrao.all().delete()
    _pedido(ana, tipo, ["Emissão de CIN"], {"Alfa": 3})
    _pedido(ana, tipo, ["Emissão de CIN"], {"Alfa": 5})
    _pedido(ana, tipo, ["Emissão de CIN", "Atendimento social"], {"Alfa": 5, "Bravo": 2})
    _pedido(ana, tipo, ["Coleta de digitais"], {"Alfa": 3})
    s = sugestoes.do_tipo(ana, tipo)
    assert s.fonte == "as últimas 4 solicitações deste tipo"
    assert [x["nome"] for x in s.servicos] == ["Emissão de CIN"]  # 3 de 4; o social, 1 de 4
    assert s.equipes == [{"id": Equipe.objects.get(nome="Alfa").pk, "nome": "Alfa",
                          "quantidade": 5}]  # 3 e 5 empatam: vale a maior


def test_modelo_do_tipo_vem_primeiro_e_pela_tela(ana):
    tipo = TipoEvento.objects.get(nome="Feira")
    tipo.servicos_sugeridos.set([Servico.objects.get(nome="Emissão de CIN")])
    tipo.solicitante_padrao = "Coordenação"
    tipo.save()
    c = Client()
    c.force_login(ana)
    r = c.get(reverse("eventos:sugestao_do_tipo"), {"tipo": tipo.pk})
    dados = r.json()
    assert dados["fonte"] == "o modelo do tipo" and dados["solicitante"] == "Coordenação"
    assert [x["nome"] for x in dados["servicos"]] == ["Emissão de CIN"]
    assert c.get(reverse("eventos:sugestao_do_tipo"), {"tipo": "x"}).status_code == 404


def test_solicitantes_anteriores_juntam_o_nome_e_trazem_o_ultimo_pedido(ana):
    tipo = TipoEvento.objects.get(nome="Feira")
    _pedido(ana, tipo, ["Emissão de CIN"], {"Alfa": 2}, solicitante_nome="Escola  Estadual X",
            contato="(41) 1111-1111")
    _pedido(ana, tipo, ["Emissão de CIN"], {"Alfa": 2}, solicitante_nome="escola estadual x",
            contato="(41) 2222-2222", solicitante_cargo_unidade="Direção")
    c = Client()
    c.force_login(ana)
    resultados = c.get(reverse("eventos:solicitantes"), {"q": "estadual"}).json()["resultados"]
    assert len(resultados) == 1
    r = resultados[0]
    assert r["titulo"] == "escola estadual x" and r["contato"] == "(41) 2222-2222"
    assert r["cargo"] == "Direção" and r["meta"].endswith("2 pedidos")
    assert c.get(reverse("eventos:solicitantes"), {"q": "e"}).json()["resultados"] == []
    outro = Client()
    outro.force_login(_usuario("bia"))  # só vê os seus
    assert outro.get(reverse("eventos:solicitantes"), {"q": "estadual"}).json()[
        "resultados"] == []
