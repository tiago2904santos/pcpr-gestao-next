"""Evidências GET do refinamento de Viagens; intercepta qualquer POST no PREVIEW."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "docs/visual-agents/evidencias/viagens-refino-20261015"
ROTAS = {"lista": "/viagens/viagens/", "futuras": "/viagens/viagens/?aba=futuras",
         "sem-resultado": "/viagens/viagens/?q=inexistente-refino-viagens",
         "vinculada": "/viagens/viagens/1/", "basica": "/viagens/viagens/5/",
         "cancelada": "/viagens/viagens/3/", "lote": "/viagens/viagens/1/gerar-documentos/"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--etapa", default="depois")
    parser.add_argument("--telas", nargs="+", choices=list(ROTAS), default=list(ROTAS))
    args = parser.parse_args()
    relatorio = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo")
        posts = []

        def proteger(route):
            if route.request.method == "POST":
                posts.append(route.request.url)
                route.abort()
            else:
                route.continue_()

        ctx.route("**/*", proteger)
        pg = ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))
        for largura in (360, 1440):
            pg.set_viewport_size({"width": largura, "height": 900})
            pasta = PASTA / args.etapa / str(largura)
            pasta.mkdir(parents=True, exist_ok=True)
            for nome in args.telas:
                rota = ROTAS[nome]
                for tentativa in range(4):
                    try:
                        resposta = pg.goto(args.base + rota, wait_until="domcontentloaded")
                        break
                    except PlaywrightError:
                        if tentativa == 3:
                            raise
                        pg.wait_for_timeout(1000)
                assert resposta.status == 200, (rota, resposta.status)
                pg.wait_for_function(
                    "() => document.documentElement.dataset.controladores === 'prontos'")
                assert pg.locator('link[href*="css/viagens."]').count(), "Candidato não carregado"
                pg.evaluate("document.fonts.ready")
                pg.wait_for_function("""() => !document.getAnimations().some(a =>
                    a.playState === 'running' && a.effect?.getTiming().iterations !== Infinity)
                """)
                pg.screenshot(path=str(pasta / f"{nome}-topo.png"))
                if nome == "vinculada":
                    for seletor in ("#dados", "#documentos", "#conferencia", "#historico"):
                        pg.locator(seletor).evaluate("e => e.scrollIntoView({block:'start'})")
                        pg.screenshot(path=str(pasta / f"{nome}-{seletor[1:]}.png"))
                    completas = pg.locator(".viagem-conferencia__concluidas > summary")
                    if completas.count():
                        completas.click()
                        pg.locator("#conferencia").evaluate(
                            "e => e.scrollIntoView({block:'start'})")
                        pg.screenshot(path=str(pasta / "conferencia-etapas-abertas.png"))
                        completas.click()
                    pg.locator(".viagem-vinculos > summary").click()
                    pg.locator(".viagem-vinculo > summary").first.click()
                    pg.locator("#vinculos").screenshot(path=str(pasta / "vinculos-abertos.png"))
                    marcados = pg.locator('#vinculos input:checked').evaluate_all(
                        "els => els.map(e => e.name + ':' + e.value)")
                    estado = pg.locator("[data-status-salvamento]").inner_text()
                    busca = pg.locator("#buscar-vinculo-oficios")
                    busca.fill("inexistente-do-refino")
                    busca.press("Enter")
                    busca.press("Tab")
                    pg.wait_for_timeout(1800)
                    assert pg.locator("[data-status-salvamento]").inner_text() == estado
                    assert marcados == pg.locator('#vinculos input:checked').evaluate_all(
                        "els => els.map(e => e.name + ':' + e.value)")
                    pg.locator("#vinculos").screenshot(
                        path=str(pasta / "vinculos-sem-resultado.png"))
                    busca.fill("")
                    pg.locator(".viagem-vinculos > summary").click()
                if nome == "lote":
                    for seletor in ("#oficio-1", "#gerar-junto"):
                        pg.locator(seletor).evaluate("e => e.scrollIntoView({block:'start'})")
                        pg.screenshot(path=str(pasta / f"lote-{seletor[1:]}.png"))
                pg.evaluate("scrollTo(0,0)")
                pg.screenshot(path=str(pasta / f"{nome}-inteira.png"), full_page=True)
                pg.evaluate((RAIZ / "tests/_vendor/axe.min.js").read_text(encoding="utf-8")
                            + "\n;true")
                axe = pg.evaluate("""async () => {
                    const r = await axe.run(document.querySelector('main'), {runOnly: {
                        type:'tag', values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});
                    return r.violations.map(v => ({id:v.id, help:v.help,
                        alvos:v.nodes.map(n => n.target)}));
                }""")
                excesso = pg.evaluate("Math.max(0,document.documentElement.scrollWidth-innerWidth)")
                relatorio.append({"tela": nome, "largura": largura, "status": resposta.status,
                                  "overflow": excesso, "erros_js": list(erros), "axe": axe,
                                  "posts_bloqueados": list(posts)})
                print(f"{largura} {nome}: HTTP {resposta.status}; overflow={excesso}; "
                      f"axe={len(axe)}; JS={len(erros)}", flush=True)
                erros.clear()
                posts.clear()
        browser.close()
    (PASTA / f"{args.etapa}-manifesto.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    assert all(not r["overflow"] and not r["erros_js"] and not r["axe"]
               and not r["posts_bloqueados"] for r in relatorio)


if __name__ == "__main__":
    main()
