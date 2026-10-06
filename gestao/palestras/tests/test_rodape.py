"""Rodapé padrão das folhas (pedido do usuário, 06/10): Finalizar e Ações (Duplicar) na
palestra; duplicar cria a palestra nova com o pedido e o lugar, pendente e sem data."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.identidade.models import Usuario
from gestao.palestras.models import Palestra, Tema

pytestmark = pytest.mark.django_db


def test_finalizar_e_duplicar():
    u = Usuario.objects.create_user("ascom", "ascom@teste.invalid", None, nome="Ascom")
    u.groups.add(Group.objects.get(name="ASCOM_PALESTRAS"))
    p = Palestra.objects.create(
        data_solicitacao=timezone.localdate() - timedelta(days=30), solicitante="Colégio X",
        telefone="41999998888", local="Auditório", status=Palestra.Status.ATENDIDA,
        data_inicio_evento=timezone.localdate() - timedelta(days=10), quantidade_publico=50,
        criado_por=u)
    p.temas.add(Tema.objects.create(nome="Golpes digitais"))
    cli = Client()
    cli.force_login(u)
    html = cli.get(reverse("palestras:palestra", args=[p.pk])).content.decode()
    assert 'form="finalizar-palestra"' in html and "Duplicar palestra" in html
    r = cli.post(reverse("palestras:duplicar", args=[p.pk]))
    nova = Palestra.objects.exclude(pk=p.pk).get()
    assert r["Location"] == reverse("palestras:palestra", args=[nova.pk])
    assert (nova.solicitante, nova.local, nova.quantidade_publico) == ("Colégio X",
                                                                        "Auditório", 50)
    assert nova.status == Palestra.Status.PENDENTE and nova.data_inicio_evento is None
    assert nova.data_solicitacao == timezone.localdate()
    assert list(nova.temas.values_list("nome", flat=True)) == ["Golpes digitais"]
