"""Oito catálogos: cadastro/erro/edição, teclado e composição responsiva."""
from pathlib import Path
from urllib.parse import quote

import pytest
from playwright.sync_api import expect

from .conftest import entrar
from .test_justificativas_identidade import _axe_estavel

pytestmark = pytest.mark.e2e
CATALOGOS = ["unidades", "cargos", "combustiveis", "tipos-de-viagem",
             "programas", "horarios", "atividades", "conjuntos"]


@pytest.mark.parametrize("slug", CATALOGOS)
@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_catalogo_cadastro_edicao_e_erro(logado, slug, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 800})
    pg.goto(f"/cadastros/{slug}/")
    abrir = pg.locator('[data-abrir-dialogo="dialogo-cadastro"]').first
    abrir.focus()
    abrir.press("Enter")
    janela = pg.locator("#dialogo-cadastro")
    expect(janela).to_be_visible()
    pg.keyboard.press("Escape")
    expect(abrir).to_be_focused()
    abrir.press("Enter")
    janela.locator('button[type="submit"]').click()
    expect(janela.locator(".campo__erro").first).to_be_visible()
    assert not janela.evaluate("e=>e.scrollWidth>e.clientWidth")
    _axe_estavel(pg)
    out = Path("artifacts/catalogos")
    out.mkdir(parents=True, exist_ok=True)
    janela.screenshot(path=str(out / f"{slug}-erro-{largura}.png"))
    nome = "Catálogo Visual de Atendimento Institucional"
    if slug in ("programas", "conjuntos"):
        nome = nome.upper()
    if slug == "horarios":
        janela.locator('input[name="inicio"]').fill("07:15")
        janela.locator('input[name="fim"]').fill("13:45")
        nome = "07:15 até 13:45"
    else:
        janela.locator('input[name="nome"]').fill(nome)
    if slug == "unidades":
        janela.get_by_label("Sigla", exact=True).fill("VISUAL")
    if slug == "atividades":
        janela.locator('[name="meta"]').fill("Atender ao público com informação clara.")
    if slug == "conjuntos":
        janela.locator('input[name="atividades"]').first.check()
    janela.locator('button[type="submit"]').click()
    registro = pg.locator(".registro").filter(has=pg.get_by_role("link", name=nome, exact=True))
    expect(registro).to_be_visible()
    registro.locator("[data-menu-botao]").click()
    expect(pg.get_by_role("menuitem", name="Editar", exact=True)).to_be_visible()
    pg.keyboard.press("Escape")
    expect(registro.locator("[data-menu-botao]")).to_be_focused()
    registro.get_by_role("link", name=nome, exact=True).click()
    expect(janela).to_be_visible()
    if slug == "horarios":
        expect(janela.locator('[name="inicio"]')).to_have_value("07:15")
        expect(janela.locator('[name="fim"]')).to_have_value("13:45")
    else:
        expect(janela.locator('[name="nome"]')).to_have_value(nome)
    if slug == "conjuntos":
        expect(janela.locator('input[name="atividades"]:checked')).to_have_count(1)
    if slug == "atividades":
        expect(janela).to_contain_text("não muda com o nome")
    janela.get_by_role("button", name="Salvar alterações").click()
    expect(registro).to_be_visible()
    _axe_estavel(pg)
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")
    pg.screenshot(path=str(out / f"{slug}-salvo-{largura}.png"), full_page=True)
    pg.get_by_role("searchbox", name="Buscar", exact=True).fill(nome)
    pg.get_by_role("button", name="Buscar", exact=True).click()
    expect(pg.locator(".registro")).to_have_count(1)
    registro.locator("[data-menu-botao]").click()
    pg.get_by_role("menuitem", name="Desativar", exact=True).click()
    expect(pg.get_by_role("heading", name="Nenhum registro encontrado")).to_be_visible()
    pg.goto(f"/cadastros/{slug}/?aba=inativos&q={quote(nome)}")
    expect(registro).to_be_visible()
    registro.locator("[data-menu-botao]").click()
    pg.get_by_role("menuitem", name="Reativar", exact=True).click()
    expect(pg.get_by_role("heading", name="Nenhum registro encontrado")).to_be_visible()


@pytest.mark.parametrize("slug", CATALOGOS)
def test_catalogo_vazio_paginado_e_leitura(pagina, dados_e2e, slug):
    from django.contrib.auth.models import Permission

    from gestao.cadastros.views_crud import CATALOGOS as CONFIGURACOES

    cat = CONFIGURACOES["tipos" if slug == "tipos-de-viagem" else slug]
    # Somente banco descartável do teste; preserva registros/vínculos e evita delete.
    if cat.com_padrao:
        cat.modelo.objects.update(padrao=False)
    cat.modelo.objects.update(ativo=False)
    pg = pagina
    entrar(pg)
    pg.set_viewport_size({"width": 360, "height": 800})
    pg.goto(f"/cadastros/{slug}/")
    expect(pg.get_by_role("heading", name="Nada cadastrado")).to_be_visible()
    _axe_estavel(pg)
    out = Path("artifacts/catalogos")
    out.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(out / f"{slug}-vazio-360.png"), full_page=True)
    cat.modelo.objects.update(ativo=True)
    for i in range(28):
        dados = {"nome": f"Registro Visual {i:02d}"}
        if slug == "horarios":
            dados["nome"] = f"06:{i:02d} até 19:{i:02d}"
        elif slug == "atividades":
            dados.update(codigo=f"VISUAL_{i}", meta="Atender o público.")
        objeto = cat.modelo.objects.create(**dados)
        if slug == "conjuntos":
            from gestao.cadastros.models import AtividadePlano

            objeto.atividades.add(AtividadePlano.objects.first())
    termo = "06:" if slug == "horarios" else "Registro Visual"
    pg.goto(f"/cadastros/{slug}/?q={quote(termo)}")
    expect(pg.locator(".registro")).to_have_count(cat.por_pagina)
    pg.get_by_role("link", name="Próxima página", exact=True).click()
    expect(pg.locator(".registro")).to_have_count(28 - cat.por_pagina)
    expect(pg.get_by_role("searchbox", name="Buscar", exact=True)).to_have_value(termo)
    _axe_estavel(pg)
    pg.screenshot(path=str(out / f"{slug}-paginado-360.png"), full_page=True)
    # Consulta sem mutação em todos os catálogos, inclusive os que o perfil
    # CONSULTA não recebe por padrão: permissão individual de leitura, nada mais.
    consulta = dados_e2e.usuarios["consulta"]
    consulta.user_permissions.add(Permission.objects.get(
        content_type__app_label="cadastros", codename=f"view_{cat.modelo._meta.model_name}"))
    pg.context.clear_cookies()
    entrar(pg, "consulta")
    pg.goto(f"/cadastros/{slug}/")
    expect(pg.locator('[data-abrir-dialogo="dialogo-cadastro"]')).to_have_count(0)
    expect(pg.locator('.registro [data-menu-botao]')).to_have_count(0)
    expect(pg.locator('#dialogo-cadastro')).to_have_count(0)
    _axe_estavel(pg)
    pg.screenshot(path=str(out / f"{slug}-consulta-360.png"), full_page=True)
