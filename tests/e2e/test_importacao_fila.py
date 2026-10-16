"""Envio real, revisão e downloads concorrentes no navegador (dados sintéticos)."""

import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.plataforma import outbox
from gestao.viagens import importacao, termos
from gestao.viagens.models import ArquivoImportado, Oficio
from tests.e2e.test_justificativas_identidade import _axe_estavel

pytestmark = pytest.mark.e2e


def captura(pg, nome, largura):
    if os.environ.get("IMPORTACAO_CAPTURAS"):
        destino = Path(os.environ["IMPORTACAO_CAPTURAS"])
        destino.mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(destino / f"{nome}-{largura}.png"), full_page=True)


@pytest.mark.parametrize("largura", [360, 1440])
def test_lote_revisao_e_documento_privado(logado, dados_e2e, largura):
    while outbox.processar_lote():
        pass
    pg = logado
    pg.on("console", lambda m: print(m.type, m.text) if m.type in {"warning", "error"} else None)
    pg.set_viewport_size({"width": largura, "height": 900})
    oficio = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])
    pg.goto("/viagens/oficios/")
    fita = pg.get_by_role("link", name="Importar documentos", exact=True).bounding_box()
    assert fita["x"] >= largura - 50 and fita["height"] < 180
    pg.get_by_role("link", name="Importar documentos", exact=True).click()
    janela = pg.get_by_role("dialog", name="Importar documentos")
    expect(janela).to_be_visible()
    _axe_estavel(pg)
    captura(pg, "envio", largura)
    janela.get_by_label("Arquivos para importar").set_input_files([
        {"name": "despacho.txt", "mimeType": "text/plain", "buffer": (
            f"DESPACHO\nOfício {oficio.numero_formatado}\n"
            "Encaminho para providências administrativas cabíveis.").encode()},
        {"name": "conferir.txt", "mimeType": "text/plain", "buffer": (
            "Uma carta sem título identificável que precisa de conferência do destino.").encode()},
    ])
    janela.get_by_role("button", name="Enviar arquivos", exact=True).click()
    expect(janela.locator("[data-importar-aviso]")).to_contain_text("2 de 2", timeout=30_000)
    expect(janela.get_by_role("button", name="Enviar arquivos", exact=True)).to_be_enabled()
    expect(janela.get_by_role("button", name="Enviar arquivos", exact=True)).not_to_have_attribute("aria-busy", "true")
    arquivos = list(ArquivoImportado.objects.all())
    assert len(arquivos) == 2
    for a in arquivos:
        importacao.processar(a.pk)
    assert ArquivoImportado.objects.filter(estado="concluido").count() == 1
    expect(janela.get_by_role("link", name="Revisar documento")).to_have_count(1, timeout=20_000)
    _axe_estavel(pg)
    captura(pg, "resultado", largura)
    janela.get_by_role("link", name="Revisar documento").click()
    expect(pg.get_by_role("heading", name="Confira o destino", level=1)).to_be_visible()
    leitor = pg.get_by_role("region", name="Documento para revisão")
    expect(leitor).to_have_attribute("data-pdf-pronto", "true", timeout=30_000)
    expect(leitor.locator("[data-pdf-texto]")).to_contain_text("conferência do destino")
    pg.get_by_role("button", name="200%", exact=True).click()
    expect(leitor).to_have_attribute("data-pdf-zoom", "200")
    captura(pg, "revisao-ampliada", largura)
    pg.get_by_role("button", name="Ajustar à largura", exact=True).click()
    expect(leitor).to_have_attribute("data-pdf-zoom", "100")
    assert "arquivo/" in pg.get_by_role("link", name="Abrir ampliado").get_attribute("href")
    _axe_estavel(pg)
    captura(pg, "revisao", largura)
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    pg.get_by_label("Tipo de documento").select_option("despacho")
    pg.get_by_label("Buscar por número ou nome").fill(oficio.numero_formatado)
    pg.get_by_label("Documento que recebe o arquivo").select_option(f"despacho:{oficio.pk}:")
    pg.get_by_role("button", name="Anexar ao destino").click()
    expect(pg.get_by_role("heading", name="Importação de documentos", level=1)).to_be_visible()
    assert all(a.partes.exclude(estado__in=["anexado", "repetido"]).count() == 0 for a in arquivos)
    _axe_estavel(pg)
    captura(pg, "historico", largura)
    assert pg.erros_console == []


@pytest.mark.parametrize("largura", [360, 1440])
def test_downloads_separados_reais_sem_zip(logado, dados_e2e, largura):
    pg = logado
    pg.add_init_script("""(() => {
      const original = window.fetch;
      window.filaMedicao = {ativos: 0, maximo: 0, falhaSimulada: false};
      window.fetch = async (...args) => {
        const dados = args[1]?.body;
        const individual = dados instanceof FormData && dados.getAll('itens').length === 1;
        if (!individual) return original(...args);
        window.filaMedicao.ativos++;
        window.filaMedicao.maximo = Math.max(window.filaMedicao.maximo, window.filaMedicao.ativos);
        try {
          await new Promise(r => setTimeout(r, 400));
          if (!window.filaMedicao.falhaSimulada) {
            window.filaMedicao.falhaSimulada = true;
            return new Response(JSON.stringify({erro: 'Falha transitória de teste. Tente novamente.'}),
              {status: 422, headers: {'Content-Type': 'application/json'}});
          }
          return await original(...args);
        }
        finally { window.filaMedicao.ativos--; }
      };
    })();""")
    pg.set_viewport_size({"width": largura, "height": 900})
    termo = termos.salvar(dados_e2e.usuarios["operador"],
                          oficio=Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"]))
    pg.goto(f"/viagens/termos/{termo.pk}/")
    acoes = pg.locator(".registro-hero__acoes")
    acoes.locator("[data-menu-botao]").click()
    acoes.get_by_role("menuitem", name="Baixar documentos", exact=True).click()
    dialogo = pg.get_by_role("dialog", name="Baixar documentos")
    expect(dialogo.locator("input[name=itens]").first).to_be_checked()
    total = dialogo.locator("input[name=itens]").count()
    dialogo.locator("label[for=baixar-separados]").click()
    downloads = []
    pg.on("download", lambda arquivo: downloads.append(arquivo))
    dialogo.get_by_role("button", name="Baixar", exact=True).click()
    fila = pg.get_by_role("dialog", name="Downloads", exact=True)
    expect(fila).to_be_visible()
    expect(fila.locator("[data-fila-status]")).to_contain_text(
        f"{total - 1} de {total} enviados ao navegador", timeout=90_000)
    expect(fila).to_contain_text("Falha transitória de teste. Tente novamente.")
    fila.get_by_role("button", name="Tentar novamente", exact=True).click()
    expect(fila.locator("[data-fila-status]")).to_contain_text(
        f"{total} de {total} enviados ao navegador", timeout=90_000)
    assert len(downloads) == total
    for d in downloads:
        assert d.suggested_filename.endswith(".pdf") and d.failure() is None
    assert pg.evaluate("window.filaMedicao.maximo") == min(total, 3)
    _axe_estavel(pg)
    captura(pg, "downloads", largura)
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert pg.erros_console == []
