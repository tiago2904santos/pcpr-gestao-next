from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _entrar(client, identificador, senha):
    return client.post(reverse("identidade:entrar"), {"username": identificador, "password": senha})


def test_entra_com_login_ou_email_sem_diferenciar_caixa(client, usuario):
    assert _entrar(client, "OPERADOR", "senha-forte-123").status_code == 302
    client.logout()
    assert _entrar(client, "Operador@PC.pr.gov.br", "senha-forte-123").status_code == 302


def test_senha_errada_mostra_mensagem_clara(client, usuario):
    resposta = _entrar(client, "operador", "errada")
    assert resposta.status_code == 200
    assert "Usuário ou senha incorretos" in resposta.content.decode()


def test_bloqueio_progressivo_apos_5_tentativas(client, usuario):
    for _ in range(5):
        _entrar(client, "operador", "errada")
    resposta = _entrar(client, "operador", "senha-forte-123")
    assert resposta.status_code == 200
    assert "Muitas tentativas" in resposta.content.decode()


def test_paginas_exigem_login(client):
    resposta = client.get("/")
    assert resposta.status_code == 302 and "/conta/entrar/" in resposta["Location"]


def test_sair_exige_post(cliente_logado):
    assert cliente_logado.get(reverse("identidade:sair")).status_code == 405
    assert cliente_logado.post(reverse("identidade:sair")).status_code == 302


def test_cabecalhos_de_seguranca(client):
    resposta = client.get(reverse("identidade:entrar"))
    csp = resposta["Content-Security-Policy"]
    assert "script-src 'self' 'nonce-" in csp and "unsafe-inline" not in csp
    assert resposta["X-Frame-Options"] == "DENY"
    assert "Server-Timing" in resposta
