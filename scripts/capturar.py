"""Captura telas do sistema NOVO em várias larguras (ferramenta do agente e do time).

Uso:
  uv run python scripts/capturar.py /ui-lab/ /viagens/oficios/ --larguras 360,1440
  uv run python scripts/capturar.py /conta/entrar/ --anonimo

Credenciais vêm de CAPTURA_LOGIN / CAPTURA_SENHA (padrão: usuário de DEV criado por
`manage.py semear_dev`). Saída em artifacts/capturas/<largura>/<rota>.png.
Também reporta rolagem horizontal (overflow), o erro de layout mais comum.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
LARGURAS_PADRAO = [360, 390, 768, 1024, 1280, 1440]


def nome_arquivo(rota: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", rota.lower()).strip("-") or "raiz"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("rotas", nargs="+")
    p.add_argument("--base", default=os.environ.get("CAPTURA_BASE", "http://127.0.0.1:8000"))
    p.add_argument("--larguras", default=",".join(map(str, LARGURAS_PADRAO)))
    p.add_argument("--anonimo", action="store_true")
    p.add_argument("--pagina-inteira", action="store_true")
    p.add_argument("--saida", default=str(RAIZ / "artifacts" / "capturas"))
    a = p.parse_args()
    larguras = [int(x) for x in a.larguras.split(",")]
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        contexto = navegador.new_context(viewport={"width": 1440, "height": 900}, locale="pt-BR",
                                          timezone_id="America/Sao_Paulo")
        pagina = contexto.new_page()
        if not a.anonimo:
            pagina.goto(f"{a.base}/conta/entrar/")
            pagina.fill("#id_username", os.environ.get("CAPTURA_LOGIN", "operador"))
            pagina.fill("#id_password", os.environ.get("CAPTURA_SENHA", "senha-local-123"))
            pagina.click("button[type=submit]")
            pagina.wait_for_load_state("networkidle")
        for largura in larguras:
            pagina.set_viewport_size({"width": largura, "height": 900})
            for rota in a.rotas:
                pagina.goto(f"{a.base}{rota}", wait_until="networkidle")
                destino = Path(a.saida) / str(largura) / f"{nome_arquivo(rota)}.png"
                destino.parent.mkdir(parents=True, exist_ok=True)
                pagina.screenshot(path=str(destino), full_page=a.pagina_inteira)
                excesso = pagina.evaluate(
                    "document.documentElement.scrollWidth - window.innerWidth"
                )
                aviso = f"  ⚠ rolagem horizontal: {excesso}px" if excesso > 0 else ""
                exibido = destino.relative_to(RAIZ) if destino.is_relative_to(RAIZ) else destino
                print(f"{largura:>5} {rota} → {exibido}{aviso}")
        navegador.close()


if __name__ == "__main__":
    main()
