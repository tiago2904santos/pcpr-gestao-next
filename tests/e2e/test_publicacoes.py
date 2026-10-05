"""E2E: publicações — registrar a pauta com unidade nova, a folha se grava sozinha, o
andamento publica (data do registro) e vai para o histórico, a lista filtra pela fila."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _dar_papel(papel: str = "ASCOM_PUBLICACOES") -> None:
    from django.contrib.auth.models import Group

    from gestao.identidade.models import Usuario

    Usuario.objects.get(login="operador").groups.add(Group.objects.get(name=papel))


def test_registrar_gravar_sozinho_e_publicar(logado, dados_e2e):
    from gestao.publicacoes.models import Integrante, Publicacao

    _dar_papel()
    Integrante.objects.create(nome="Gabriela")
    pg = logado
    pg.goto("/publicacoes/")
    pg.get_by_role("link", name="Nova pauta").first.click()
    pg.locator("#id_titulo").fill("Prisão em flagrante (e2e)")
    pg.get_by_role("combobox", name="Jornalista").click()
    pg.get_by_role("option", name="Gabriela").click()
    pg.get_by_label("Outra unidade (não listada)").fill("DP de Irati (e2e)")
    pg.get_by_role("button", name="Registrar pauta").click()
    expect(pg).to_have_url(re.compile(r"/publicacoes/pautas/\d+/$"))
    p = Publicacao.objects.get()
    assert p.unidade and p.unidade.nome == "DP de Irati (e2e)"

    pg.locator("#id_link_site").fill("https://example.invalid/noticia")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text(re.compile("Salvo"),
                                                                    timeout=10000)
    p.refresh_from_db()
    assert p.link_site == "https://example.invalid/noticia"

    pg.locator("label.opcao", has_text="Publicada").click()
    pg.locator("#id_anotacao").fill("No ar (e2e)")
    pg.get_by_role("button", name="Registrar andamento").last.click()
    expect(pg.locator("#frase-pauta")).to_contain_text("Publicada em")
    expect(pg.locator("#historico")).to_contain_text("No ar (e2e)")

    pg.goto("/publicacoes/pautas/?fila=publicadas")
    expect(pg.locator(".registro__link", has_text="Prisão em flagrante (e2e)")).to_be_visible()
    assert not pg.erros_console  # type: ignore[attr-defined]


@pytest.mark.parametrize("largura", [360, 1440])
def test_telas_sem_rolagem_horizontal(logado, dados_e2e, largura):
    from django.utils import timezone

    from gestao.identidade.models import Usuario
    from gestao.publicacoes import services
    from gestao.publicacoes.models import Integrante, UnidadeResponsavel

    _dar_papel()
    _dar_papel("ADMINISTRADOR")
    u = Usuario.objects.get(login="operador")
    p = services.criar(u, {"data": timezone.localdate(), "titulo": "Título bem comprido de "
                           "uma pauta para testar a quebra da linha (e2e) " * 2,
                           "jornalista": Integrante.objects.create(nome="Gabriela"),
                           "unidade": UnidadeResponsavel.objects.create(nome="DP (e2e)")})
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    for rota in ("/publicacoes/", "/publicacoes/pautas/", f"/publicacoes/pautas/{p.pk}/",
                 "/publicacoes/pautas/nova/", "/publicacoes/cadastros/unidades/"):
        pg.goto(rota)
        excesso = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert excesso <= 0, f"{rota} @ {largura}px: rolagem horizontal de {excesso}px"
