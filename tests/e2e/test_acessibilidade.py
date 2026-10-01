"""WCAG 2.2 AA automático (axe-core) em todas as páginas do piloto."""

from __future__ import annotations

import pytest

from .conftest import rodar_axe, salvar_relatorio
from .rotas import ROTAS_AUTENTICADAS, ROTAS_PUBLICAS, resolver

pytestmark = pytest.mark.a11y

GRAVES = {"serious", "critical"}


def _avaliar(pg, rota):
    pg.goto(rota, wait_until="networkidle")
    violacoes = rodar_axe(pg)
    graves = [v for v in violacoes if v["impact"] in GRAVES]
    salvar_relatorio(f"axe-{rota.strip('/').replace('/', '_') or 'raiz'}.json", violacoes)
    detalhes = [(v["id"], v["help"], [n["target"] for n in v["nodes"]][:3]) for v in graves]
    assert not graves, f"{rota}: {detalhes}"


@pytest.mark.parametrize("rota", ROTAS_PUBLICAS)
def test_paginas_publicas_sem_violacoes_graves(pagina, rota):
    _avaliar(pagina, rota)


@pytest.mark.parametrize("rota", ROTAS_AUTENTICADAS)
def test_paginas_autenticadas_sem_violacoes_graves(logado, dados_e2e, rota):
    _avaliar(logado, resolver(rota, dados_e2e.ids))


@pytest.mark.parametrize("largura", [360, 1440])
def test_ui_lab_sem_violacoes_em_todas_as_larguras(logado, largura):
    logado.set_viewport_size({"width": largura, "height": 900})
    _avaliar(logado, "/ui-lab/")


def _rgb(token: str) -> str:
    from scripts import contraste

    hexa = contraste.valores()[token]
    r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgb({r}, {g}, {b})"


def _foco(pg, seletor: str) -> dict:
    alvo = pg.locator(seletor).first
    alvo.focus()
    pg.keyboard.press("Shift+Tab")
    pg.keyboard.press("Tab")
    return alvo.evaluate("""e => { const s = getComputedStyle(e);
        return {outline: s.outlineStyle, cor: s.outlineColor, largura: s.outlineWidth,
                offset: s.outlineOffset, borda: s.borderColor, sombra: s.boxShadow}; }""")


def test_foco_por_teclado_e_a_assinatura_do_sistema_nao_o_anel_do_navegador(logado, dados_e2e):
    """Overdrive 2: anel grafite com halo claro no conteúdo; dourado sobre o cabeçalho;
    campos acendem (borda grafite + halo) em vez de anel externo. Nunca azul."""
    pg = logado
    pg.goto("/viagens/oficios/")
    botao = _foco(pg, "a.botao--primario")
    assert botao["outline"] == "solid" and botao["cor"] == _rgb("--grafite-900"), botao
    assert botao["largura"] == "2px" and botao["offset"] == "2px", botao
    assert _rgb("--neutro-0") in botao["sombra"], botao  # halo claro no vão

    cabecalho = _foco(pg, ".cabecalho__botao")
    assert cabecalho["cor"] == _rgb("--dourado-300"), cabecalho
    assert _rgb("--grafite-950") in cabecalho["sombra"], cabecalho

    campo = _foco(pg, "#busca-oficios")
    assert campo["outline"] == "none" and campo["borda"] == _rgb("--grafite-800"), campo
    assert campo["sombra"] != "none", campo  # halo dourado

    registro = _foco(pg, ".registro__link")
    linha = pg.locator(".registro").first.evaluate("e => getComputedStyle(e).boxShadow")
    assert registro["outline"] == "none" and _rgb("--grafite-900") in linha, (registro, linha)

    # Nenhum estilo de foco computado usa o azul do navegador/DS antigo.
    azul = _rgb("--azul-600")
    for estilo in (botao, cabecalho, campo, registro):
        assert azul not in estilo["cor"] and azul not in estilo["sombra"] and azul not in estilo["borda"]
