"""Gerar documentos em lote (módulo 8c, paridade com pacote.py da referência): um ofício por
equipe com roteiro e motivo; motorista entra na equipe; termos menos a unidade emissora; OS e
plano só se faltarem; validações todas de uma vez; tela com adicionar/remover ofício."""

from __future__ import annotations

from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from gestao.cadastros.models import Municipio, Servidor, TipoViagem, Viatura
from gestao.viagens import viagem, viagem_lote
from gestao.viagens.models import Oficio, Roteiro, TermoAutorizacao, Viagem

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def c():
    cen = cenario_completo()
    TipoViagem.objects.create(nome="Unidade Móvel")
    return cen


def _viagem(c, com_roteiro=True) -> Viagem:
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    vinculos = {"roteiros": [Roteiro.objects.get(pk=c.ids["roteiro"])]} if com_roteiro else {}
    viagem.salvar_dados(op, v.pk, tipos=list(TipoViagem.objects.all()), motivo="Feira (teste)",
                        data_inicio=date(2030, 5, 10),
                        destinos=[Municipio.objects.get(nome="Londrina", uf="PR")],
                        vinculos=vinculos)
    return Viagem.objects.get(pk=v.pk)


def _servidores(n):
    return list(Servidor.objects.filter(ativo=True).order_by("pk")[:n])


def test_gera_oficios_termos_os_e_plano(c):
    v = _viagem(c)
    a, b, m = _servidores(3)
    viatura = Viatura.objects.filter(ativo=True).first()
    r = viagem_lote.gerar(c.usuarios["operador"], v.pk, [
        viagem_lote.Equipe(servidores=[a], motorista=m, viatura=viatura),
        viagem_lote.Equipe(servidores=[b])])
    assert len(r.oficios) == 2 and r.ordem is not None and r.plano is not None
    primeiro = Oficio.objects.get(pk=r.oficios[0].pk)
    assert primeiro.viagem_id == v.pk and primeiro.motivo == "Feira (teste)"
    assert primeiro.roteiro_id == c.ids["roteiro"] and primeiro.trechos.exists()
    equipe = set(primeiro.viajantes.values_list("servidor_id", flat=True))
    assert equipe == {a.pk, m.pk}  # o motorista entrou na equipe
    assert primeiro.viatura_id == viatura.pk
    v.refresh_from_db()
    assert v.situacao == Viagem.Situacao.GERADOS
    assert TermoAutorizacao.objects.filter(viagem=v).count() == r.termos


def test_validacoes_de_uma_vez(c):
    v = _viagem(c)
    a, b = _servidores(2)
    viatura = Viatura.objects.filter(ativo=True).first()
    with pytest.raises(viagem_lote.LoteInvalido) as erro:
        viagem_lote.gerar(c.usuarios["operador"], v.pk, [
            viagem_lote.Equipe(servidores=[a], viatura=viatura),
            viagem_lote.Equipe(servidores=[a, b], viatura=viatura),
            viagem_lote.Equipe(servidores=[])])
    texto = " ".join(erro.value.erros)
    assert "cada servidor vai em um ofício só" in texto
    assert "Ofício 3: escolha ao menos um servidor." in texto
    assert f"A viatura {viatura} está nos ofícios 1 e 2." in texto
    with pytest.raises(viagem_lote.LoteInvalido, match="Monte ao menos um ofício"):
        viagem_lote.gerar(c.usuarios["operador"], v.pk, [])


def test_servidor_ja_em_oficio_da_viagem_e_os_existente(c):
    v = _viagem(c)
    a, b = _servidores(2)
    viagem_lote.gerar(c.usuarios["operador"], v.pk, [viagem_lote.Equipe(servidores=[a])])
    with pytest.raises(viagem_lote.LoteInvalido, match="já está no"):
        viagem_lote.gerar(c.usuarios["operador"], v.pk, [viagem_lote.Equipe(servidores=[a])])
    r = viagem_lote.gerar(c.usuarios["operador"], v.pk, [viagem_lote.Equipe(servidores=[b])])
    assert r.ordem is None and any("não foi alterada" in a for a in r.avisos)


def test_sem_roteiro_avisa(c):
    v = _viagem(c, com_roteiro=False)
    r = viagem_lote.gerar(c.usuarios["operador"], v.pk,
                          [viagem_lote.Equipe(servidores=_servidores(1))])
    assert any("sem roteiro" in a for a in r.avisos)


def test_tela_adicionar_e_gerar(c):
    v = _viagem(c)
    a, b = _servidores(2)
    cli = Client()
    cli.force_login(c.usuarios["operador"])
    url = reverse("viagens:gerar_documentos_viagem", args=[v.pk])
    html = cli.get(url).content.decode()
    assert "Ofício 1" in html and "Gerar documentos" in html
    r = cli.post(url, {"quantidade": "1", "acao": "adicionar", "equipe_0": [str(a.pk)]})
    html = r.content.decode()
    assert "Ofício 2" in html and not Oficio.objects.filter(viagem=v).exists()
    r = cli.post(url, {"quantidade": "2", "acao": "gerar", "equipe_0": [str(a.pk)],
                       "equipe_1": [str(b.pk)], "termos": "on", "ordem": "on", "plano": "on"})
    assert r.status_code == 302 and Oficio.objects.filter(viagem=v).count() == 2
    r = cli.post(url, {"quantidade": "1", "acao": "gerar"})
    assert r.status_code == 422 and "Monte ao menos um ofício com a equipe." in r.content.decode()


def test_consulta_nao_gera(c):
    v = _viagem(c)
    cli = Client()
    cli.force_login(c.usuarios["consulta"])
    r = cli.get(reverse("viagens:gerar_documentos_viagem", args=[v.pk]), follow=True)
    assert "Reative a viagem antes de gerar documentos." in r.content.decode()
