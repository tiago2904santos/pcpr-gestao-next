"""Captura Planos no PREVIEW sem gravar dados; GETs e controles de apresentação.

Uso: uv run python scripts/evidencias_planos.py --etapa depois
As telas completas e recortes por seção complementam a captura inicial dos módulos.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "docs/visual-agents/evidencias/planos-refino-20261015"
ROTAS = {
    "lista": "/viagens/planos/",
    "novo": "/viagens/planos/novo/",
    "gerado": "/viagens/planos/1/",
    "incompleto": "/viagens/planos/4/",
    "cancelado": "/viagens/planos/3/",
    "evento": "/viagens/planos/1/?evento=novo",
    "resultados": "/viagens/planos/1/resultados/",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--etapa", default="depois")
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    relatorio = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo")
        pg = ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))

        def proteger(route):
            if route.request.method == "POST":
                route.abort()
            else:
                route.continue_()

        ctx.route("**/*", proteger)
        for largura in (360, 1440):
            pg.set_viewport_size({"width": largura, "height": 900})
            pasta = SAIDA / args.etapa / str(largura)
            pasta.mkdir(parents=True, exist_ok=True)
            for nome, rota in ROTAS.items():
                for tentativa in range(6):
                    try:
                        resposta = pg.goto(args.base + rota, wait_until="domcontentloaded")
                        break
                    except PlaywrightError:
                        if tentativa == 5:
                            raise
                        pg.wait_for_timeout(1500)
                assert resposta.status == 200, (rota, resposta.status)
                pg.wait_for_function(
                    "() => document.documentElement.dataset.controladores === 'prontos'")
                pg.evaluate("document.fonts.ready")
                pg.evaluate("""async () => {
                    await Promise.all(document.getAnimations().filter(a =>
                        a.effect?.getTiming().iterations !== Infinity
                    ).map(a => a.finished.catch(() => {})));
                }""")
                pg.screenshot(path=str(pasta / f"{nome}-topo.png"))
                # O editor usa carregamento adiado: a captura integral só vale após vê-lo.
                previa = pg.locator("#previa")
                if previa.count():
                    previa.scroll_into_view_if_needed()
                    pg.wait_for_timeout(1200)
                if nome == "gerado":
                    for seletor in ("#t-coord", "#efetivo", "#atividades", "#eventos", "#previa"):
                        pg.locator(seletor).evaluate("e => e.scrollIntoView({block:'start'})")
                        pg.wait_for_timeout(250)
                        pg.screenshot(path=str(pasta / f"{nome}-{seletor[1:]}.png"))
                if nome == "evento":
                    dialogo = pg.locator("#dialogo-evento")
                    dialogo.wait_for(state="visible")
                    pg.screenshot(path=str(pasta / "evento-dialogo-topo.png"))
                    dialogo.locator(".dialogo__rodape").scroll_into_view_if_needed()
                    pg.screenshot(path=str(pasta / "evento-dialogo-rodape.png"))
                pg.evaluate("scrollTo(0,0)")
                pg.wait_for_timeout(250)
                pg.screenshot(path=str(pasta / f"{nome}-inteira.png"), full_page=True)
                excesso = pg.evaluate("Math.max(0,document.documentElement.scrollWidth-innerWidth)")
                violacoes = []
                if nome in {"lista", "novo", "gerado", "evento"}:
                    pg.evaluate((RAIZ / "tests/_vendor/axe.min.js").read_text(encoding="utf-8")
                                + "\n;true")
                    violacoes = pg.evaluate("""async () => {
                        const modal = document.querySelector('dialog:modal');
                        const include = modal ? [modal] : [...document.querySelectorAll(
                            '.plano-coordenacoes, #atividades, #efetivo, .colecao-planos')];
                        const r = await axe.run({include}, {runOnly: {
                            type:'tag', values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});
                        return r.violations.map(v => ({id:v.id, help:v.help,
                            alvos:v.nodes.map(n => n.target)}));
                    }""")
                relatorio.append({"tela": nome, "largura": largura, "status": resposta.status,
                                  "overflow": excesso, "erros_js": list(erros),
                                  "axe_componentes": violacoes})
                print(f"{largura} {nome}: HTTP {resposta.status}, overflow={excesso}", flush=True)
                erros.clear()
        browser.close()
    (SAIDA / f"{args.etapa}-manifesto.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    assert all(not r["overflow"] and not r["erros_js"] and not r["axe_componentes"]
               for r in relatorio), relatorio


if __name__ == "__main__":
    main()
