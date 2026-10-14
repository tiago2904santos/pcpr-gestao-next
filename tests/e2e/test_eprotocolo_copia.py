"""Campos copiáveis da Folha/Resumo: Clipboard, fallback e atualização real HTMX."""

import re
from pathlib import Path

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from gestao.viagens.models import Oficio

from .conftest import rodar_axe

pytestmark = pytest.mark.e2e


def _abrir(bloco):
    # O bloco nasce fechado (resumo e folha); abre pelo summary quando ainda está fechado.
    if bloco.get_attribute("open") is None:
        bloco.locator("summary").click()
    expect(bloco).to_have_attribute("open", "")


def _clipboard(pg):
    # O Clipboard do Windows devolve CRLF; inputs/textarea usam LF no DOM.
    # Preservar todos os demais caracteres, espaços e linhas do texto copiado.
    return pg.evaluate("navigator.clipboard.readText()").replace("\r\n", "\n")


@pytest.mark.parametrize("largura", [360, 1440])
def test_folha_copia_campos_e_tudo_sem_dados_pessoais(logado, dados_e2e, largura):
    pg = logado
    pg.context.grant_permissions(["clipboard-read", "clipboard-write"])
    pg.set_viewport_size({"width": largura, "height": 900})
    pk = dados_e2e.ids["oficio_rascunho"]
    pg.goto(reverse("viagens:editar", args=[pk]))
    bloco = pg.locator("#eprotocolo-folha-bloco")
    _abrir(bloco)
    botoes = bloco.locator("button[data-copiar-alvo]:not([data-copiar-revelar])")
    expect(botoes).to_have_count(5)
    for botao in botoes.all():
        campo = pg.locator("#" + botao.get_attribute("data-copiar-alvo"))
        texto = campo.input_value()
        botao.click()
        expect(botao.locator("[data-copiar-rotulo]")).to_have_text("Copiado")
        assert _clipboard(pg) == texto
    tudo = bloco.locator("button[data-copiar-revelar]")
    texto = pg.locator("#" + tudo.get_attribute("data-copiar-alvo")).input_value()
    tudo.click()
    expect(tudo.locator("[data-copiar-rotulo]")).to_have_text("Copiado")
    assert _clipboard(pg) == texto
    assert "Interessados:" in texto and "Detalhamento:" in texto
    for viajante in Oficio.objects.get(pk=pk).viajantes.select_related("servidor"):
        assert viajante.servidor.nome in texto
        assert viajante.servidor.cpf_formatado not in texto
        assert viajante.servidor.rg not in texto
    pasta = Path("artifacts/eprotocolo")
    pasta.mkdir(parents=True, exist_ok=True)
    for captura in ([360, 390, 768, 1024, 1440] if largura == 1440 else [largura]):
        pg.set_viewport_size({"width": captura, "height": 900})
        bloco.scroll_into_view_if_needed()
        assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth")
        pg.screenshot(path=str(pasta / f"folha-{captura}.png"), full_page=True)
    assert pg.erros_console == []


def test_resumo_nao_tem_copia_e_mostra_protocolo_no_cabecalho(logado, dados_e2e):
    pg = logado
    oficio = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])
    pg.goto(f"/viagens/oficios/?q={oficio.numero_formatado}&escopo=numero")
    pg.locator(".registro__link").first.click()
    janela = pg.locator("#dialogo-resumo")
    expect(janela).to_be_visible()
    # Os dados para o eProtocolo vivem só na folha; o Resumo mostra o protocolo na identificação.
    expect(janela.locator("[data-dados-eprotocolo]")).to_have_count(0)
    expect(janela.locator(".registro-hero__complemento")).to_contain_text(oficio.protocolo_formatado)
    for largura in [360, 1440]:
        pg.set_viewport_size({"width": largura, "height": 900})
        assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth")
    violacoes = [v for v in rodar_axe(pg) if v["impact"] in ("serious", "critical")]
    assert not violacoes, [(v["id"], [n["target"] for n in v["nodes"]]) for v in violacoes]
    assert pg.erros_console == []


def test_autosave_atualiza_texto_e_preserva_divulgacao_aberta(logado, dados_e2e):
    pg = logado
    pk = dados_e2e.ids["oficio_rascunho"]
    pg.goto(reverse("viagens:editar", args=[pk]))
    bloco = pg.locator("#eprotocolo-folha-bloco")
    _abrir(bloco)
    texto = "Motivo atualizado para copiar depois do salvamento."
    url = reverse("viagens:autosave_oficio", args=[pk])
    with pg.expect_response(lambda r: r.request.method == "POST" and url in r.url) as envio:
        pg.locator("#id_motivo").fill(texto)
    assert envio.value.status == 200
    expect(bloco.get_by_label("Detalhamento", exact=True)).to_have_value(
        re.compile(texto), timeout=15000)
    expect(bloco).to_have_attribute("open", "")
    assert Oficio.objects.get(pk=pk).motivo == texto
    assert pg.erros_console == []


def test_equipe_htmx_preserva_foco_na_copia_durante_resposta(logado, dados_e2e):
    pg = logado
    pk = dados_e2e.ids["oficio_rascunho"]
    oficio = Oficio.objects.get(pk=pk)
    nome = oficio.viajantes.select_related("servidor").get().servidor.nome
    pg.goto(reverse("viagens:editar", args=[pk]))
    bloco = pg.locator("#eprotocolo-folha-bloco")
    _abrir(bloco)
    campo = bloco.get_by_label("Interessados", exact=True)
    url = reverse("viagens:definir_motorista", args=[pk])

    def responder(rota):
        resposta = rota.fetch()
        try:
            # A pessoa voltou à cópia enquanto a alteração da equipe aguardava resposta.
            campo.focus()
        finally:
            rota.fulfill(response=resposta)

    pg.route("**" + url, responder, times=1)
    with pg.expect_response(lambda r: url in r.url and r.request.method == "POST") as envio:
        pg.get_by_role("button", name=f"Desmarcar {nome} como motorista", exact=True).click()
    assert envio.value.status == 200
    expect(bloco).to_have_attribute("open", "")
    expect(campo).to_be_focused()
    assert not Oficio.objects.get(pk=pk).viajantes.get().motorista
    pg.wait_for_load_state("networkidle")
    assert pg.erros_console == []
