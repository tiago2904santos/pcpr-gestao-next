"""O resultado do trecho acompanha o autosave; concluir não finaliza a prestação."""

import re
from urllib.parse import quote

import pytest
from playwright.sync_api import expect

from gestao.viagens.models import DiarioBordo, PrestacaoContas

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_resultado_vivo_estado_visivel_e_conclusao(logado, dados_e2e, largura):
    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 600})
    pg.goto(f"/viagens/prestacoes/equipe/{p.pk}/diario/")
    d = DiarioBordo.objects.get(prestacao=p)
    trecho = d.linhas.order_by("ordem").first()
    resultado = pg.locator(f"#rodado-{trecho.pk}")
    expect(resultado).to_contain_text("A preencher")
    pg.locator(f"#l-{trecho.pk}-km_inicial").fill("10000")
    chegada = pg.locator(f"#l-{trecho.pk}-km_final")
    chegada.fill("10440")
    expect(resultado).to_contain_text("440 km")
    expect(chegada).to_be_focused()
    estado = pg.locator("[data-status-salvamento]")
    expect(estado).to_contain_text("Salvo automaticamente")
    expect(estado).to_be_visible()
    assert pg.locator(".barra-acoes").evaluate("e=>getComputedStyle(e).position") == "static"
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    chegada.fill("10470")
    expect(resultado).to_contain_text("470 km")
    expect(chegada).to_be_focused()
    finalizar = pg.get_by_role("button", name="Finalizar", exact=True)
    finalizar.focus()
    finalizar.press("Enter")
    expect(pg).to_have_url(re.compile(
        r"/viagens/prestacoes/\?q=" + re.escape(quote(p.oficio.numero_formatado, safe=""))))
    trecho.refresh_from_db()
    assert trecho.km_final == 10470
    assert not p.servidores.filter(finalizada_em__isnull=False).exists()
    pg.wait_for_load_state("networkidle")
    assert pg.erros_console == []
