"""Envio manual: PDFs, mensagem única, mesma aba, acessibilidade e confirmação."""

import io
import json
import zipfile
from pathlib import Path

import pikepdf
import pytest
from playwright.sync_api import expect

from gestao.automacao.models import Comunicacao
from gestao.viagens.models import PrestacaoServidor
from gestao.viagens.tests.test_envios_manuais import pacote_completo

from .conftest import entrar, estabilizar, rodar_axe

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]
EVIDENCIAS = Path(__file__).resolve().parents[2] / "docs/automacao/evidencias-envios-manuais"


@pytest.mark.parametrize("largura", [360, 1440])
def test_documentos_mensagem_e_confirmacao(pagina, dados_e2e, settings, live_server, largura):
    settings.AUTOMACAO_TRANSPORTE = "manual"
    settings.URL_PUBLICA = live_server.url
    cen = dados_e2e
    cen.ps = PrestacaoServidor.objects.select_related("prestacao__oficio", "servidor").filter(
        prestacao__oficio_id=cen.ids["oficio_emitido"]).first()
    ps = pacote_completo(cen)
    pg = pagina
    pg.set_viewport_size({"width": largura, "height": 900})
    entrar(pg)
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    pg.goto("/viagens/prestacoes/")
    assert pg.locator(f'a[href="/viagens/envios/{ps.pk}/"]').first.get_attribute("target") == "_self"
    # A barra fixa da paginação cobre a linha que estiver embaixo dela; no fim da lista ela
    # volta ao lugar dela e o alvo de toque (WCAG 2.5.8) mede só a página.
    pg.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    estabilizar(pg)
    assert not rodar_axe(pg)
    pg.screenshot(path=str(EVIDENCIAS / f"prestacoes-{largura}.png"), full_page=True)
    pg.goto("/viagens/envios/")
    expect(pg.get_by_role("heading", name="Envios manuais", exact=True)).to_be_visible()
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    problemas = {}
    estabilizar(pg)
    problemas["lista"] = rodar_axe(pg)
    pg.screenshot(path=str(EVIDENCIAS / f"lista-{largura}.png"), full_page=True)
    pg.goto(f"/viagens/envios/{ps.pk}/")
    pg.get_by_role("button", name="Preparar mensagem completa").click()
    expect(pg.locator("#texto-envio")).to_contain_text("Ofício: segue anexo")
    expect(pg.locator("#texto-envio")).to_contain_text("Relatório técnico (RT): segue anexo")
    texto = pg.locator("#texto-envio").input_value()
    assert texto.count("http") == 1  # apenas o link pessoal de KM
    com = Comunicacao.objects.get(contexto__ps=ps.pk, contexto__manual=True,
                                   situacao="aguardando_aprovacao")
    with pg.expect_download() as download:
        pg.get_by_role("link", name="Baixar PDFs separados (ZIP)").click()
    with zipfile.ZipFile(download.value.path()) as arquivos:
        assert arquivos.namelist() == ["oficio.pdf", "relatorio-tecnico.pdf"]
        assert all(arquivos.read(nome).startswith(b"%PDF") for nome in arquivos.namelist())
    with pg.expect_download() as download:
        pg.get_by_role("link", name="Baixar PDF único").click()
    with pikepdf.open(io.BytesIO(Path(download.value.path()).read_bytes())) as pdf:
        assert len(pdf.pages) >= 2
    pg.context.grant_permissions(["clipboard-read", "clipboard-write"])
    pg.get_by_role("button", name="Copiar mensagem").click()
    expect(pg.get_by_role("button", name="Copiado", exact=True)).to_be_visible()
    assert pg.evaluate("navigator.clipboard.readText()").replace("\r\n", "\n") == texto
    estabilizar(pg)
    pg.evaluate("window.scrollTo(0, 0)")
    estabilizar(pg)
    problemas["conferencia"] = rodar_axe(pg)
    pg.screenshot(path=str(EVIDENCIAS / f"conferencia-{largura}.png"), full_page=True)
    assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth")
    # Não acessa o WhatsApp real: o destino é uma página de teste e nenhuma mensagem sai.
    pg.context.route("https://wa.me/**", lambda rota: rota.fulfill(
        content_type="text/html", body="<h1>Conversa de teste</h1>"))
    quantidade = len(pg.context.pages)
    pg.get_by_role("link", name="Abrir conversa nesta aba").click()
    expect(pg.get_by_role("heading", name="Conversa de teste")).to_be_visible()
    assert len(pg.context.pages) == quantidade == 1
    assert pg.url.startswith("https://wa.me/5541999997771?")
    pg.go_back()
    expect(pg.get_by_role("button", name="Confirmar envio manual")).to_be_visible()
    com.refresh_from_db()
    assert com.situacao == "aguardando_aprovacao"
    pg.get_by_label("Enviei a mensagem e anexei os PDFs disponíveis").check()
    pg.get_by_role("button", name="Confirmar envio manual").click()
    com.refresh_from_db()
    assert com.situacao == "manual"
    pg.goto("/viagens/envios/?aba=historico")
    expect(pg.locator("main")).to_contain_text("Confirmado por")
    estabilizar(pg)
    problemas["historico"] = rodar_axe(pg)
    pg.screenshot(path=str(EVIDENCIAS / f"historico-{largura}.png"), full_page=True)
    (EVIDENCIAS / f"axe-{largura}.json").write_text(
        json.dumps(problemas, ensure_ascii=False, indent=2), encoding="utf-8")
    assert not any(problemas.values()), problemas
