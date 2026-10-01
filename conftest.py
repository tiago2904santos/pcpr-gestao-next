"""Fixtures compartilhadas."""

from __future__ import annotations

import pytest


@pytest.fixture
def usuario(db, django_user_model):
    return django_user_model.objects.create_user(
        "operador", "operador@pc.pr.gov.br", "senha-forte-123", nome="Operador de Testes"
    )


@pytest.fixture
def cliente_logado(client, usuario):
    client.force_login(usuario)
    return client
