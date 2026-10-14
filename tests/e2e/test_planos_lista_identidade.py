"""Lista operacional de Planos: ordenação, HTMX, menu e permissões preservados."""

from datetime import date
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.cadastros.models import Municipio
from gestao.viagens import planos
from gestao.viagens.models import PlanoTrabalho
from tests.e2e.conftest import entrar, rodar_axe

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_lista_busca_ordem_menu_e_aba(logado, dados_e2e, largura):
    pg = logado
    op = dados_e2e.usuarios["operador"]
    a, _ = planos.salvar(op, destinos=[Municipio.objects.get(nome="Maringá", uf="PR")],
                         data_inicio=date(2030, 6, 25), data_fim=date(2030, 6, 27))
    b, _ = planos.salvar(op)
    pg.set_viewport_size({"width": largura, "height": 700})
    pg.goto("/viagens/planos/")
    expect(pg.locator(".registro-hero")).to_contain_text("Planos de trabalho")
    expect(pg.locator(".registro-operacional")).to_have_count(2)
    assert pg.locator(".barra-acoes").evaluate("e => getComputedStyle(e).position") == "sticky"  # rodapé grudado, como no ofício
    busca = pg.get_by_role("searchbox", name="Buscar")
    busca.fill("sem-resultado-identidade-planos")
    expect(pg.locator(".barra-acoes__status")).to_contain_text("0 planos")
    expect(busca).to_be_focused()
    expect(pg.get_by_role("button", name="Novo plano de trabalho", exact=True)).to_be_visible()
    busca.fill("Maringá")
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    expect(pg.locator(".registro-operacional .registro__link")).to_contain_text(str(a))
    # OOB preserva contagens e a dimensão temporal; ordenar mantém busca.
    pg.get_by_role("combobox", name="Ordenar por").click()
    pg.get_by_role("option", name="Período (próximos)", exact=True).click()
    expect(pg).to_have_url(pytest_url("ordem=periodo"))
    expect(pg.locator("#busca-planos")).to_have_value("Maringá")
    expect(pg.locator(".registros__grupo")).to_contain_text("Junho")
    expect(pg.locator("#abas-filtro")).to_contain_text("Que vão acontecer")
    menu = pg.get_by_role("button", name=f"Ações do {a}", exact=True)
    menu.focus()
    menu.press("Enter")
    expect(pg.get_by_role("menuitem", name="Ver resumo", exact=True)).to_be_focused()  # o resumo abre o menu
    expect(pg.get_by_role("menuitem", name="Abrir", exact=True)).to_be_visible()
    expect(pg.get_by_role("menuitem", name="Abrir o plano (PDF)")).to_have_count(0)
    pg.keyboard.press("Escape")
    expect(menu).to_be_focused()
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert rodar_axe(pg) == []
    pasta = Path("artifacts/planos-lista-identidade")
    pasta.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(pasta / f"lista-{largura}.png"), full_page=True)
    pg.goto("/viagens/planos/?ordem=numero")
    expect(pg.locator(".registro-operacional .registro__link").first).to_contain_text(str(a))
    expect(pg.locator(".registro-operacional .registro__link").last).to_contain_text(str(b))
    assert pg.erros_console == []


def pytest_url(fragment):
    import re
    return re.compile(re.escape(fragment))


def test_paginacao_cancelamento_e_leitura(logado, dados_e2e):
    pg = logado
    op = dados_e2e.usuarios["operador"]
    alvo, _ = planos.salvar(op)
    for _ in range(20):
        planos.salvar(op)
    pg.goto("/viagens/planos/")
    expect(pg.locator(".registro-operacional")).to_have_count(20)
    expect(pg.locator(".barra-acoes__status")).to_contain_text("21 planos")
    expect(pg.locator(".barra-acoes--acompanha")).to_be_visible()
    pg.goto(f"/viagens/planos/?q={alvo.ano}&aba=futuros&ordem=numero")
    pg.get_by_role("link", name="Próxima página", exact=True).click()
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    expect(pg.locator("#busca-planos")).to_have_value(str(alvo.ano))
    expect(pg).to_have_url(pytest_url("aba=futuros"))
    expect(pg).to_have_url(pytest_url("ordem=numero"))
    pg.goto("/viagens/planos/?pagina=2")
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    pg.get_by_role("button", name=f"Ações do {alvo}", exact=True).click()
    pg.get_by_role("menuitem", name="Cancelar", exact=True).press("Enter")
    dialogo = pg.get_by_role("dialog", name=f"Cancelar o {alvo}?")
    dialogo.get_by_label("Motivo do cancelamento").fill("Evento adiado para revisão")
    dialogo.get_by_role("button", name="Cancelar plano", exact=True).click()
    alvo.refresh_from_db()
    assert alvo.cancelado
    pg.goto("/viagens/planos/?aba=cancelados")
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    expect(pg.locator(".registro__texto")).to_contain_text("Evento adiado")
    pg.context.clear_cookies()
    entrar(pg, "consulta")
    pg.goto("/viagens/planos/?aba=cancelados")
    pg.get_by_role("button", name=f"Ações do {alvo}", exact=True).click()
    expect(pg.get_by_role("menuitem", name="Abrir", exact=True)).to_be_visible()
    expect(pg.get_by_role("menuitem", name="Reativar", exact=True)).to_have_count(0)
    expect(pg.get_by_role("button", name="Novo plano de trabalho", exact=True)).to_have_count(0)
    assert PlanoTrabalho.objects.count() == 21
    # Medir o contraste final, após a cascata global de entrada (base.css).
    # Não desativar animações nem excluir controles/regras do axe.
    pg.evaluate("""async () => await Promise.all(document.getAnimations().filter(a =>
        a.effect?.target?.closest('.conteudo__interno') &&
        a.effect.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})))""")
    violacoes = rodar_axe(pg)
    assert violacoes == [], str(violacoes)
    assert pg.erros_console == []
