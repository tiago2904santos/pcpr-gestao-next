"""Cadastro rápido real após carga adiada, erro recuperável e fechamento durante busca."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from gestao.cadastros.models import Servidor, Viatura
from gestao.viagens.models import Oficio

from .conftest import AXE, rodar_axe, salvar_relatorio

pytestmark = pytest.mark.e2e


def _teclado_modal(pg, janela):
    pg.keyboard.press("Tab")
    assert janela.evaluate("d => d.contains(document.activeElement)")
    pg.keyboard.press("Shift+Tab")
    assert janela.evaluate("d => d.contains(document.activeElement)")


def _sobreposto(pg, pai, rotulo, id_janela):
    origem = pai.get_by_role("button", name=rotulo, exact=True)
    origem.click()
    janela = pg.locator(f"#{id_janela}")
    expect(janela).to_be_visible()
    expect(janela.locator("form")).to_have_count(1)
    _teclado_modal(pg, janela)
    pg.keyboard.press("Escape")
    expect(janela).to_be_hidden()
    expect(pai).to_be_visible()
    expect(origem).to_be_focused()


@pytest.mark.parametrize("largura", [360, 1440])
def test_cadastra_servidor_e_viatura_sem_perder_a_folha(logado, dados_e2e, largura):
    pg = logado
    pk = dados_e2e.ids["oficio_rascunho"]
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.goto(reverse("viagens:editar", args=[pk]), wait_until="networkidle")
    pg.evaluate("async () => await document.fonts.ready")
    expect(pg.locator("#dialogo-servidor form")).to_have_count(0)
    inicio = rodar_axe(pg)
    salvar_relatorio(f"cadastro-adiado-axe-inicial-{largura}.json", inicio)
    assert not [v for v in inicio if v["impact"] in ("serious", "critical")]
    texto = "Dados preservados ao cadastrar sem sair da folha."
    pg.locator("#id_motivo").fill(texto)
    pg.get_by_role("button", name="Cadastrar servidor", exact=True).click()
    janela = pg.locator("#dialogo-servidor")
    expect(janela).to_be_visible()
    nome = janela.get_by_label("Nome completo")
    expect(nome).to_be_focused(timeout=15000)
    _teclado_modal(pg, janela)
    expect(nome).to_be_focused()
    _sobreposto(pg, janela, "Cadastrar cargo", "dialogo-cargo")
    _sobreposto(pg, janela, "Cadastrar unidade", "dialogo-unidade")
    for campo in ["cpf", "rg", "telefone"]:
        expect(janela.locator(f"input[name='{campo}']")).to_be_visible()
    expect(pg.locator("#dialogo-viatura form")).to_have_count(1)
    nome.fill(f"Servidora carga adiada {largura}")
    janela.get_by_role("button", name="Cadastrar servidor", exact=True).click()
    expect(janela).to_be_hidden()
    expect(pg.locator("#equipe")).to_contain_text(f"Servidora Carga Adiada {largura}")
    servidor = Servidor.objects.get(nome=f"Servidora Carga Adiada {largura}")
    assert Oficio.objects.get(pk=pk).viajantes.filter(servidor=servidor).exists()
    expect(pg.locator("#id_motivo")).to_have_value(texto)
    pg.get_by_role("button", name="Cadastrar viatura", exact=True).click()
    viatura = pg.locator("#dialogo-viatura")
    expect(viatura).to_be_visible()
    _teclado_modal(pg, viatura)
    _sobreposto(pg, viatura, "Cadastrar combustível", "dialogo-combustivel")
    placa = f"TST{1 if largura == 360 else 2}C23"
    viatura.get_by_label("Placa").fill(placa)
    viatura.get_by_label("Modelo").fill("Veículo teste de carga adiada")
    viatura.get_by_role("button", name="Cadastrar viatura", exact=True).click()
    expect(viatura).to_be_hidden()
    criada = Viatura.objects.get(placa=placa)
    expect(pg.locator("#id_viatura")).to_have_value(str(criada.pk))
    expect(pg.locator("#id_motivo")).to_have_value(texto)
    pasta = Path("artifacts/cadastro-adiado")
    pasta.mkdir(parents=True, exist_ok=True)
    pg.get_by_role("button", name="Cadastrar servidor", exact=True).click()
    expect(janela).to_be_visible()
    janela.evaluate("async d => { await Promise.all(d.getAnimations().map(a => a.finished)); }")
    sessao = pg.context.new_cdp_session(pg)
    raiz = sessao.send("DOM.getDocument")["root"]["nodeId"]
    no = sessao.send("DOM.querySelector", {"nodeId": raiz, "selector": "#id_marcador-gatilho"})["nodeId"]
    backend = sessao.send("DOM.describeNode", {"nodeId": no})["node"]["backendNodeId"]
    arvore = sessao.send("Accessibility.getPartialAXTree",
                         {"backendNodeId": backend, "fetchRelatives": True})
    salvar_relatorio(f"cadastro-adiado-ax-{largura}.json", arvore)
    controle = next(n for n in arvore["nodes"] if n.get("backendDOMNodeId") == backend)
    assert controle["ignored"] and any(
        r["name"] == "activeModalDialog" for r in controle["ignoredReasons"])
    sessao.detach()
    pg.screenshot(path=str(pasta / f"servidor-{largura}.png"))
    assert pg.erros_console == [], "Erros antes da auditoria axe"
    # O Chromium exclui o fundo da árvore acessível pelo diálogo modal nativo.
    # Auditar toda a página aberta antes, e aqui a superfície modal operável.
    pg.evaluate(AXE.read_text() + "\n;true")
    violacoes = pg.evaluate("""async () => (await axe.run(
        document.querySelector('#dialogo-servidor'), {
        runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']},
        resultTypes: ['violations']
        })).violations""")
    salvar_relatorio(f"cadastro-adiado-axe-{largura}.json", violacoes)
    assert not [v for v in violacoes if v["impact"] in ("serious", "critical")]
    assert pg.erros_console == []
    janela.get_by_role("button", name="Cancelar", exact=True).click()
    expect(janela).to_be_hidden()
    # Finalizar é um envio real que aguarda o autosave e termina fora da folha.
    # Evita que pagehide envie um beacon concorrente com TRUNCATE da fixture.
    pg.get_by_role("button", name="Finalizar", exact=True).click()
    pg.wait_for_url("**/viagens/oficios/")
    assert Oficio.objects.get(pk=pk).motivo == texto


def test_falha_de_carga_orienta_e_nova_abertura_tenta_de_novo(logado, dados_e2e):
    pg = logado
    pk = dados_e2e.ids["oficio_rascunho"]
    pg.goto(reverse("viagens:editar", args=[pk]))
    pg.route("**/editar/?cadastros=1", lambda rota: rota.fulfill(status=503), times=1)
    botao = pg.get_by_role("button", name="Cadastrar servidor", exact=True)
    botao.click()
    janela = pg.locator("#dialogo-servidor")
    expect(janela.locator("[data-cadastro-estado]")).to_contain_text("Feche e abra novamente")
    janela.get_by_role("button", name="Fechar", exact=True).click()
    expect(janela).to_be_hidden()
    botao.click()
    expect(janela.get_by_label("Nome completo")).to_be_focused(timeout=15000)
    # 503 foi injetado deliberadamente; não aceitar exceção JS adicional.
    assert all("503" in erro for erro in pg.erros_console), pg.erros_console


def test_fechar_durante_carga_nao_reabre_nem_rouba_foco(logado, dados_e2e):
    pg = logado
    pk = dados_e2e.ids["oficio_rascunho"]
    pg.goto(reverse("viagens:editar", args=[pk]))
    janela = pg.locator("#dialogo-servidor")

    def responder(rota):
        resposta = rota.fetch()
        try:
            janela.get_by_role("button", name="Fechar", exact=True).click()
            expect(janela).to_be_hidden()
            pg.locator("#id_motivo").focus()
        finally:
            rota.fulfill(response=resposta)
            resposta.dispose()

    pg.route("**/editar/?cadastros=1", responder, times=1)
    pg.get_by_role("button", name="Cadastrar servidor", exact=True).click()
    expect(janela.locator("form")).to_have_count(1, timeout=15000)
    expect(janela).to_be_hidden()
    expect(pg.locator("#id_motivo")).to_be_focused()
    assert pg.erros_console == []
