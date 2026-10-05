"""E2E: palestras — registrar o pedido com tema, a folha se grava sozinha, agendar pelo
andamento (a tela pede a data e o palestrante), responder com a resposta padrão e ver a
lista pela aba de status."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _dar_papel() -> None:
    from django.contrib.auth.models import Group

    from gestao.identidade.models import Usuario

    Usuario.objects.get(login="operador").groups.add(Group.objects.get(name="ASCOM_PALESTRAS"))


def test_registrar_agendar_e_responder(logado, dados_e2e):
    from datetime import timedelta

    from django.utils import timezone

    from gestao.palestras.models import Palestra, Palestrante, RespostaPadrao, Tema

    _dar_papel()
    Tema.objects.create(nome="Golpes pela internet")
    Palestrante.objects.create(nome="Ana Ribeiro", lotacao="DPCAP")
    RespostaPadrao.objects.create(tipo="Confirmação", mensagem="Olá, {solicitante}! Até {data}.")
    pg = logado
    pg.goto("/palestras/")
    pg.get_by_role("link", name="Nova palestra").first.click()
    pg.locator("#id_solicitante").fill("Colégio Estadual (e2e)")
    pg.locator("#id_telefone").fill("41999998888")
    pg.get_by_label("Golpes pela internet").check()
    pg.get_by_role("button", name="Registrar palestra").click()
    expect(pg).to_have_url(re.compile(r"/palestras/pedidos/\d+/$"))
    p = Palestra.objects.get()
    assert p.telefone == "(41) 99999-8888" and p.temas.count() == 1

    pg.locator("#id_local").fill("Auditório (e2e)")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text(re.compile("Salvo"),
                                                                    timeout=10000)
    p.refresh_from_db()
    assert p.local == "Auditório (e2e)"

    data = timezone.localdate() + timedelta(days=5)
    pg.locator("label.opcao", has_text="Agendada").click()
    pg.locator("#id_data_evento").fill(f"{data:%d/%m/%Y}")
    pg.get_by_role("combobox", name="Palestrante", exact=True).click()
    pg.get_by_role("option", name="Ana Ribeiro").click()
    pg.get_by_role("button", name="Registrar andamento").click()
    expect(pg.locator("#frase-palestra")).to_contain_text("Agendada")
    expect(pg.locator("#frase-palestra")).to_contain_text(f"{data:%d/%m/%Y}")

    pg.get_by_role("combobox", name="Resposta padrão").click()
    pg.get_by_role("option", name="Confirmação").click()
    expect(pg.locator("#id_texto")).to_have_value(
        f"Olá, Colégio Estadual (e2e)! Até {data:%d/%m/%Y}.")
    pg.get_by_role("button", name="Registrar resposta").click()
    expect(pg.get_by_role("link", name="Abrir no WhatsApp")).to_be_visible()
    expect(pg.locator("#historico")).to_contain_text("Resposta enviada: Confirmação")

    pg.goto("/palestras/pedidos/?status=agendada")
    expect(pg.locator(".registro__link", has_text="Palestra")).to_be_visible()
    assert not pg.erros_console  # type: ignore[attr-defined]


@pytest.mark.parametrize("largura", [360, 1440])
def test_telas_sem_rolagem_horizontal(logado, dados_e2e, largura):
    from django.utils import timezone

    from gestao.identidade.models import Usuario
    from gestao.palestras import services

    _dar_papel()
    u = Usuario.objects.get(login="operador")
    p = services.criar(u, {"data_solicitacao": timezone.localdate(),
                           "solicitante": "Associação com um nome bem comprido para testar a "
                                          "quebra de linha na tela (e2e)"})
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    for rota in ("/palestras/", "/palestras/pedidos/", f"/palestras/pedidos/{p.pk}/",
                 "/palestras/pedidos/nova/", "/palestras/cadastros/palestrantes/",
                 "/palestras/cadastros/temas/", "/palestras/cadastros/respostas/"):
        pg.goto(rota)
        excesso = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert excesso <= 0, f"{rota} @ {largura}px: rolagem horizontal de {excesso}px"
