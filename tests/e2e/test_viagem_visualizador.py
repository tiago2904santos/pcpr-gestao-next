"""Visualizador da folha da viagem: o cartão abre o documento pronto (ou a janela de resumo
das listas), as setas passam por todos os documentos da viagem e Esc devolve o foco ao
cartão; "Baixar" abre a janela de escolha dos documentos."""

import re

import pytest
from playwright.sync_api import expect

from gestao.viagens import viagem
from gestao.viagens.models import Oficio
from tests.e2e.test_justificativas_identidade import _axe_estavel
from tests.e2e.test_viagens_folha_identidade import _viagem

pytestmark = pytest.mark.e2e


def _proximo(pg, passos: int) -> None:
    """Anda `passos` documentos (negativo volta) pelas setas da janela que estiver aberta."""
    for _ in range(abs(passos)):
        lado = "proximo" if passos > 0 else "anterior"
        pg.locator(f"[data-v-{lado}]:visible, [data-r-{lado}]:visible").click()


@pytest.mark.parametrize("largura", [360, 1440])
def test_setas_passam_por_todos_os_documentos(logado, dados_e2e, largura):
    pg = logado
    v = _viagem(dados_e2e)
    emitido = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])
    rascunho = Oficio.objects.get(pk=dados_e2e.ids["oficio_rascunho"])
    viagem.salvar_dados(dados_e2e.usuarios["operador"], v.pk, tipos=list(v.tipos.all()),
                        vinculos={"oficios": [emitido, rascunho]})
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.goto(f"/viagens/viagens/{v.pk}/")
    itens = pg.locator("a[data-visualizar]")
    hrefs = [itens.nth(i).get_attribute("href") or "" for i in range(itens.count())]
    total = len(hrefs)
    i_emitido = next(i for i, h in enumerate(hrefs) if h.endswith(f"/oficios/{emitido.pk}/editar/"))
    i_rascunho = next(i for i, h in enumerate(hrefs)
                      if h.endswith(f"/oficios/{rascunho.pk}/editar/"))
    # Só o emitido está pronto: abre a folha; o rascunho abre a janela de resumo.
    assert "/documento/oficio/folha/" in (itens.nth(i_emitido).get_attribute("data-paginas") or "")
    assert itens.nth(i_rascunho).get_attribute("data-paginas") is None

    visor, resumo = pg.locator("#dialogo-documento"), pg.locator("#dialogo-resumo")
    itens.nth(i_emitido).click()
    expect(visor).to_be_visible()
    expect(pg.locator("[data-v-posicao]")).to_have_text(f"{i_emitido + 1} de {total}")
    expect(pg.locator(".importador-fita")).to_be_hidden()
    _axe_estavel(pg)
    # Até o rascunho, pelas setas: a janela troca para o resumo de sempre (o das listas).
    _proximo(pg, i_rascunho - i_emitido)
    expect(resumo).to_be_visible()
    expect(visor).to_be_hidden()
    expect(resumo).to_have_class(re.compile(r"\bdialogo--resumo\b.*\bdialogo--mesa\b"))
    expect(pg.locator("#resumo-dialogo #resumo-titulo")).to_be_visible()
    expect(pg.locator("[data-r-posicao]")).to_have_text(f"{i_rascunho + 1} de {total}")
    _axe_estavel(pg)
    # E de volta, pelo teclado.
    for _ in range(abs(i_rascunho - i_emitido)):
        pg.keyboard.press("ArrowLeft" if i_rascunho > i_emitido else "ArrowRight")
    expect(visor).to_be_visible()
    expect(resumo).to_be_hidden()
    # Do primeiro ao último da viagem, sem ficar preso no tipo.
    _proximo(pg, -i_emitido)
    expect(pg.locator("[data-v-anterior]:visible, [data-r-anterior]:visible")).to_be_disabled()
    _proximo(pg, total - 1)
    expect(pg.locator("[data-v-proximo]:visible, [data-r-proximo]:visible")).to_be_disabled()
    pg.keyboard.press("Escape")
    expect(visor).to_be_hidden()
    expect(resumo).to_be_hidden()
    expect(itens.nth(total - 1)).to_be_focused()
    expect(pg.get_by_role("link", name="Importar documentos", exact=True)).to_be_visible()
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert pg.erros_console == []


def test_documento_pronto_abre_a_folha(logado, dados_e2e):
    pg = logado
    v = _viagem(dados_e2e)
    emitido = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])
    viagem.salvar_dados(dados_e2e.usuarios["operador"], v.pk, tipos=list(v.tipos.all()),
                        vinculos={"oficios": [emitido]})
    v.refresh_from_db()
    pg.set_viewport_size({"width": 1440, "height": 900})
    pg.goto(f"/viagens/viagens/{v.pk}/")
    pg.locator('a[data-visualizar][data-grupo="oficio"]').click()
    folha = pg.locator("[data-v-folha]")
    expect(folha).to_be_visible()
    assert f"/oficios/{emitido.pk}/documento/oficio/folha/" in (folha.get_attribute("src") or "")
    assert "final=1" in (folha.get_attribute("src") or "")  # emitido: sem a marca de minuta
    expect(pg.locator("[data-v-anterior]")).to_be_hidden()
    expect(pg.frame_locator("[data-v-folha]").locator("body")).to_contain_text("Ofício")
    # As ações rápidas: imprimir, baixar, baixar todos e editar (anexar assinado aparece
    # quando quem vê pode anexar).
    for acao in ("imprimir", "baixar", "todos", "editar"):
        expect(pg.locator(f"[data-v-{acao}]")).to_be_visible()
    # Baixar: a janela de escolha (quais e como), com as peças do ofício, por cima do documento.
    pg.locator("[data-v-baixar]").click()
    janela = pg.locator("#dialogo-baixar")
    expect(janela).to_be_visible()
    expect(janela.locator("[data-baixar-subtitulo]")).to_have_text(str(emitido))
    expect(janela.locator(".baixar__item").first).to_be_visible()
    janela.get_by_role("button", name="Fechar").click()
    expect(janela).to_be_hidden()
    expect(folha).to_be_visible()
    # Baixar todos: a mesma janela, com os documentos da viagem.
    pg.locator("[data-v-todos]").click()
    expect(janela).to_be_visible()
    expect(janela.locator("[data-baixar-subtitulo]")).to_have_text(str(v))
    assert pg.erros_console == []


def test_solicitacao_anexada_abre_no_visualizador(logado, dados_e2e, tmp_path, settings):
    pg = logado
    v = _viagem(dados_e2e)
    pdf = tmp_path / "oficio-pedido.pdf"
    pdf.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    pg.set_viewport_size({"width": 1440, "height": 900})
    pg.goto(f"/viagens/viagens/{v.pk}/")
    pg.get_by_role("button", name="Anexar e-mail ou ofício").click()
    pg.get_by_label("Ofício de solicitação").check()
    pg.set_input_files("#solicitacao-arquivo", str(pdf))
    pg.locator("#dialogo-solicitacao button[type=submit]").click()
    cartao = pg.locator('a[data-visualizar][data-grupo="solicitacao"]')
    expect(cartao).to_contain_text("oficio-pedido.pdf")
    expect(cartao).to_contain_text("Ofício")
    with pg.expect_response(lambda r: "/viagens/solicitacao/" in r.url) as resposta:
        cartao.click()
    assert resposta.value.status == 200
    assert resposta.value.headers.get("x-frame-options") == "SAMEORIGIN"
    # O arquivo anexado baixa direto (não tem peças para escolher).
    expect(pg.locator("[data-v-baixar-arquivo]")).to_have_attribute("href", re.compile(r"baixar=1"))
    expect(pg.locator("[data-v-baixar]")).to_be_hidden()
    pg.keyboard.press("Escape")
    assert pg.erros_console == []
