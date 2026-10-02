"""Copia dependências de front-end do node_modules para static/ (sem CDN).

- htmx.min.js  → static/vendor/
- Leaflet (BSD-2) → static/vendor/leaflet/ (carregado sob demanda pelo mapa do itinerário)
- axe.min.js   → tests/_vendor/ (somente testes; nunca servido)
- Inter (variável, subconjunto latino, OFL) → static/fonts/
- ícones Lucide usados pelo sistema → static/icons/sprite.svg (um único request,
  cacheável). A lista de ícones é a fonte única em ICONES abaixo.

Rodar após atualizar package.json:  npm ci && python3 scripts/vendor_assets.py
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NODE = RAIZ / "node_modules"

ICONES = sorted({
    "alert-circle", "alert-triangle", "arrow-left", "arrow-right", "arrow-up-down",
    "badge-check", "banknote", "bell", "building-2", "calendar", "calendar-days",
    "car", "check", "check-circle-2", "chevron-down", "chevron-left", "chevron-right",
    "chevrons-up-down", "circle", "circle-dot", "clipboard-list", "clock", "copy",
    "download", "ellipsis-vertical", "external-link", "eye", "eye-off", "file-check-2",
    "file-clock", "file-pen-line", "file-plus-2", "file-signature", "file-text", "files",
    "filter", "folder-open", "gauge", "history", "home", "inbox", "info", "layers",
    "layout-dashboard", "list-checks", "loader-circle", "lock", "log-out", "map",
    "map-pin", "menu", "minus", "monitor", "moon", "panel-left", "pencil", "plus",
    "printer", "route", "save", "search", "send", "settings", "shield-check",
    "shield-alert", "sliders-horizontal", "sun", "trash-2", "user", "user-round",
    "users", "x", "x-circle", "wallet", "landmark", "palette", "command", "keyboard",
    "bus", "plane", "receipt", "scale", "server-crash", "ban", "undo-2", "stamp",
    "grip-vertical", "flag", "timer", "navigation",
})


def sprite() -> str:
    simbolos = []
    for nome in ICONES:
        svg = (NODE / "lucide-static" / "icons" / f"{nome}.svg").read_text()
        corpo = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S)
        assert corpo, nome
        miolo = re.sub(r"<!--.*?-->", "", corpo.group(1), flags=re.S)
        miolo = re.sub(r"\s+", " ", miolo).strip()
        simbolos.append(f'<symbol id="i-{nome}" viewBox="0 0 24 24">{miolo}</symbol>')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        "<!-- Lucide (ISC) — gerado por scripts/vendor_assets.py -->"
        + "".join(simbolos) + "</svg>\n"
    )


def main() -> None:
    (RAIZ / "static/vendor").mkdir(parents=True, exist_ok=True)
    shutil.copy(NODE / "htmx.org/dist/htmx.min.js", RAIZ / "static/vendor/htmx.min.js")
    leaflet = RAIZ / "static/vendor/leaflet"
    leaflet.mkdir(parents=True, exist_ok=True)
    for arquivo in ("leaflet.js", "leaflet.css"):
        shutil.copy(NODE / "leaflet/dist" / arquivo, leaflet / arquivo)
    shutil.copy(NODE / "leaflet/LICENSE", leaflet / "LICENSE")
    (RAIZ / "tests/_vendor").mkdir(parents=True, exist_ok=True)
    shutil.copy(NODE / "axe-core/axe.min.js", RAIZ / "tests/_vendor/axe.min.js")
    (RAIZ / "static/icons/sprite.svg").write_text(sprite())
    (RAIZ / "static/fonts").mkdir(parents=True, exist_ok=True)
    shutil.copy(NODE / "@fontsource-variable/inter/files/inter-latin-wght-normal.woff2",
                RAIZ / "static/fonts/inter-latin-wght-normal.woff2")
    print(f"OK: htmx, Leaflet, axe-core e {len(ICONES)} ícones.")


if __name__ == "__main__":
    main()
