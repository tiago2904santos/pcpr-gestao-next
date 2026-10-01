"""Decisão do dono do produto (ADR 0006): a navegação principal é SUPERIOR, nunca lateral.

Desktop = menu superior · tablet = menu superior responsivo · celular = gaveta lateral
temporária aberta pelo ☰ (decisão D9) · barra lateral permanente = não. Estes testes
estáticos impedem que uma navegação lateral fixa volte por CSS, template ou registro de
módulo; o comportamento no navegador está em `tests/e2e/test_navegacao_superior.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from gestao.plataforma import navegacao
from gestao.plataforma.navegacao import Grupo, Item, Modulo

RAIZ = Path(__file__).resolve().parent.parent
FONTES = [
    *RAIZ.glob("templates/**/*.html"),
    *RAIZ.glob("gestao/**/templates/**/*.html"),
    *RAIZ.glob("static/css/*.css"),
    *RAIZ.glob("static/js/**/*.js"),
]
PROIBIDOS = re.compile(r"sidebar|side-nav|barra-lateral|menu-lateral|navegacao-lateral|\blateral__",
                       re.IGNORECASE)


@pytest.mark.parametrize("arquivo", FONTES, ids=lambda p: str(p.relative_to(RAIZ)))
def test_sem_navegacao_lateral_no_codigo(arquivo: Path):
    achados = [f"{n}: {linha.strip()}" for n, linha in
               enumerate(arquivo.read_text(encoding="utf-8").splitlines(), start=1)
               if PROIBIDOS.search(linha)]
    assert not achados, "Navegação lateral é proibida (ADR 0006):\n" + "\n".join(achados)


def test_gaveta_so_no_celular_e_sempre_temporaria():
    """A gaveta (☰) só existe abaixo de 768px e começa escondida; acima, barra horizontal."""
    css = (RAIZ / "static/css/layout.css").read_text(encoding="utf-8")
    js = (RAIZ / "static/js/componentes/shell.js").read_text(encoding="utf-8")
    assert "const LARGURA_GAVETA = 768;" in js
    blocos = css.split("@media")
    celular = next(b for b in blocos if b.startswith(" (max-width: 767.98px)"))
    fechada = celular.split(".shell--gaveta-aberta .navegacao")[0]
    assert "position: fixed" in fechada and "translateX(-100%)" in fechada
    assert "visibility: hidden" in fechada
    # Nenhuma outra faixa posiciona o menu como painel fixo (seria barra lateral permanente).
    for bloco in blocos:
        if bloco is not celular and ".navegacao {" in bloco:
            assert "position: fixed" not in bloco.split(".navegacao {")[1].split("}")[0]


def test_decisao_registrada_na_adr_e_no_design_system():
    adr = (RAIZ / "docs/adr/0006-app-shell-menu-superior.md").read_text(encoding="utf-8")
    nav = (RAIZ / "docs/design-system/navigation.md").read_text(encoding="utf-8")
    for texto in (adr, nav):
        assert "SIDEBAR PERMANENTE = NÃO" in texto


def _modulo(itens_diretos: int, menus: int = 0) -> Modulo:
    item = Item("Item", "painel:inicio", "home")
    grupos = [Grupo("Direto", tuple([item] * itens_diretos))]
    grupos += [Grupo(f"Menu {i}", (item, item), em_menu=True) for i in range(menus)]
    return Modulo("teste-nav", "Teste", "home", "painel:inicio", grupos=tuple(grupos))


def test_limite_de_entradas_na_barra():
    assert navegacao.entradas_na_barra(_modulo(5, menus=2)) == 7
    with pytest.raises(ValueError, match="máximo 7"):
        navegacao.registrar_modulo(_modulo(6, menus=2))


def test_modulos_registrados_respeitam_o_limite():
    assert navegacao.modulos()
    for modulo in navegacao.modulos():
        assert navegacao.entradas_na_barra(modulo) <= navegacao.MAX_ENTRADAS_NA_BARRA
