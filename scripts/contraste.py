"""Calcula o contraste (WCAG 2.x) dos pares de cor do Design System.

Lê os valores direto de static/css/tokens.css (fonte única). Usado por
docs/design-system/colors.md e por tests/test_design_tokens.py.
"""

from __future__ import annotations

import re
from pathlib import Path

TOKENS = Path(__file__).resolve().parent.parent / "static" / "css" / "tokens.css"

# (texto, fundo, mínimo exigido, uso)
PARES: list[tuple[str, str, float, str]] = [
    ("--neutro-900", "--neutro-0", 4.5, "Texto principal sobre superfície"),
    ("--neutro-900", "--neutro-50", 4.5, "Texto principal sobre fundo da página"),
    ("--neutro-600", "--neutro-0", 4.5, "Texto secundário sobre superfície"),
    ("--neutro-600", "--neutro-50", 4.5, "Texto secundário sobre fundo"),
    ("--neutro-500", "--neutro-0", 4.5, "Texto terciário (placeholder) sobre superfície"),
    ("--neutro-500", "--neutro-50", 4.5, "Texto terciário sobre fundo"),
    ("--neutro-600", "--neutro-100", 4.5, "Texto secundário sobre fundo do login/realce"),
    ("--neutro-300", "--grafite-800", 4.5, "Texto sutil do cabeçalho (busca, subtítulo)"),
    ("--neutro-0", "--grafite-900", 4.5, "Texto do cabeçalho / botão primário"),
    ("--grafite-950", "--dourado-500", 4.5, "Texto do botão de marca"),
    ("--dourado-700", "--neutro-0", 4.5, "Texto dourado sobre branco"),
    ("--dourado-700", "--dourado-50", 4.5, "Texto dourado sobre fundo de marca"),
    ("--dourado-300", "--grafite-900", 4.5, "Papel do usuário no cabeçalho"),
    ("--verde-700", "--verde-50", 4.5, "Selo/alerta de sucesso"),
    ("--ambar-700", "--ambar-50", 4.5, "Selo/alerta de aviso"),
    ("--vermelho-700", "--vermelho-50", 4.5, "Selo/alerta de perigo"),
    ("--azul-700", "--azul-50", 4.5, "Selo/alerta de informação"),
    ("--azul-700", "--neutro-0", 4.5, "Links"),
    ("--neutro-0", "--vermelho-600", 4.5, "Botão de perigo"),
    ("--neutro-400", "--neutro-0", 3.0, "Borda de campo (--cor-borda-campo, 1.4.11)"),
    ("--neutro-500", "--neutro-0", 3.0, "Borda de caixa/rádio e marcadores de progresso"),
    ("--grafite-900", "--neutro-0", 3.0, "Anel de foco sobre superfícies claras (2.4.11/1.4.11)"),
    ("--grafite-900", "--neutro-50", 3.0, "Anel de foco sobre o fundo da página"),
    ("--dourado-300", "--grafite-900", 3.0, "Anel de foco sobre o cabeçalho"),
    ("--grafite-800", "--neutro-0", 3.0, "Borda do campo em foco"),
    ("--dourado-600", "--neutro-0", 3.0, "Indicador dourado de item ativo (não textual)"),
    ("--dourado-600", "--dourado-50", 3.0, "Indicador ativo sobre fundo de marca"),
    ("--neutro-400", "--neutro-50", 3.0, "Borda de campo sobre fundo"),
    ("--dourado-500", "--grafite-900", 3.0, "Filete dourado sob o cabeçalho"),
]


def valores() -> dict[str, str]:
    texto = TOKENS.read_text()
    return dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;", texto))


def luminancia(hexa: str) -> float:
    canais = [int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contraste(a: str, b: str) -> float:
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def tabela() -> list[tuple[str, str, float, float, str]]:
    v = valores()
    return [(t, f, round(contraste(v[t], v[f]), 2), m, uso) for t, f, m, uso in PARES]


if __name__ == "__main__":
    print("| Primeiro plano | Fundo | Contraste | Mínimo | Uso |")
    print("|---|---|---:|---:|---|")
    for t, f, c, m, uso in tabela():
        marca = "✅" if c >= m else "❌"
        print(f"| `{t}` | `{f}` | {c:.2f}:1 {marca} | {m}:1 | {uso} |")
