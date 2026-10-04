"""Repetir viagem (módulo 8d, paridade com duplicar.py da referência): datas deslocadas,
cidade trocada, números novos, sem protocolo; documentos cancelados ficam de fora."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.test import Client
from django.urls import reverse

from gestao.cadastros.models import Municipio, Servidor, TipoViagem
from gestao.viagens import viagem, viagem_lote, viagem_repetir
from gestao.viagens.models import Oficio, OrdemServico, PlanoTrabalho, Roteiro, Viagem

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def c():
    cen = cenario_completo()
    TipoViagem.objects.create(nome="Unidade Móvel")
    return cen


def _m(nome):
    return Municipio.objects.get(nome=nome, uf="PR")


def _viagem_completa(c) -> Viagem:
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    roteiro = Roteiro.objects.get(pk=c.ids["roteiro"])
    inicio = roteiro.trechos.order_by("ordem").first().saida_em.date()
    viagem.salvar_dados(op, v.pk, tipos=list(TipoViagem.objects.all()), motivo="Feira",
                        data_inicio=inicio, data_fim=inicio + timedelta(days=1),
                        destinos=[_m("Ponta Grossa")], vinculos={"roteiros": [roteiro]})
    viagem_lote.gerar(op, v.pk, [viagem_lote.Equipe(
        servidores=list(Servidor.objects.filter(ativo=True).order_by("pk")[:2]))])
    return Viagem.objects.get(pk=v.pk)


def test_repetir_desloca_datas_e_troca_cidade(c):
    op = c.usuarios["operador"]
    v = _viagem_completa(c)
    original = viagem.documentos(v)
    nova_data = v.data_inicio + timedelta(days=30)
    nova = viagem_repetir.repetir(op, v.pk, nova_data, _m("Londrina"))
    assert nova.pk != v.pk and nova.data_inicio == nova_data
    assert [d.municipio for d in nova.destinos.all()] == [_m("Londrina")]
    docs = viagem.documentos(nova)
    assert len(docs.oficios) == len(original.oficios) == 1
    novo, velho = docs.oficios[0], original.oficios[0]
    assert novo.numero != velho.numero and not novo.protocolo
    assert novo.situacao == Oficio.Situacao.RASCUNHO
    assert set(novo.viajantes.values_list("servidor_id", flat=True)) == set(
        velho.viajantes.values_list("servidor_id", flat=True))
    t_novo = novo.trechos.order_by("ordem").first()
    t_velho = velho.trechos.order_by("ordem").first()
    assert t_novo.saida_em - t_velho.saida_em == timedelta(days=30)
    assert docs.ordens and docs.planos and docs.roteiros
    assert PlanoTrabalho.objects.get(pk=docs.planos[0].pk).data_inicio == nova_data
    assert OrdemServico.objects.get(pk=docs.ordens[0].pk).viagem_id == nova.pk


def test_sem_data_nao_repete(c):
    v = viagem.criar(c.usuarios["operador"])
    with pytest.raises(viagem.ViagemInvalida, match="não tem data para servir de base"):
        viagem_repetir.repetir(c.usuarios["operador"], v.pk, date(2031, 1, 1))


def test_tela_repetir(c):
    op = c.usuarios["operador"]
    v = _viagem_completa(c)
    cli = Client()
    cli.force_login(op)
    html = cli.get(reverse("viagens:editar_viagem", args=[v.pk])).content.decode()
    assert "Repetir viagem" in html and 'id="dialogo-repetir"' in html
    r = cli.post(reverse("viagens:repetir_viagem", args=[v.pk]), {"nova_data": ""}, follow=True)
    assert "Informe a data da nova edição." in r.content.decode()
    nova_data = (v.data_inicio + timedelta(days=7)).strftime("%d/%m/%Y")
    r = cli.post(reverse("viagens:repetir_viagem", args=[v.pk]), {"nova_data": nova_data},
                 follow=True)
    assert "Viagem repetida em rascunho" in r.content.decode()
    assert Viagem.objects.count() == 2
