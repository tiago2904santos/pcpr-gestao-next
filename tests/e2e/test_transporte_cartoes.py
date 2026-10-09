"""Seleção em cartão, preservação da busca e motorista na preparação do ofício."""
import json
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.cadastros.models import Viatura
from gestao.viagens.models import Oficio

from .conftest import rodar_axe

pytestmark = [pytest.mark.e2e, pytest.mark.visual, pytest.mark.a11y]


@pytest.mark.parametrize("largura", [360, 390, 768, 1024, 1440])
def test_busca_cartao_remocao_e_motorista_sem_perder_valor(logado, dados_e2e, largura):
    pg = logado
    pg.emulate_media(reduced_motion="reduce")
    pg.set_viewport_size({"width": largura, "height": 900})
    pk = dados_e2e.ids["oficio_rascunho"]
    pg.goto(f"/viagens/oficios/{pk}/editar/")
    pg.locator("#t-recursos").evaluate("e=>e.scrollIntoView({block:'start'})")
    busca = pg.locator("#id_viatura-busca")
    cartao = pg.locator("[data-viatura-cartao]")
    externo = pg.locator("details.motorista-externo")
    expect(externo).to_be_hidden()
    busca.fill("ABC")
    expect(pg.locator("#transporte [role='option']").first).to_contain_text("ABC1D23")
    busca.press("Enter")
    expect(busca).to_have_value("")
    expect(cartao).to_contain_text("ABC1D23")
    # Reselecionar a viatura inicial não cria alteração fantasma nem pedido de salvar.
    expect(pg.locator("[data-status-salvamento]")).not_to_contain_text("Alterações não salvas")
    busca.fill("XYZ")
    expect(pg.locator("#transporte [role='option']").first).to_contain_text("XYZ-9876")
    busca.press("Enter")
    escolhida = Viatura.objects.get(placa="XYZ9876")
    expect(pg.locator("#id_viatura")).to_have_value(str(escolhida.pk))
    expect(pg.locator("pc-combobox[data-escolha-em-cartao] [aria-live]")).to_contain_text("Selecionado: XYZ-9876")
    meta = pg.locator("#id_viatura option:checked").get_attribute("data-meta")
    expect(cartao.locator("[data-recurso-meta]")).to_have_text(meta)
    assert cartao.evaluate("e=>getComputedStyle(e).backgroundColor") == pg.locator("#equipe .equipe__cartao").first.evaluate("e=>getComputedStyle(e).backgroundColor")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    assert Oficio.objects.get(pk=pk).viatura_id == escolhida.pk

    # Uma consulta abandonada ou apagada não remove a viatura já escolhida.
    busca.fill("ABC")
    busca.press("Escape")
    expect(cartao).to_contain_text("XYZ-9876")
    busca.fill("")
    busca.press("Escape")
    expect(pg.locator("#id_viatura")).to_have_value(str(escolhida.pk))
    assert pg.locator("#equipe .pessoa__nome, #equipe .pessoa__meta").evaluate_all("""els => els.every(e =>
      getComputedStyle(e).whiteSpace === 'nowrap' && e.title === e.textContent.trim()
      && e.clientHeight <= parseFloat(getComputedStyle(e).lineHeight) + 1)""")

    violacoes = rodar_axe(pg)
    assert not violacoes
    assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert pg.erros_console == []
    pasta = Path("artifacts/transporte-cartoes")
    pasta.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(pasta / f"selecionada-{largura}.png"))
    (pasta / f"axe-{largura}.json").write_text(json.dumps(violacoes), encoding="utf-8")

    autosave = pg.locator("#form-oficio").get_attribute("data-autosave")
    with pg.expect_response(lambda r: autosave in r.url and r.request.method == "POST") as salvamento:
        cartao.get_by_role("button", name="Remover viatura", exact=False).press("Enter")
    assert salvamento.value.json()["salvo"]
    expect(cartao).to_be_hidden()
    expect(busca).to_be_focused()
    expect(pg.locator("#id_viatura")).to_have_value("")
    busca.press("Escape")
    pg.get_by_role("button", name="Desmarcar Carla Regina Duarte como motorista").click()
    expect(externo).to_be_visible()
    with pg.expect_response(lambda r: autosave in r.url and r.request.method == "POST") as salvamento:
        externo.locator("summary").press("Enter")
    assert salvamento.value.json()["salvo"]
    expect(externo).to_have_js_property("open", True)
    expect(pg.locator("#id_motorista_externo")).to_be_enabled()
    expect(pg.get_by_role("combobox", name="Quem dirige", exact=True)).to_be_enabled()
    with pg.expect_response(lambda r: autosave in r.url and r.request.method == "POST") as salvamento:
        modo = pg.get_by_role("combobox", name="Quem dirige", exact=True)
        modo.press("Enter")
        modo.press("End")
        modo.press("Enter")
        pg.locator("#id_motorista_externo_nome").fill("Motorista externo E2E")
        pg.locator("#id_motorista_oficio_origem").fill("23/2026")
        pg.locator("#id_motorista_protocolo_origem").fill("12.345.678-9")
    assert salvamento.value.json()["salvo"]
    expect(externo.locator("summary")).to_contain_text("Motorista externo E2E")
    expect(externo.locator("summary")).to_contain_text("23/2026")
    # Voltar à equipe fecha/desabilita a opção externa; autosave não a reativa.
    with pg.expect_response(lambda r: "/equipe/motorista/" in r.url and r.request.method == "POST") as motorista:
        cartao_motorista = pg.get_by_role("button", name="Marcar Carla Regina Duarte como motorista")
        if largura in (360, 768, 1440):
            cartao_motorista.click()
        else:
            cartao_motorista.press("Enter")
    assert motorista.value.status == 200, motorista.value.text()
    expect(pg.locator("#equipe [data-motorista]")).to_be_visible()
    expect(externo).to_be_hidden()
    expect(pg.locator("#id_motorista_externo")).to_have_value("")
    expect(pg.locator("#id_motorista_externo")).to_be_disabled()
    with pg.expect_response(lambda r: autosave in r.url and r.request.method == "POST") as salvamento:
        pg.locator("#id_motivo").fill("Preservar motorista da equipe depois da troca.")
    assert salvamento.value.json()["salvo"]
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    pg.wait_for_load_state("networkidle")
    oficio = Oficio.objects.get(pk=pk)
    assert not oficio.motorista_externo
    assert oficio.viajantes.filter(motorista=True, servidor__nome="Carla Regina Duarte").exists()


def test_viatura_nativa_sem_javascript_continua_salvando(logado, dados_e2e):
    pg = logado
    pk = dados_e2e.ids["oficio_rascunho"]
    pg.goto(f"/viagens/oficios/{pk}/editar/")
    ctx = pg.context.browser.new_context(storage_state=pg.context.storage_state(), java_script_enabled=False)
    try:
        nativa = ctx.new_page()
        nativa.goto(pg.url)
        viatura = Viatura.objects.get(placa="XYZ9876")
        campo = nativa.get_by_label("Selecionar viatura", exact=False)
        expect(campo).to_be_visible()
        campo.select_option(str(viatura.pk))
        nativa.get_by_role("button", name="Salvar rascunho", exact=True).first.click()
        expect(campo).to_have_value(str(viatura.pk))
        assert Oficio.objects.get(pk=pk).viatura_id == viatura.pk
    finally:
        ctx.close()
