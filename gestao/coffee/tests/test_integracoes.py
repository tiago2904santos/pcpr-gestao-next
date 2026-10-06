"""CB7a: o Coffee Break na Agenda (OS com data; prazos de vigência e de certidão, só a
certidão vigente de cada tipo), na busca global e no cartão da página inicial — tudo só
para quem tem o módulo."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio
from gestao.coffee import pedidos
from gestao.coffee.models import Certidao, Contrato, Fornecedor, Lote, Solicitacao, TermoAditivo
from gestao.identidade.models import Usuario
from gestao.plataforma import agenda, busca

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    u = Usuario.objects.create_user("ana", "ana@teste.invalid", None, nome="Ana")
    u.groups.add(Group.objects.get(name="ASCOM_COFFEE_BREAK"))
    hoje = timezone.localdate()
    f = Fornecedor.objects.create(razao_social="Buffet Exemplo Ltda", cnpj="11222333000181")
    c = Contrato.objects.create(fornecedor=f, numero="12/2025", valor_unitario=Decimal("20"),
                                vigencia_fim=hoje + timedelta(days=10))
    TermoAditivo.objects.create(contrato=c, numero="1", vigencia_fim=hoje + timedelta(days=20))
    cwb = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                          defaults={"nome": "Curitiba", "uf": "PR"})[0]
    lote = Lote.objects.create(contrato=c, numero=1, exercicio=str(hoje.year),
                               quantidade_total=100)
    lote.municipios.set([cwb])
    s = pedidos.salvar(u, {"municipio": cwb, "data_solicitacao": hoje, "numero": "",
                           "descricao": "Posse da diretoria", "quantidade": 40}).solicitacao
    Solicitacao.objects.filter(pk=s.pk).update(data_evento=hoje + timedelta(days=3),
                                               nota_fiscal="8957")
    for validade in (hoje + timedelta(days=5), hoje + timedelta(days=40)):  # a 2ª renova
        Certidao.objects.create(fornecedor=f, tipo="fgts", validade=validade, enviada_por=u,
                                arquivo=ContentFile(b"%PDF-1.4", name="c.pdf"))
    return u, s, hoje


def test_agenda(cenario):
    u, s, hoje = cenario
    itens = agenda.compromissos_de(u, hoje, hoje + timedelta(days=60),
                                   ["coffee", "coffee_contratos", "coffee_certidoes"])
    por_chave = {i.chave: i for i in itens}
    os_ = por_chave[f"coffee-{s.pk}"]
    assert os_.titulo == "Posse da diretoria (40)" and os_.situacao == "Ativa"
    assert os_.url == reverse("coffee:solicitacao", args=[s.pk])
    contrato = next(i for i in itens if i.chave.startswith("contrato-"))
    assert contrato.titulo == "Fim da vigência — Contrato 12/2025 (Buffet Exemplo Ltda)"
    assert contrato.prazo and contrato.tom == "aviso"
    assert any(i.titulo.startswith("Fim da vigência — Termo aditivo 1 · Contrato 12/2025")
               for i in itens)
    certidoes = [i for i in itens if i.fonte == "coffee_certidoes"]
    assert len(certidoes) == 1  # a renovada não marca o dia da antiga
    assert certidoes[0].titulo == "Certidão FGTS vence — Buffet Exemplo Ltda"
    pedidos.cancelar(u, s.pk, "Desmarcado")
    os_ = next(i for i in agenda.compromissos_de(u, hoje, hoje + timedelta(days=10), ["coffee"]))
    assert os_.encerrado and os_.situacao == "Cancelada"
    outro = Usuario.objects.create_user("beto", "beto@teste.invalid", None, nome="Beto")
    assert not any(f.slug.startswith("coffee") for f in agenda.fontes_de(outro))
    assert agenda.compromissos_de(outro, hoje, hoje + timedelta(days=60), ["coffee"]) == []


def test_busca_global(cenario):
    u, s, _hoje = cenario
    resultados = busca.buscar(u, "8957")
    assert [r["grupo"] for r in resultados] == ["Coffee break"]
    assert resultados[0]["url"] == reverse("coffee:solicitacao", args=[s.pk])
    assert busca.buscar(u, "posse")[0]["titulo"].endswith("Posse da diretoria")
    outro = Usuario.objects.create_user("beto", "beto@teste.invalid", None, nome="Beto")
    assert busca.buscar(outro, "8957") == []


def test_cartao_da_pagina_inicial(cenario):
    u, _s, hoje = cenario
    cli = Client()
    cli.force_login(u)
    html = cli.get(reverse("painel:inicio")).content.decode()
    assert "Saldo dos lotes" in html and "Lotes em alerta" in html
    from gestao.coffee import painel
    assert painel.indicadores_do_inicio(hoje) == [("Saldo dos lotes", 60, False),
                                                  ("Pendências", 1, True),
                                                  ("Lotes em alerta", 0, False)]
