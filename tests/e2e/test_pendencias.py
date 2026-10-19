"""Aba Pendências da Agenda no navegador: 1440 e 360 px, axe sem violações, sem rolagem
horizontal, e o caminho até a conferência do envio manual."""

import os
import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone
from playwright.sync_api import expect

from gestao.viagens import prestacao
from gestao.viagens.models import PrestacaoServidor

from .conftest import entrar, estabilizar, rodar_axe

pytestmark = [pytest.mark.e2e, pytest.mark.a11y, pytest.mark.django_db(transaction=True)]
# Capturas fora do repositório (pasta indicada pelo ambiente); sem ela, nada é salvo.
CAPTURAS = os.environ.get("PENDENCIAS_CAPTURAS", "")


@pytest.mark.parametrize("largura", [1440, 360])
def test_aba_pendencias(pagina, dados_e2e, settings, largura):
    settings.AUTOMACAO_TRANSPORTE = "manual"
    cen = dados_e2e
    hoje = timezone.localdate()
    a, b = PrestacaoServidor.objects.filter(
        prestacao__oficio_id=cen.ids["oficio_emitido"]).order_by("pk")
    PrestacaoServidor.objects.filter(pk=b.pk).update(prazo_limite_saque=hoje - timedelta(days=40))
    prestacao.salvar_solicitacao(cen.usuarios["operador"], a.pk, numero="2026/0001",
                                 liberacao=hoje, prazo=hoje + timedelta(days=2))
    pg = pagina
    pg.set_viewport_size({"width": largura, "height": 900})
    entrar(pg)
    pg.goto("/agenda/pendencias/")
    expect(pg.get_by_role("heading", name="Pendências", exact=True)).to_be_visible()
    expect(pg.get_by_role("heading", name="Envios aos servidores")).to_be_visible()
    expect(pg.get_by_role("heading", name="Ofícios em rascunho")).to_be_visible()
    expect(pg.get_by_role("heading", name="Prestação vencida")).to_be_visible()
    estabilizar(pg)
    assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not rodar_axe(pg)
    if CAPTURAS:
        Path(CAPTURAS).mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(Path(CAPTURAS) / f"pendencias-{largura}.png"), full_page=True)
    # Uma seção por vez (aba), e o item leva à conferência do envio.
    pg.get_by_role("link", name="Envios aos servidores").first.click()
    expect(pg).to_have_url(re.compile(r"/agenda/pendencias/\?secao=envios$"))
    estabilizar(pg)
    assert not rodar_axe(pg)
    if CAPTURAS:
        pg.screenshot(path=str(Path(CAPTURAS) / f"pendencias-envios-{largura}.png"),
                      full_page=True)
    pg.locator(f'.registro-operacional__conferencia a[href="/viagens/envios/{a.pk}/"]').click()
    expect(pg).to_have_url(re.compile(rf"/viagens/envios/{a.pk}/$"))
    expect(pg.get_by_role("link", name="Voltar às pendências")).to_be_visible()
