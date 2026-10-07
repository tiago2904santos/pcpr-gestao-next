"""Sessão expirada em pedidos assíncronos (QA Lote 3, I1): o servidor não manda a tela de
login para dentro de um menu, de uma lista trocada ao vivo ou de um JSON — responde 401 com
o caminho de volta, e o front avisa "Sua sessão terminou — entre de novo"."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db

ACOES = "/viagens/oficios/1/acoes/"


def test_navegacao_comum_continua_indo_ao_login(client):
    r = client.get("/viagens/oficios/")
    assert r.status_code == 302 and r["Location"].startswith("/conta/entrar/?next=")


@pytest.mark.parametrize("cabecalhos", [
    {"HTTP_HX_REQUEST": "true"},
    {"HTTP_SEC_FETCH_DEST": "empty"},
    {"HTTP_X_REQUESTED_WITH": "fetch"},
    {"HTTP_ACCEPT": "application/json"},
])
def test_pedido_assincrono_recebe_401_com_o_caminho_de_volta(client, cabecalhos):
    r = client.get(ACOES, HTTP_REFERER="http://testserver/viagens/oficios/?documento=rascunho",
                   **cabecalhos)
    assert r.status_code == 401
    assert r["X-Sessao-Expirada"] == "1"
    corpo = r.json()
    assert corpo["mensagem"] == "Sua sessão terminou — entre de novo."
    # Volta para a página onde a pessoa estava, não para o fragmento.
    assert corpo["entrar"] == "/conta/entrar/?next=/viagens/oficios/%3Fdocumento%3Drascunho"


def test_htmx_ganha_redirecionamento_da_pagina_inteira(client):
    r = client.get("/viagens/oficios/", HTTP_HX_REQUEST="true",
                   HTTP_HX_CURRENT_URL="http://testserver/viagens/oficios/?q=maringa")
    assert r.status_code == 401
    assert r["HX-Redirect"] == "/conta/entrar/?next=/viagens/oficios/%3Fq%3Dmaringa"


def test_referer_de_outro_site_nao_vira_destino(client):
    r = client.get(ACOES, HTTP_SEC_FETCH_DEST="empty", HTTP_REFERER="https://mal.example/x")
    assert r.json()["entrar"] == "/conta/entrar/?next=/viagens/oficios/1/acoes/"
