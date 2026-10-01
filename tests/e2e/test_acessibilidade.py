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
