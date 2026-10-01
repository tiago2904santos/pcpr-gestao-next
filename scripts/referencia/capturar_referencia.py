"""Captura telas do SISTEMA DE REFERÊNCIA em modo somente leitura.

- Credenciais apenas por ambiente: REF_USER, REF_PASS (REF_BASE_URL opcional).
  Nunca grave credenciais em arquivo versionado.
- Só faz GET. Recusa rotas com cara de ação (excluir, emitir, gerar, enviar…).
- Saída: artifacts/referencia/<largura>/<rota>.png (diretório ignorado pelo Git).

Uso:
  REF_USER=... REF_PASS=... uv run python scripts/referencia/capturar_referencia.py \
      /viagens/oficios/ /viagens/oficios/161/editar/ --larguras 1440,390
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
ACOES = re.compile(
    r"(excluir|delete|apagar|remov|sair|logout|cancel|emitir|gerar|baixar|download|enviar|"
    r"aprovar|assinar|duplic|reabrir|devolver|deferir|finaliz|concluir|ativar|desativar|"
    r"export|importar|sincron|reset|senha|abrir|marcar|anexar|publicar|protocol)", re.I)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("rotas", nargs="+")
    p.add_argument("--larguras", default="1440")
    a = p.parse_args()
    base = os.environ.get("REF_BASE_URL", "https://eventos.gerenciadorviagens.tech")
    usuario, senha = os.environ.get("REF_USER"), os.environ.get("REF_PASS")
    if not usuario or not senha:
        print("Defina REF_USER e REF_PASS no ambiente (não em arquivo).", file=sys.stderr)
        return 2
    bloqueadas = [r for r in a.rotas if ACOES.search(r)]
    if bloqueadas:
        print(f"Recusado (parece ação, não leitura): {bloqueadas}", file=sys.stderr)
        return 2
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        ctx = navegador.new_context(viewport={"width": 1440, "height": 900}, locale="pt-BR")
        pg = ctx.new_page()
        pg.route("**/*", lambda rota: rota.abort() if rota.request.method != "GET"
                 and "/conta/entrar/" not in rota.request.url else rota.continue_())
        pg.goto(f"{base}/conta/entrar/")
        pg.fill("#id_username", usuario)
        pg.fill("#id_password", senha)
        pg.click("button[type=submit]")
        pg.wait_for_load_state("networkidle")
        for largura in [int(x) for x in a.larguras.split(",")]:
            pg.set_viewport_size({"width": largura, "height": 900})
            for rota in a.rotas:
                pg.goto(f"{base}{rota}", wait_until="networkidle")
                nome = re.sub(r"[^a-z0-9]+", "-", rota.lower()).strip("-") or "raiz"
                destino = RAIZ / "artifacts" / "referencia" / str(largura) / f"{nome}.png"
                destino.parent.mkdir(parents=True, exist_ok=True)
                pg.screenshot(path=str(destino), full_page=True)
                print(f"{largura:>5} {rota} → {destino.relative_to(RAIZ)}")
        navegador.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
