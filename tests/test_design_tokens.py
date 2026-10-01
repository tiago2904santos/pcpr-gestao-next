"""Os tokens são a fonte única de valores visuais (docs/design-system/principles.md §9)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
CSS = RAIZ / "static" / "css"
sys.path.insert(0, str(RAIZ / "scripts"))

import contraste  # noqa: E402

ARQUIVOS = sorted(p.name for p in CSS.glob("*.css") if p.name != "tokens.css")
COR_SOLTA = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")


def _sem_comentarios(texto: str) -> str:
    return re.sub(r"/\*.*?\*/", "", texto, flags=re.S)


@pytest.mark.parametrize("arquivo", ARQUIVOS)
def test_css_nao_usa_cor_fora_dos_tokens(arquivo):
    texto = _sem_comentarios((CSS / arquivo).read_text())
    achados = [linha.strip() for linha in texto.splitlines() if COR_SOLTA.search(linha)]
    assert not achados, f"{arquivo} usa cor literal; use var(--…): {achados[:5]}"


@pytest.mark.parametrize("arquivo", ARQUIVOS)
def test_css_nao_usa_espacamento_em_px_solto(arquivo):
    """Espaçamentos (margin/padding/gap) só por token. Bordas de 1–4px são permitidas."""
    texto = _sem_comentarios((CSS / arquivo).read_text())
    proibidos = re.findall(
        r"(?:margin|padding|gap)[a-z-]*\s*:\s*[^;]*\b(?:[5-9]|\d{2,})px", texto
    )
    assert not proibidos, f"{arquivo}: espaçamento em px fora dos tokens: {proibidos[:5]}"


def test_todos_os_tokens_usados_existem():
    definidos = set(re.findall(r"(--[a-z0-9-]+)\s*:", (CSS / "tokens.css").read_text()))
    usados: set[str] = set()
    for arquivo in CSS.glob("*.css"):
        usados |= set(re.findall(r"var\((--[a-z0-9-]+)", arquivo.read_text()))
    locais = {"--botao-fundo", "--botao-texto", "--botao-borda", "--botao-fundo-hover",
              "--selo-fundo", "--selo-texto", "--selo-borda", "--alerta-fundo",
              "--alerta-texto", "--alerta-borda"}
    faltando = sorted(usados - definidos - locais)
    assert not faltando, f"Tokens usados mas não definidos: {faltando}"


@pytest.mark.parametrize("par", contraste.tabela(), ids=lambda p: f"{p[0]}/{p[1]}")
def test_contraste_wcag_dos_pares_do_design_system(par):
    primeiro, fundo, valor, minimo, uso = par
    assert valor >= minimo, f"{uso}: {primeiro} sobre {fundo} = {valor}:1 (mínimo {minimo}:1)"


def test_sem_modo_escuro():
    """Decisão do dono do produto: somente tema claro (docs/design-system/principles.md §9)."""
    for arquivo in CSS.glob("*.css"):
        texto = arquivo.read_text()
        assert "prefers-color-scheme" not in texto, f"{arquivo.name} define modo escuro"
    assert "color-scheme: light;" in (CSS / "base.css").read_text()
    base = (RAIZ / "templates" / "base_documento.html").read_text()
    assert '<meta name="color-scheme" content="light">' in base
