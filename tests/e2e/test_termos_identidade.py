"""Identidade migrada: seleção visível, destinos, calendário e ações HTMX."""

from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.viagens import termos
from gestao.viagens.models import Oficio, TermoAutorizacao
from tests.e2e.conftest import rodar_axe

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_relacoes_visiveis_destinos_e_acoes(logado, dados_e2e, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 700})
    oficio = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])
    termo = termos.salvar(dados_e2e.usuarios["operador"], oficio=oficio)
    pg.goto(f"/viagens/termos/{termo.pk}/")
    cartao = pg.locator("#transporte [data-viatura-cartao]")
    expect(cartao).to_be_visible()
    expect(cartao.locator("[data-recurso-titulo]")).to_contain_text(oficio.viatura.placa_formatada)
    expect(pg.locator("[data-destino] [data-alca] .itin__ordem").first).to_have_text("1")
    # A antiga grade de seis colunas não pode esmagar os cartões compactos.
    equipe = pg.locator(".campo-equipe--compacta .equipe__cartoes")
    assert equipe.evaluate(
        """e => [...e.children].every(c => c.getBoundingClientRect().height < 80 &&
        c.getBoundingClientRect().width >= e.getBoundingClientRect().width * 0.4)"""
    )
    # O calendário abre por teclado e retorna o foco, sem alterar o período.
    calendario = pg.locator("pc-data[data-periodo] button.seletor__botao")
    calendario.focus()
    calendario.press("Enter")
    expect(calendario).to_have_attribute("aria-expanded", "true")
    pg.keyboard.press("Escape")
    expect(calendario).to_be_focused()
    assert pg.locator(".barra-acoes").evaluate("e => getComputedStyle(e).position") == "static"
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert rodar_axe(pg) == []
    # Remover o recurso limpa o campo e grava a escolha verdadeira.
    cartao.get_by_role("button", name="Remover viatura", exact=False).click()
    expect(cartao).to_be_hidden()
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    termo.refresh_from_db()
    assert termo.viatura_id is None
    # A lista não perde contagem/ação ao receber resultados por HTMX.
    pg.goto("/viagens/termos/")
    busca = pg.get_by_role("searchbox", name="Buscar")
    busca.fill("termo-sem-resultado-identidade")
    expect(pg.locator(".barra-acoes__status")).to_contain_text("0 termos")
    expect(busca).to_be_focused()
    expect(pg.get_by_role("button", name="Novo termo", exact=True)).to_be_visible()
    assert rodar_axe(pg) == []
    busca.fill(termos.efetivo(termo).destinos[0].nome)
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    menu = pg.get_by_role("button", name=f"Ações do {termo}")
    menu.focus()
    menu.press("Enter")
    expect(pg.get_by_role("menuitem", name="Baixar documentos", exact=True)).to_be_focused()
    pg.keyboard.press("Escape")
    expect(menu).to_be_focused()
    pasta = Path("artifacts/termos-identidade")
    pasta.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(pasta/f"lista-{largura}.png"), full_page=True)
    assert TermoAutorizacao.objects.count() == 1
    assert pg.erros_console == []


def test_paginacao_e_consulta_sem_edicao(logado, dados_e2e):
    """Lista longa e consulta preservam acesso, sem oferecer ações de escrita."""
    from tests.e2e.conftest import entrar

    pg = logado
    oficio = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])
    for _ in range(21):
        termos.salvar(dados_e2e.usuarios["operador"], oficio=oficio)
    pg.goto("/viagens/termos/")
    expect(pg.locator(".registro-operacional")).to_have_count(20)
    pg.get_by_role("link", name="Próxima página", exact=True).click()
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    expect(pg.locator(".barra-acoes__status")).to_contain_text("21 termos")
    termo = TermoAutorizacao.objects.first()
    pg.context.clear_cookies()
    entrar(pg, "consulta")
    pg.goto(f"/viagens/termos/{termo.pk}/")
    expect(pg.locator("#form-termo fieldset").first).to_have_attribute("disabled", "")
    expect(pg.locator("#id_evento")).to_be_disabled()
    expect(pg.locator("pc-editor-documento")).to_have_count(0)
    expect(pg.get_by_role("button", name="Finalizar", exact=True)).to_have_count(0)
    assert rodar_axe(pg) == []
    assert pg.erros_console == []


def test_via_assinada_no_editor_migrado(logado, dados_e2e, tmp_path):
    """Anexo real pela barra operacional; via permanece separada do PDF gerado."""
    from gestao.viagens.models import ViaAssinada
    from tests.e2e.test_assinados import PDF

    pg = logado
    termo = termos.salvar(
        dados_e2e.usuarios["operador"],
        oficio=Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"]),
    )
    pg.goto(f"/viagens/termos/{termo.pk}/#previa")
    bloco = pg.locator("pc-editor-documento").first
    pg.locator("#previa").scroll_into_view_if_needed()
    bloco.get_by_role("link", name="Anexar", exact=True).click()
    janela = pg.get_by_role("dialog", name="Anexar via assinada")
    expect(janela).to_be_visible()
    arquivo = tmp_path / "termo-assinado.pdf"
    arquivo.write_bytes(PDF)
    janela.locator('input[type="file"]').set_input_files(str(arquivo))
    janela.get_by_role("button", name="Anexar via assinada").click()
    expect(pg.locator(".toast").first).to_contain_text("Via assinada anexada")
    pg.locator("#previa").scroll_into_view_if_needed()
    expect(bloco.locator("[data-anexar-assinado]")).to_have_text("Trocar via")
    via = ViaAssinada.objects.get()
    assert via.termo_id == termo.pk
    assert pg.request.get(f"/viagens/assinados/via/{via.pk}/").body() == PDF
    pg.goto("/viagens/termos/")
    expect(pg.locator(".registro-operacional")).to_contain_text("assinado")
    assert pg.erros_console == []
