"""Lista/diálogo de Justificativas: contexto, gravação, ações e leitura reais."""

import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.viagens import services
from gestao.viagens.models import Oficio
from tests.e2e.conftest import entrar, rodar_axe

pytestmark = pytest.mark.e2e


def _axe_estavel(pg):
    # A URL muda no commit da navegação, antes de o CSS registrar animações.
    pg.wait_for_load_state("load")
    # Transição nativa entre documentos desenha snapshots após load. O axe
    # precisa da composição final, não do snapshot parcialmente transparente.
    pg.evaluate("""async () => {
        const limite = performance.now() + 5000;
        while (document.documentElement.matches(':active-view-transition')) {
            if (performance.now() > limite) throw new Error('Transição de navegação não terminou');
            await new Promise(requestAnimationFrame);
        }
    }""")
    # O cronômetro do toast pausa sob hover/foco por acessibilidade; não é
    # animação de entrada nem pode ser aguardado até sumir para medir contraste.
    pg.evaluate("""async () => await Promise.all(document.getAnimations().filter(a =>
        a.animationName !== 'toast-tempo' &&
        a.effect.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})))""")
    violacoes = rodar_axe(pg)
    assert violacoes == [], str(violacoes)


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_busca_erro_cancelar_gravar_e_excluir(logado, dados_e2e, largura):
    pg = logado
    oficio = Oficio.objects.get(pk=dados_e2e.ids["oficio_rascunho"])
    pg.set_viewport_size({"width": largura, "height": 500})
    pg.goto("/viagens/justificativas/?aba=todas")
    busca = pg.get_by_role("searchbox", name="Buscar")
    busca.fill(oficio.numero_formatado)
    expect(pg).to_have_url(re.compile("q=" + oficio.numero_formatado.replace("/", "%2F")))
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    expect(pg.locator("#abas-filtro a[aria-current]")).to_contain_text("Todas")
    expect(busca).to_be_focused()
    acoes = pg.get_by_role("button", name=f"Ações da justificativa do Ofício {oficio.numero_formatado}")
    acoes.press("Enter")
    expect(pg.get_by_role("menuitem", name="Escrever justificativa")).to_be_focused()
    pg.keyboard.press("Escape")
    expect(acoes).to_be_focused()
    pg.locator(".registro__link").click()
    janela = pg.get_by_role("dialog", name=f"Justificativa do Ofício {oficio.numero_formatado}")
    expect(janela).to_be_visible()
    with pg.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/salvar/")) as erro:
        janela.get_by_role("button", name="Gravar no ofício").click()
    assert erro.value.status == 422
    expect(janela.locator(".campo__erro")).to_contain_text("Escreva a justificativa")
    janela.get_by_role("link", name="Cancelar", exact=True).click()
    expect(pg).to_have_url(re.compile(r"/viagens/justificativas/\?.*aba=todas"))
    expect(pg.get_by_role("searchbox", name="Buscar")).to_have_value(oficio.numero_formatado)
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    pg.locator(".registro__link").click()
    texto = "Convocação institucional recebida após o prazo."
    janela.get_by_label("Justificativa", exact=True).fill(texto)
    oficio.refresh_from_db()
    assert oficio.justificativa == ""  # Gravação manual, sem autosave.
    _axe_estavel(pg)
    with pg.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/salvar/")) as salvo:
        janela.get_by_role("button", name="Gravar no ofício").click()
    assert salvo.value.status == 302
    expect(pg.locator(".registro__texto")).to_contain_text(texto)
    oficio.refresh_from_db()
    assert oficio.justificativa == texto
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert pg.locator(".barra-acoes--colecao").evaluate("e => getComputedStyle(e).position") == "static"
    _axe_estavel(pg)
    acoes.click()
    pg.get_by_role("menuitem", name="Apagar justificativa").click()
    confirmacao = pg.get_by_role("dialog", name="Apagar justificativa?")
    expect(confirmacao).to_be_visible()
    with pg.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/salvar/")) as apagado:
        confirmacao.get_by_role("button", name="Apagar", exact=True).click()
    assert apagado.value.status == 302
    expect(pg.locator(".registro__selos")).to_contain_text("Pendente")
    oficio.refresh_from_db()
    assert oficio.justificativa == ""
    assert pg.erros_console == ["Failed to load resource: the server responded with a status of 422 (Unprocessable Content)"]
    pg.goto("/viagens/oficios/")
    pg.wait_for_load_state("networkidle")


def test_download_pdf_e_escape_devolve_foco(logado, dados_e2e):
    pg = logado
    oficio = Oficio.objects.get(pk=dados_e2e.ids["oficio_rascunho"])
    services.salvar_dados(oficio, dados_e2e.usuarios["operador"], {"justificativa": "Convite sintético."})
    pg.goto(f"/viagens/justificativas/?aba=preenchidas&q={oficio.numero_formatado}")
    menu = pg.get_by_role("button", name=f"Ações da justificativa do Ofício {oficio.numero_formatado}")
    menu.click()
    pg.get_by_role("menuitem", name="Baixar documentos").click()
    janela = pg.get_by_role("dialog", name="Baixar documentos")
    expect(janela).to_be_visible()
    expect(janela.locator("input[name=itens]")).to_have_count(2)
    assert janela.locator("input[name=itens]").evaluate_all("es => es.map(e => e.value)") == ["justificativa", "oficio"]
    janela.get_by_role("button", name="Desmarcar todos").click()
    janela.locator("input[name=itens]").first.check()
    with pg.expect_download() as baixado:
        janela.get_by_role("button", name="Baixar", exact=True).click()
    pasta = Path("artifacts/justificativas-identidade")
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / baixado.value.suggested_filename
    baixado.value.save_as(arquivo)
    assert arquivo.read_bytes().startswith(b"%PDF")
    expect(janela).to_be_hidden()
    menu.click()
    pg.get_by_role("menuitem", name="Baixar documentos").click()
    expect(janela).to_be_visible()
    pg.keyboard.press("Escape")
    expect(janela).to_be_hidden()
    expect(menu).to_be_focused()
    assert pg.erros_console == []
    pg.goto("/viagens/oficios/")
    pg.wait_for_load_state("networkidle")


def test_conflito_preserva_texto_e_consulta_sem_edicao(logado, dados_e2e):
    pg = logado
    oficio = Oficio.objects.get(pk=dados_e2e.ids["oficio_rascunho"])
    pg.goto(f"/viagens/justificativas/?editar={oficio.pk}")
    janela = pg.get_by_role("dialog", name=f"Justificativa do Ofício {oficio.numero_formatado}")
    janela.get_by_label("Justificativa", exact=True).fill("Texto desta janela.")
    services.salvar_dados(oficio, dados_e2e.usuarios["operador"], {"justificativa": "Alteração concorrente."})
    with pg.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/salvar/")) as conflito:
        janela.get_by_role("button", name="Gravar no ofício").click()
    assert conflito.value.status == 422
    expect(janela.get_by_role("alert")).to_contain_text("Outra pessoa salvou")
    expect(janela.get_by_label("Justificativa", exact=True)).to_have_value("Texto desta janela.")
    oficio.refresh_from_db()
    assert oficio.justificativa == "Alteração concorrente."
    janela.get_by_role("link", name="Cancelar", exact=True).click()
    pg.context.clear_cookies()
    entrar(pg, "consulta")
    pg.goto(f"/viagens/justificativas/?aba=preenchidas&q={oficio.numero_formatado}")
    expect(pg.locator(".registro__link--estatico")).to_have_count(1)
    expect(pg.locator(".registro__link--estatico")).to_contain_text("Ofício")
    expect(pg.get_by_role("menuitem", name="Editar justificativa")).to_have_count(0)
    _axe_estavel(pg)


def test_paginacao_filtrada_apos_erro(logado, dados_e2e, monkeypatch):
    from gestao.viagens import views

    monkeypatch.setattr(views, "POR_PAGINA", 1)
    for chave in ["oficio_rascunho", "oficio_vazio"]:
        oficio = Oficio.objects.get(pk=dados_e2e.ids[chave])
        services.salvar_dados(oficio, dados_e2e.usuarios["operador"], {
            "justificativa": "Contexto sintético de paginação.",
        })
    pg = logado
    pg.goto("/viagens/justificativas/?aba=todas&q=Contexto+sint%C3%A9tico")
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    pg.locator(".registro__link").click()
    janela = pg.get_by_role("dialog", name=re.compile("Justificativa do Ofício"))
    janela.get_by_label("Justificativa", exact=True).fill("")
    with pg.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/salvar/")) as erro:
        janela.get_by_role("button", name="Gravar no ofício").click()
    assert erro.value.status == 422
    proxima = pg.get_by_role("link", name="Próxima página", exact=True)
    assert proxima.get_attribute("href").startswith("/viagens/justificativas/?")
    janela.get_by_role("link", name="Cancelar", exact=True).click()
    proxima.click()
    expect(pg).to_have_url(re.compile("pagina=2"))
    expect(pg.get_by_role("searchbox", name="Buscar")).to_have_value("Contexto sintético")
    expect(pg.locator("#abas-filtro a[aria-current]")).to_contain_text("Todas")
    expect(pg.locator(".registro-operacional")).to_have_count(1)
    barra = pg.locator(".barra-acoes--colecao")
    assert barra.evaluate("e => getComputedStyle(e).position") == "static"
    assert barra.evaluate("""e => {
        const barra = e.getBoundingClientRect();
        return [...document.querySelectorAll('.registro-operacional')].every(registro =>
            registro.getBoundingClientRect().bottom <= barra.top);
    }""")
    _axe_estavel(pg)
    assert pg.erros_console == ["Failed to load resource: the server responded with a status of 422 (Unprocessable Content)"]
