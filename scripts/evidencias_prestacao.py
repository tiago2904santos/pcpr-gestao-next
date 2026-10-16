"""Capturas e verificações GET da prestação; nenhuma submissão no PREVIEW."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "docs/visual-agents/evidencias/prestacao-refino-20261015"
ROTAS = {
    "lista": "/viagens/prestacoes/",
    "liberadas": "/viagens/prestacoes/?aba=liberadas",
    "finalizadas": "/viagens/prestacoes/?aba=finalizados",
    "sem-resultado": "/viagens/prestacoes/?q=refino-inexistente-999999",
    "diario": "/viagens/prestacoes/equipe/211/diario/",
    "relatorio": "/viagens/prestacoes/equipe/211/relatorio/",
    "documentos": "/viagens/prestacoes/equipe/211/documentos/",
    "catalogo": "/ui-lab/",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--etapa", default="depois")
    parser.add_argument("--telas", nargs="+", choices=list(ROTAS), default=list(ROTAS))
    args = parser.parse_args()
    registros = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo",
                                  reduced_motion="reduce")
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
                resposta = pg.goto("http://127.0.0.1:8000" + ROTAS[nome],
                                   wait_until="domcontentloaded")
                assert resposta.status == 200, (nome, resposta.status)
                pg.wait_for_function(
                    "() => document.documentElement.dataset.controladores === 'prontos'")
                pg.evaluate("document.fonts.ready")
                pg.wait_for_function("""() => !document.getAnimations().some(a =>
                    a.playState === 'running' && a.effect?.getTiming().iterations !== Infinity)
                """)
                if nome == "catalogo":
                    pg.locator("#equipe-prestacao").evaluate("""e => scrollTo({
                        top:e.getBoundingClientRect().top+scrollY-80,behavior:'instant'})""")
                    pg.screenshot(path=str(pasta / "catalogo.png"))
                else:
                    pg.screenshot(path=str(pasta / f"{nome}-topo.png"))
                    pg.screenshot(path=str(pasta / f"{nome}-inteira.png"), full_page=True)
                pg.evaluate((RAIZ / "tests/_vendor/axe.min.js").read_text(encoding="utf-8")
                            + "\n;true")
                axe = pg.evaluate("""async seletor => {
                    const r = await axe.run(document.querySelector(seletor), {runOnly: {
                        type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});
                    return r.violations.map(v => ({id:v.id,alvos:v.nodes.map(n=>n.target)}));
                }""", "#equipe-prestacao" if nome == "catalogo" else "main")
                excesso_pagina = pg.evaluate(
                    "Math.max(0,document.documentElement.scrollWidth-innerWidth)")
                excesso = (pg.locator("#equipe-prestacao").evaluate("""e => Math.max(0,
                    e.scrollWidth-e.clientWidth,e.getBoundingClientRect().right-innerWidth)""")
                    if nome == "catalogo" else excesso_pagina)
                registros.append({"tela": nome, "largura": largura, "http": resposta.status,
                                  "overflow": excesso, "axe": axe, "js": list(erros),
                                  "posts": list(posts), "overflow_pagina": excesso_pagina,
                                  "extravasados": pg.evaluate("""() =>
                                    [...document.querySelectorAll('main *')].filter(e => {
                                      const r=e.getBoundingClientRect();
                                      return r.width && r.right > innerWidth+1;
                                    }).slice(0,15).map(e=>({tag:e.tagName,id:e.id,
                                      classe:e.className?.baseVal ?? e.className}))
                                  """) if excesso else []})
                print(f"{largura} {nome}: HTTP {resposta.status}, overflow {excesso}, "
                      f"axe {len(axe)}, JS {len(erros)}", flush=True)
                secoes = {"diario": ["#motorista", "#realizada", "#conferencia"],
                          "relatorio": ["#custeio", "#diarias", "#documentos"],
                          "documentos": ["#servidores > article:first-of-type", "#anteriores"]}
                for indice, seletor in enumerate(secoes.get(nome, [])):
                    pg.locator(seletor).screenshot(path=str(pasta / f"{nome}-secao-{indice}.png"))
                gatilho = None
                if nome == "lista":
                    pendencias = pg.locator('form[data-autosave] details.divulgacao').first
                    if pendencias.count():
                        pendencias.locator("summary").click()
                        pendencias.screenshot(path=str(pasta / "lista-pendencias.png"))
                        pendencias.locator("summary").click()
                    gatilho = pg.locator('article a[hx-target="#resumo-dialogo"]').first
                elif nome == "finalizadas":
                    envios = pg.locator('button[data-abrir-dialogo^="envio-"]')
                    if envios.count():
                        gatilho = envios.first
                if gatilho:
                    gatilho.click()
                    dialogo = pg.locator("dialog[open]")
                    if nome == "lista":
                        dialogo.locator(".registro-hero").wait_for()
                    pg.screenshot(path=str(pasta / f"{nome}-dialogo.png"))
                    extras = pg.evaluate("""async () => {
                        const r=await axe.run(document.querySelector('dialog[open]'),{runOnly:{
                          type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});
                        return r.violations.map(v=>({id:v.id,alvos:v.nodes.map(n=>n.target)}));
                    }""")
                    registros.append({"tela": nome + "-dialogo", "largura": largura,
                                      "http": resposta.status, "overflow": pg.evaluate(
                                          "Math.max(0,document.documentElement.scrollWidth-innerWidth)"),
                                      "axe": extras, "js": list(erros), "posts": list(posts)})
                    dialogo.locator("[data-fechar-dialogo]").first.click()
                erros.clear()
                posts.clear()
        browser.close()
    (PASTA / f"{args.etapa}-manifesto.json").write_text(
        json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8")
    assert all(not r["overflow"] and not r["axe"] and not r["js"] and not r["posts"]
               for r in registros)


if __name__ == "__main__":
    main()
