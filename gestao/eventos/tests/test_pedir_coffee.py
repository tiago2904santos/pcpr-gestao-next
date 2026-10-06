"""CB7b: "Pedir coffee break" a partir da solicitação de evento — o botão só
para quem tem o módulo, a OS nasce preenchida e ligada à origem (só origem visível), a
folha mostra de onde veio e avisa a remarcação."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio
from gestao.coffee.models import Contrato, Fornecedor, Lote, Solicitacao
from gestao.eventos.models import Solicitacao as Evento
from gestao.eventos.models import TipoEvento
from gestao.identidade.models import Usuario

pytestmark = pytest.mark.django_db


def _usuario(login: str, *papeis: str) -> Usuario:
    u = Usuario.objects.create_user(login, f"{login}@teste.invalid", None, nome=login.title())
    for p in papeis:
        u.groups.add(Group.objects.get(name=p))
    return u


@pytest.fixture
def cenario():
    hoje = timezone.localdate()
    cwb = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                          defaults={"nome": "Curitiba", "uf": "PR"})[0]
    f = Fornecedor.objects.create(razao_social="Buffet Exemplo Ltda", cnpj="11222333000181")
    c = Contrato.objects.create(fornecedor=f, numero="12/2025", valor_unitario=Decimal("20"),
                                vigencia_fim=hoje + timedelta(days=300))
    lote = Lote.objects.create(contrato=c, numero=1, exercicio=str(hoje.year),
                               quantidade_total=500)
    lote.municipios.set([cwb])
    ana = _usuario("ana", "ASCOM_COFFEE_BREAK")
    evento = Evento.objects.create(
        data_solicitacao=hoje, data_inicio_evento=hoje + timedelta(days=20), municipio=cwb,
        tipo_evento=TipoEvento.objects.get(nome="Feira"), solicitante_nome="Escola X",
        contato="(41) 3000-0000", local_evento="Ginásio", endereco="Rua A, 10", criado_por=ana)
    return ana, evento, cwb, hoje


def test_pedir_a_partir_do_evento(cenario):
    ana, evento, _cwb, hoje = cenario
    cli = Client()
    cli.force_login(ana)
    folha = cli.get(reverse("eventos:solicitacao", args=[evento.pk])).content.decode()
    url = f"{reverse('coffee:nova')}?origem=evento:{evento.pk}"
    assert url.replace("&", "&amp;") in folha and "Pedir coffee break" in folha
    nova = cli.get(url).content.decode()
    assert 'value="Curitiba/PR"' in nova and "Feira – Ginásio – Curitiba" in nova
    assert 'value="Escola X (41) 3000-0000"' in nova and f'value="evento:{evento.pk}"' in nova
    r = cli.post(reverse("coffee:nova"), {
        "municipio": "Curitiba/PR", "data_solicitacao": f"{hoje:%d/%m/%Y}", "numero": "",
        "descricao": "Feira – Ginásio – Curitiba", "quantidade": "40",
        "data_evento": f"{evento.data_inicio_evento:%d/%m/%Y}", "origem": f"evento:{evento.pk}"})
    assert r.status_code == 302
    s = Solicitacao.objects.get()
    assert (s.origem_tipo, s.origem_id) == ("evento", evento.pk)
    assert f"Pedido a partir de Solicitação de evento #{evento.pk}." in s.movimentos.get().texto
    Evento.objects.filter(pk=evento.pk).update(data_inicio_evento=hoje + timedelta(days=25))
    html = cli.get(reverse("coffee:solicitacao", args=[s.pk])).content.decode()
    assert reverse("eventos:solicitacao", args=[evento.pk]) in html
    assert (f"O evento foi remarcado para {hoje + timedelta(days=25):%d/%m/%Y}, e a OS está "
            f"com {hoje + timedelta(days=20):%d/%m/%Y}.") in html


def test_origem_invisivel_ou_sem_modulo(cenario):
    _ana, evento, _cwb, _hoje = cenario
    outro = _usuario("beto", "ASCOM_COFFEE_BREAK")  # tem o coffee, não vê o evento da Ana
    cli = Client()
    cli.force_login(outro)
    nova = cli.get(f"{reverse('coffee:nova')}?origem=evento:{evento.pk}").content.decode()
    assert "Ginásio" not in nova and f"evento:{evento.pk}" not in nova
    sem_coffee = _usuario("caio")
    Evento.objects.filter(pk=evento.pk).update(criado_por=sem_coffee)
    cli.force_login(sem_coffee)
    folha = cli.get(reverse("eventos:solicitacao", args=[evento.pk])).content.decode()
    assert "Pedir coffee break" not in folha

