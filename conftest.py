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


@pytest.fixture
def trilha_descartavel(django_db_blocker):
    """Para testes que ADULTERAM a trilha de propósito: limpa antes e depois.

    A tabela é protegida contra DELETE/TRUNCATE; só aqui (banco de teste) o
    trigger é desligado momentaneamente para descartar os eventos.
    """
    from django.db import connection

    def limpar():
        with django_db_blocker.unblock(), connection.cursor() as cur:
            cur.execute("ALTER TABLE auditoria_evento DISABLE TRIGGER auditoria_evento_imutavel")
            cur.execute("DELETE FROM auditoria_evento")
            cur.execute("ALTER TABLE auditoria_evento ENABLE TRIGGER auditoria_evento_imutavel")

    limpar()
    yield
    limpar()
