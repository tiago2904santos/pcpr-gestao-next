"""CB7b: "Pedir coffee break" a partir da palestra — o botão só para quem tem os dois
módulos e a OS nasce com município, data, horário, descrição, quem recebe e o público."""

from __future__ import annotations

from datetime import time, timedelta

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio
from gestao.identidade.models import Usuario
from gestao.palestras.models import Palestra, Tema

pytestmark = pytest.mark.django_db


def test_pedir_a_partir_da_palestra():
    hoje = timezone.localdate()
    cwb = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                          defaults={"nome": "Curitiba", "uf": "PR"})[0]
    ana = Usuario.objects.create_user("ana", "ana@teste.invalid", None, nome="Ana")
    ana.groups.add(Group.objects.get(name="ASCOM_PALESTRAS"))
    cli = Client()
    cli.force_login(ana)
    p = Palestra.objects.create(
        data_solicitacao=hoje, solicitante="Colégio X", telefone="41999998888",
        evento="palestra", data_inicio_evento=hoje + timedelta(days=10),
        hora_inicio=time(9, 30), municipio=cwb, local="Auditório", quantidade_publico=80,
        criado_por=ana)
    p.temas.add(Tema.objects.create(nome="Segurança digital"))
    folha = cli.get(reverse("palestras:palestra", args=[p.pk])).content.decode()
    assert "Pedir coffee break" not in folha  # sem o Coffee Break
    ana.groups.add(Group.objects.get(name="ASCOM_COFFEE_BREAK"))
    ana = Usuario.objects.get(pk=ana.pk)  # permissões relidas
    cli.force_login(ana)
    folha = cli.get(reverse("palestras:palestra", args=[p.pk])).content.decode()
    assert "Pedir coffee break" in folha
    nova = cli.get(f"{reverse('coffee:nova')}?origem=palestra:{p.pk}").content.decode()
    assert "Palestra – Segurança digital – Curitiba" in nova and 'value="80"' in nova
    assert 'value="09:30"' in nova and 'value="Colégio X 41999998888"' in nova
