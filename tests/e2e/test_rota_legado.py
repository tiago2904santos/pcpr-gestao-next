"""Sugestão da referência chega ao formulário; tempos manuais continuam editáveis."""

from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.viagens import rotas
from gestao.viagens.models import Oficio

from .test_fluxo_oficio import _data_hora

pytestmark = pytest.mark.e2e


def _salvar(pg):
    with pg.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/editar/")) as envio:
        pg.locator("#id_protocolo").press("Enter")
    resposta = envio.value
    assert resposta.status < 400, resposta.text()
    pg.wait_for_url("**/editar/?salvo=1")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Rascunho salvo às")


def _valor_inteiro(campo):
    assert campo.evaluate("""campo => {
        const estilo = getComputedStyle(campo);
        const contexto = document.createElement('canvas').getContext('2d');
        contexto.font = `${estilo.fontSize} ${estilo.fontFamily}`;
        const disponivel = campo.clientWidth - parseFloat(estilo.paddingLeft)
            - parseFloat(estilo.paddingRight);
        return contexto.measureText(campo.value).width <= disponivel;
    }"""), "O valor do tempo deve aparecer inteiro, sem rolagem do texto."


@pytest.mark.parametrize("largura", [360, 1440])
def test_rota_legada_sugere_tempos_e_preserva_edicao_manual(logado, dados_e2e, settings,
                                                         monkeypatch, largura):
    settings.ROTAS_PROVEDOR = "osrm"
    monkeypatch.setitem(rotas.PROVEDORES, "osrm", lambda a, b: (
        300_000.0, 10_800.0, [[-49.27, -25.43], [-50.16, -25.09]]))
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    pk = dados_e2e.ids["oficio_vazio"]
    pg.goto(f"/viagens/oficios/{pk}/editar/")
    pg.locator("input[name='destino-0-cidade']").fill("Ponta Grossa/PR")
    _data_hora(pg, "destino-0-saida", 20, 6)
    _data_hora(pg, "retorno-saida", 21, 8)
    viagem = pg.locator("#id_destino-0-tempo_viagem")
    adicional = pg.locator("#id_destino-0-tempo_adicional")
    expect(viagem).to_have_value("04:00")
    expect(adicional).to_have_value("00:45")
    _salvar(pg)
    pg.reload()
    expect(viagem).to_have_value("04:00")
    expect(adicional).to_have_value("00:45")

    pasta = Path("artifacts/rota-legado")
    pasta.mkdir(parents=True, exist_ok=True)
    for captura in ([360, 390, 768, 1024, 1440] if largura == 1440 else [largura]):
        pg.set_viewport_size({"width": captura, "height": 900})
        pg.locator("#roteiro").scroll_into_view_if_needed()
        _valor_inteiro(viagem)
        _valor_inteiro(adicional)
        pg.screenshot(path=str(pasta / f"rota-{captura}.png"), full_page=True)
    pg.set_viewport_size({"width": largura, "height": 900})
    # Ajustes do operador não são substituídos pela sugestão em outro acesso.
    viagem.fill("02:00")
    adicional.fill("00:30")
    _salvar(pg)
    pg.reload()
    expect(viagem).to_have_value("02:00")
    expect(adicional).to_have_value("00:30")
    trecho = Oficio.objects.get(pk=pk).trechos.order_by("ordem").first()
    assert (trecho.tempo_viagem_min, trecho.tempo_adicional_min) == (120, 30)
    assert pg.erros_console == []
