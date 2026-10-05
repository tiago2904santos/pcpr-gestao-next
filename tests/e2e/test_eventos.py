"""E2E: catálogos de Eventos Sociais — incluir, inativar e o modelo do tipo de evento; e
a escala e a pauta da agenda (A2b) abrem sem rolagem horizontal."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _admin() -> None:
    from django.contrib.auth.models import Group

    from gestao.identidade.models import Usuario

    Usuario.objects.get(login="operador").groups.add(Group.objects.get(name="ADMINISTRADOR"))


def test_catalogo_e_modelo_do_tipo(logado, dados_e2e):
    from gestao.eventos.models import Servico, TipoEvento, UnidadeMovel

    _admin()
    # O banco do navegador é limpo a cada teste: a carga inicial não está lá.
    tipo = TipoEvento.objects.create(nome="Palestra")
    Servico.objects.create(nome="Emissão de CIN")
    pg = logado
    pg.goto("/eventos/cadastros/")
    pg.goto("/eventos/cadastros/unidades-moveis/")
    pg.locator("#novo-nome").fill("Caminhão (e2e)")
    pg.get_by_role("button", name="Incluir").click()
    expect(pg.locator(".registros")).to_contain_text("Caminhão (e2e)")
    pg.get_by_role("button", name="Inativar Caminhão (e2e)").click()
    expect(pg.locator(".registros")).to_contain_text("Inativo")
    assert not UnidadeMovel.objects.get(nome="Caminhão (e2e)").ativo
    pg.goto(f"/eventos/cadastros/tipos-evento/{tipo.pk}/modelo/")
    pg.locator("#solicitante").fill("Escola (e2e)")
    pg.get_by_label("Emissão de CIN").check()
    pg.get_by_role("button", name="Salvar modelo").click()
    expect(pg.get_by_role("status").first).to_be_attached()
    tipo.refresh_from_db()
    assert tipo.solicitante_padrao == "Escola (e2e)" and tipo.servicos_sugeridos.count() == 1
    assert not pg.erros_console  # type: ignore[attr-defined]


@pytest.mark.parametrize("largura", [360, 1440])
def test_sem_rolagem_horizontal(logado, dados_e2e, largura):
    _admin()
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    for rota in ("/eventos/cadastros/", "/eventos/cadastros/servicos/", "/agenda/escala/",
                 "/agenda/?vista=semana"):
        pg.goto(rota)
        excesso = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert excesso <= 0, f"{rota} @ {largura}px: rolagem horizontal de {excesso}px"
