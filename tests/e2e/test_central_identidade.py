"""Central: todos os acessos autorizados, menus por teclado e consumidores do painel."""
from collections import Counter
from pathlib import Path

import pytest
from django.contrib.auth.models import Group
from django.test import RequestFactory
from playwright.sync_api import expect

from gestao.identidade.models import Usuario
from gestao.plataforma.navegacao import navegacao_para

from .conftest import SENHA, entrar
from .test_justificativas_identidade import _axe_estavel

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("perfil", ["operador", "consulta", "admin", "ascom"])
@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_central_preserva_acessos_e_menus(pagina, dados_e2e, perfil, largura):
    if perfil in ("admin", "ascom"):
        usuario = Usuario.objects.create_user(perfil, f"{perfil}@pc.pr.gov.br", SENHA, nome=perfil)
        usuario.groups.add(Group.objects.get(name="ADMINISTRADOR" if perfil == "admin" else "ASCOM_IMPRENSA"))
    else:
        usuario = dados_e2e.usuarios[perfil]
    request = RequestFactory().get("/")
    request.user = usuario
    modulos = navegacao_para(request)["modulos"]
    pg = pagina
    entrar(pg, perfil)
    pg.set_viewport_size({"width": largura, "height": 800})
    pg.goto("/")
    expect(pg.get_by_role("heading", level=1)).to_have_text("Central de módulos")
    expect(pg.locator(".modulo")).to_have_count(len(modulos))
    for modulo in modulos:
        secao = pg.locator(f'[aria-labelledby="mod-{modulo["chave"]}"]')
        esperado = [modulo["url"], *[i["url"] for g in modulo["grupos"]
                                    for i in g["itens"] if i["url"] != modulo["url"]]]
        encontrado = secao.locator("a").evaluate_all("els=>els.map(e=>e.getAttribute('href'))")
        assert Counter(encontrado) == Counter(esperado)
    _axe_estavel(pg)
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")
    out = Path("artifacts/central")
    out.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(out / f"{perfil}-lista-{largura}.png"), full_page=True)
    menus = pg.locator(".modulo [data-menu-botao]")
    for i in range(menus.count()):
        botao = menus.nth(i)
        botao.focus()
        botao.press("Enter")
        painel = pg.locator(".modulo .menu__painel:visible")
        expect(painel).to_be_visible()
        if i == 0:
            _axe_estavel(pg)
        pg.screenshot(path=str(out / f"{perfil}-menu{i}-{largura}.png"))
        pg.keyboard.press("Escape")
        expect(botao).to_be_focused()
    assert pg.erros_console == []  # type: ignore[attr-defined]
    pg.locator(".modulo .botao--primario").first.click()
    expect(pg.get_by_role("heading", level=1)).to_be_visible()


@pytest.mark.parametrize("rota", ["/eventos/", "/eventos/cadastros/"])
@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_consumidores_de_metricas_e_acessos(pagina, dados_e2e, rota, largura):
    usuario = Usuario.objects.create_user("admin", "admin@pc.pr.gov.br", SENHA, nome="Administrador")
    usuario.groups.add(Group.objects.get(name="ADMINISTRADOR"))
    pg = pagina
    entrar(pg, "admin")
    pg.set_viewport_size({"width": largura, "height": 800})
    response = pg.goto(rota)
    assert response.status == 200
    _axe_estavel(pg)
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")
    assert pg.erros_console == []  # type: ignore[attr-defined]
    out = Path("artifacts/central")
    out.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(out / f"compat-{rota.strip('/').replace('/', '-')}-{largura}.png"), full_page=True)
