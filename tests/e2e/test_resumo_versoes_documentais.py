"""RS-02 real: transição worker→polling, foco/cópia e fechamento do resumo.

Arquivos/estados são sintéticos no LAB do pytest. Não usa mock de XMLHttpRequest.
"""

import re
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import expect

from gestao.viagens import services
from gestao.viagens.models import Documento, Oficio, ViaAssinada

from .conftest import rodar_axe

pytestmark = pytest.mark.e2e


def _versoes(cenario, *, historico_gerando=False):
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
    anterior = oficio.documentos.get(tipo="oficio", versao=1)
    Documento.objects.filter(pk=anterior.pk).update(
        situacao="gerando" if historico_gerando else "pronto",
        sha256="a" * 64, arquivo="documentos/rs02-v1.pdf")
    dados = deepcopy(anterior.dados)
    dados["motivo"] = "Motivo exclusivo da emissão v2 para copiar."
    atual = Documento.objects.create(
        oficio=oficio, tipo="oficio", versao=2,
        situacao="pronto" if historico_gerando else "gerando", dados=dados,
        sha256="b" * 64 if historico_gerando else "", arquivo="documentos/rs02-v2.pdf",
        emitido_por=cenario.usuarios["operador"])
    return oficio, anterior, atual


def _abrir(pg, oficio):
    pg.goto(f"/viagens/oficios/?q={oficio.numero_formatado}&escopo=numero")
    origem = pg.locator(".registro__link").first
    origem.click()
    janela = pg.locator("#dialogo-resumo")
    expect(janela).to_be_visible()
    expect(janela.locator("#resumo-documentos-area")).to_be_visible()
    return janela, origem


@pytest.mark.parametrize("largura", [360, 1440])
def test_polling_real_pronta_v2_atualiza_acoes_sem_perder_copia(
        logado, dados_e2e, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.context.grant_permissions(["clipboard-read", "clipboard-write"])
    oficio, anterior, atual = _versoes(dados_e2e)
    janela, _ = _abrir(pg, oficio)
    rodape = janela.locator("#resumo-rodape")
    expect(rodape).to_contain_text("PDF v2 em geração")
    expect(rodape.get_by_text("Ver minuta", exact=True)).to_have_count(0)
    expect(rodape.get_by_text("Ver o PDF", exact=True)).to_have_count(0)
    expect(rodape.get_by_text("Baixar em Word", exact=True)).to_have_count(0)
    historia = janela.locator('[aria-label="Documentos históricos"]')
    expect(historia).to_contain_text("Ofício v1 (histórico)")
    expect(historia.locator(f'a[href="{reverse("viagens:baixar_documento", args=[anterior.pk])}"]')) \
        .to_have_count(1)
    copia = janela.locator("#eprotocolo-resumo-bloco")
    assert copia.locator("summary").evaluate("el => getComputedStyle(el).display") == "inline-flex"
    copia.locator("summary").click()
    expect(copia).to_have_attribute("open", "")
    expect(copia).to_contain_text("Dados da emissão v2")
    expect(copia.get_by_label("Detalhamento", exact=True)).to_have_value(
        re.compile("Motivo exclusivo da emissão v2"))
    botao = copia.locator('button[data-copiar-alvo="eprotocolo-resumo-1"]')
    botao.click()
    expect(botao.locator("[data-copiar-rotulo]")).to_have_text("Copiado")
    campo = copia.get_by_label("Interessados", exact=True)
    campo.focus()
    # Simula somente a conclusão do worker; a atualização da tela é GET HTMX real.
    Documento.objects.filter(pk=atual.pk).update(situacao="pronto", sha256="b" * 64)
    expect(rodape.get_by_text("Ver o PDF", exact=True)).to_be_visible(timeout=10000)
    expect(rodape.get_by_text("Baixar em Word", exact=True)).to_have_count(1)
    expect(rodape.locator("[data-anexar-assinado]").first).to_have_attribute(
        "data-assinado-titulo", f"Ofício {oficio.numero_formatado} · v2")
    expect(janela.locator("[data-resumo-poll]")).to_have_count(0)
    expect(copia).to_have_attribute("open", "")
    expect(campo).to_be_focused()
    expect(copia).to_contain_text("Dados da emissão v2")
    expect(copia).not_to_contain_text("PDF em geração")
    pasta = Path("artifacts/rs02-resumo")
    pasta.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(pasta / f"corrente-pronta-{largura}.png"))
    assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth")
    violacoes = [v for v in rodar_axe(pg) if v["impact"] in ("serious", "critical")]
    assert not violacoes, [(v["id"], [n["target"] for n in v["nodes"]]) for v in violacoes]
    assert pg.erros_console == []


def test_link_corrente_recusa_via_de_outro_dono_e_pacote_incompleto(logado, dados_e2e):
    """Guards pelo link real, bytes HTTP e comando Baixar, sem geração de minuta viva."""
    pg = logado
    oficio, _, atual = _versoes(dados_e2e)
    original = b"%PDF-1.7\n% original sintetico do oficio corrente\n%%EOF\n"
    atual.dados["justificativa"] = "Justificativa esperada na emissão, ainda sem documento."
    atual.situacao = "pronto"
    atual.sha256 = sha256(original).hexdigest()
    atual.arquivo.save("guard-corrente.pdf", ContentFile(original))
    via = ViaAssinada.objects.create(
        oficio_id=dados_e2e.ids["oficio_outra_unidade"], documento=atual, tipo="oficio",
        enviado_por=dados_e2e.usuarios["outra"], sha256="c" * 64, tamanho=10)
    via.arquivo.save("guard-outro-dono.pdf", ContentFile(b"%PDF-via-de-outra-unidade"))
    janela, _ = _abrir(pg, oficio)
    rodape = janela.locator("#resumo-rodape")
    pdf = rodape.get_by_text("Ver o PDF", exact=True)
    expect(pdf).to_have_attribute("href", reverse("viagens:baixar_documento", args=[atual.pk]))
    resposta = pg.request.get(pdf.get_attribute("href"))
    assert resposta.status == 200 and resposta.body() == original
    assert resposta.headers["x-content-sha256"] == atual.sha256

    downloads = []
    pg.on("download", lambda download: downloads.append(download))
    documentos_antes = Documento.objects.filter(oficio=oficio).count()
    rodape.get_by_role("button", name="Mais ações", exact=True).click()
    rodape.get_by_role("menuitem", name="Baixar documentos…", exact=True).click()
    baixar = pg.get_by_role("dialog", name="Baixar documentos", exact=True)
    expect(baixar.locator('input[name="itens"][value="justificativa"]')).to_be_checked()
    expect(baixar).to_contain_text("PDF indisponível")
    url = reverse("viagens:baixar_oficio", args=[oficio.pk])
    with pg.expect_response(lambda r: url in r.url and r.request.method == "POST") as recusado:
        baixar.get_by_role("button", name="Baixar", exact=True).click()
    assert recusado.value.status == 422
    expect(baixar.locator("[data-baixar-erro]")).to_contain_text(
        re.compile("justificativa.*indisponível"))
    assert downloads == []
    assert Documento.objects.filter(oficio=oficio).count() == documentos_antes
    atual.refresh_from_db()
    assert atual.sha256 == sha256(original).hexdigest()
    assert all(re.fullmatch(r"Failed to load resource: the server responded with a status of "
                            r"422 \(.*\)", erro) for erro in pg.erros_console), pg.erros_console


def test_fechar_aborta_resposta_real_em_voo_e_interrompe_pedidos(logado, dados_e2e):
    pg = logado
    oficio, _, atual = _versoes(dados_e2e)
    janela, origem = _abrir(pg, oficio)
    url = reverse("viagens:resumo", args=[oficio.pk])
    pedidos = []
    fechamentos = []
    pg.on("request", lambda req: pedidos.append(req.url)
          if url in req.url and req.method == "GET" else None)

    def concluir_depois_de_fechar(rota):
        Documento.objects.filter(pk=atual.pk).update(situacao="pronto", sha256="b" * 64)
        resposta = rota.fetch()  # resposta real já contém PDF/Word v2 disponíveis
        assert resposta.status == 200 and "Ver o PDF" in resposta.text()
        janela.locator(".dialogo__fechar").click()
        expect(janela).not_to_be_visible()
        fechamentos.append(True)
        try:
            rota.fulfill(response=resposta)
        except PlaywrightError:
            # Chromium pode recusar fulfill de um pedido já abortado pelo close.
            assert rota.request.failure and "ABORT" in rota.request.failure.upper()

    pg.route("**" + url, concluir_depois_de_fechar, times=1)
    expect(janela).not_to_be_visible(timeout=10000)
    assert fechamentos == [True]
    expect(origem).to_be_focused()
    assert len(pedidos) == 1
    pg.wait_for_timeout(4500)  # duas janelas de polling; não deve existir novo HTTP
    assert len(pedidos) == 1
    expect(janela).not_to_be_visible()
    expect(origem).to_be_focused()
    expect(janela.locator("#resumo-rodape")).not_to_contain_text("Ver o PDF")


def test_historico_gerando_isolado_nao_faz_polling(logado, dados_e2e):
    pg = logado
    oficio, _, _ = _versoes(dados_e2e, historico_gerando=True)
    janela, _ = _abrir(pg, oficio)
    expect(janela.locator("[data-resumo-poll]")).to_have_count(0)
    pedidos = []
    url = reverse("viagens:resumo", args=[oficio.pk])
    pg.on("request", lambda req: pedidos.append(req.url) if url in req.url else None)
    pg.wait_for_timeout(4500)
    assert pedidos == []
    expect(janela.locator("#resumo-rodape")).to_contain_text("Ver o PDF")
    expect(janela.locator('[aria-label="Documentos históricos"]')).to_contain_text("gerando")
    assert pg.erros_console == []


def test_reaberto_preserva_minuta_e_documentos_assinados_historicos(logado, dados_e2e):
    pg = logado
    oficio, _, atual = _versoes(dados_e2e, historico_gerando=True)
    via = ViaAssinada.objects.create(
        oficio=oficio, tipo="oficio", documento=atual, arquivo="assinados/rs02.pdf",
        sha256="c" * 64, tamanho=10, enviado_por=dados_e2e.usuarios["operador"])
    services.reabrir(oficio, dados_e2e.usuarios["gestor"], "Revisar o destino.")
    oficio.refresh_from_db()
    janela, _ = _abrir(pg, oficio)
    expect(janela.locator("[data-resumo-poll]")).to_have_count(0)
    expect(janela.locator("#resumo-rodape")).to_contain_text("Ver minuta")
    expect(janela.locator("#resumo-rodape")).not_to_contain_text("Ver o PDF")
    historia = janela.locator('[aria-label="Documentos históricos"]')
    expect(historia).to_contain_text("Ofício v2 (histórico)")
    expect(historia).to_contain_text("Via assinada histórica · revogada")
    expect(historia.locator(f'a[href="{reverse("viagens:abrir_via_assinada", args=[via.pk])}"]')) \
        .to_have_count(1)
    assert pg.erros_console == []


@pytest.mark.parametrize("alvo", ["word_com_id", "item_sem_id"])
def test_polling_justificativa_preserva_foco_operavel_em_mais_acoes(
        logado, dados_e2e, alvo):
    pg = logado
    oficio, _, atual = _versoes(dados_e2e, historico_gerando=True)
    snapshot = deepcopy(atual.dados)
    snapshot["justificativa"] = "Convite tardio registrado na emissão v2."
    Documento.objects.filter(pk=atual.pk).update(dados=snapshot)
    justificativa = Documento.objects.create(
        oficio=oficio, tipo="justificativa", versao=1, situacao="gerando",
        dados=snapshot, arquivo="documentos/rs02-justificativa-v1.pdf",
        emitido_por=dados_e2e.usuarios["operador"])
    janela, _ = _abrir(pg, oficio)
    expect(janela.locator("[data-resumo-poll]")).to_have_count(1)
    rodape = janela.locator("#resumo-rodape")
    gatilho = rodape.locator(f"#resumo-mais-acoes-{oficio.pk}")
    gatilho.click()
    expect(gatilho).to_have_attribute("aria-expanded", "true")
    word = rodape.locator(f"#resumo-word-{oficio.pk}")
    expect(word).to_be_visible()
    item = (word if alvo == "word_com_id" else rodape.locator(
        '[role="menuitem"]:not([id]):not([aria-disabled="true"])').first)
    if alvo == "item_sem_id":
        assert not item.get_attribute("id")
    item.focus()
    expect(item).to_be_focused()
    Documento.objects.filter(pk=justificativa.pk).update(
        situacao="pronto", sha256="d" * 64)
    # A conclusão vem do GET HTMX real; nenhuma resposta/ação OOB é simulada.
    expect(janela.locator("[data-resumo-poll]")).to_have_count(0, timeout=10000)
    pg.wait_for_function("""id => {
      const foco = document.activeElement;
      const gatilho = document.getElementById(id);
      if (!(foco instanceof HTMLElement) || !gatilho || !foco.isConnected
          || !foco.getClientRects().length || getComputedStyle(foco).visibility === 'hidden') {
        return false;
      }
      if (foco === gatilho) return gatilho.getAttribute('aria-expanded') === 'false';
      const painel = foco.closest('[role="menu"]');
      return painel && gatilho.getAttribute('aria-expanded') === 'true'
        && gatilho.getAttribute('aria-controls') === painel.id;
    }""", arg=f"resumo-mais-acoes-{oficio.pk}", timeout=10000)
    if gatilho.get_attribute("aria-expanded") == "true":
        pg.keyboard.press("Escape")
    expect(gatilho).to_be_focused()
    gatilho.press("Enter")
    expect(word).to_be_visible()
    expect(word).to_be_focused()
    word.press("Escape")
    expect(gatilho).to_be_focused()
    assert pg.erros_console == []
