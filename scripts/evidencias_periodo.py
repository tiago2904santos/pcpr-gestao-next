"""Validação/capturas da propagação do calendário, sem gravar registros no PREVIEW.

Uso: uv run python scripts/evidencias_periodo.py
As interações de edição têm POST interceptado; capturas refletem GETs reais.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
BASE = os.environ.get("CAPTURA_BASE", "http://127.0.0.1:8000")
SAIDA = RAIZ / "docs/visual-agents/evidencias/periodo-propagacao-20261014/depois/1440"
ROTAS = [
    ("viagem", "/viagens/viagens/1/", "#viagem-periodo", "viagem"),
    ("ordem", "/viagens/ordens/2/", "#ordem-periodo", "viagem"),
    ("plano", "/viagens/planos/1/", "#plano-periodo", "evento"),
    ("evento-plano", "/viagens/planos/1/?evento=novo", "#evento-periodo", "evento"),
    ("termo", "/viagens/termos/8/", "#termo-periodo", "evento"),
    ("eventos", "/eventos/solicitacoes/nova/", "#solicitacao-evento-periodo", "evento"),
    ("palestras", "/palestras/pedidos/nova/", "#palestra-periodo", "evento"),
]


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        contexto = browser.new_context(viewport={"width": 1440, "height": 900},
                                       locale="pt-BR", timezone_id="America/Sao_Paulo")
        pagina = contexto.new_page()
        erros: list[str] = []
        pagina.on("pageerror", lambda e: erros.append(str(e)))
        def abrir(rota):
            for tentativa in range(3):
                try:
                    return pagina.goto(BASE + rota, wait_until="networkidle")
                except PlaywrightError as exc:
                    if "ERR_EMPTY_RESPONSE" not in str(exc) or tentativa == 2:
                        raise
                    pagina.wait_for_timeout(2000)
            return None

        abrir("/conta/entrar/")
        pagina.fill("#id_username", os.environ.get("CAPTURA_LOGIN", "operador"))
        pagina.fill("#id_password", os.environ.get("CAPTURA_SENHA", "senha-local-123"))
        pagina.click("button[type=submit]")
        pagina.wait_for_load_state("networkidle")

        def proteger_post(route):
            if route.request.method != "POST":
                route.continue_()
            elif "/autosave/" in route.request.url:
                route.fulfill(json={"salvo": False, "mensagem": "Validação sem gravação."})
            else:
                route.abort()

        contexto.route("**/*", proteger_post)
        escolhidas = set(os.environ.get("PERIODO_PAGINAS", "").split(",")) - {""}
        for nome, rota, seletor, natureza in ROTAS:
            if escolhidas and nome not in escolhidas:
                continue
            resposta = abrir(rota)
            assert resposta and resposta.status == 200, (
                nome, resposta.status if resposta else None)
            periodo = pagina.locator(seletor)
            card = periodo.locator("xpath=ancestor::*[@data-resumo-periodo][1]")
            botao = card.locator(".mesa-evento__botao")
            assert periodo.count() == 1
            assert card.locator("[data-periodo-de]").count() == 1
            assert card.locator("[data-periodo-ate]").count() == 1
            assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
            ids = pagina.locator("[data-resumo-periodo] [id]").evaluate_all(
                "els => els.map(el => el.id)")
            assert len(ids) == len(set(ids)), (nome, "IDs do componente duplicados")
            card.evaluate('el => el.scrollIntoView({block:"center"})')
            pagina.wait_for_timeout(350)
            pagina.screenshot(path=str(SAIDA / f"{nome}.png"))
            altura = card.bounding_box()["height"]
            assert altura < 130, (nome, altura)
            if botao.is_enabled():
                nomes = card.locator("input[name]").evaluate_all("els => els.map(el => el.name)")
                botao.click()
                painel = card.locator(".calendario")
                painel.wait_for(state="visible")
                assert painel.locator('td[tabindex="0"]').evaluate(
                    "el => el === document.activeElement")
                pagina.keyboard.press("Escape")
                assert botao.evaluate("el => el === document.activeElement")
                pagina.keyboard.press("Enter")
                painel.wait_for(state="visible")
                pagina.keyboard.press("Enter")
                assert painel.is_visible()
                assert painel.locator('td[tabindex="0"]').evaluate(
                    "el => el === document.activeElement")
                pagina.keyboard.press("ArrowRight")
                pagina.keyboard.press("Enter")
                assert not painel.is_visible()
                assert botao.evaluate("el => el === document.activeElement")
                assert card.locator(".mesa-evento__duracao").inner_text() == f"2 dias de {natureza}"
                assert card.locator(".mesa-evento__folha").count() == 2
                assert "Informado no calendário" in card.inner_text()
                assert nomes == card.locator("input[name]").evaluate_all(
                    "els => els.map(el => el.name)")
                botao.click()
                painel.get_by_role("button", name="Limpar", exact=True).click()
                assert card.locator(".mesa-evento__antecedencia strong").inner_text() == "—"
            print(json.dumps({"pagina": nome, "rota": rota, "altura": round(altura, 1),
                              "captura": f"{nome}.png", "interacao": "OK"},
                             ensure_ascii=False), flush=True)

        abrir("/ui-lab/")
        pagina.locator("#termo-lab").evaluate('el => el.scrollIntoView({block:"start"})')
        pagina.screenshot(path=str(SAIDA / "ui-lab-periodo.png"))
        pagina.locator("#periodo-estados-lab").evaluate('el => el.scrollIntoView({block:"center"})')
        pagina.screenshot(path=str(SAIDA / "ui-lab-estados.png"))
        consulta = pagina.locator("#lab-periodo-consulta-periodo").locator("..")
        assert consulta.locator("button").is_disabled()
        hoje = pagina.locator("#lab-periodo-hoje-periodo-resumo .mesa-evento__antecedencia strong")
        assert hoje.inner_text() == "0"
        assert pagina.locator("#lab-periodo-erro-periodo-erros").count() == 1
        # Mesmo carregamento diagnóstico usado em tests/e2e/conftest.py (CSP preservada).
        pagina.evaluate((RAIZ / "tests/_vendor/axe.min.js").read_text() + "\n;true")
        violacoes = pagina.evaluate("""async () => {
          const areas = [...document.querySelectorAll('[data-resumo-periodo]')];
          const r = await axe.run({include: areas}, {runOnly: ['wcag2a','wcag2aa','wcag21aa']});
          return r.violations.map(v => ({id:v.id, impact:v.impact, help:v.help}));
        }""")
        graves = [v for v in violacoes if v["impact"] in {"serious", "critical"}]
        assert not graves, graves
        assert not erros, erros
        print(json.dumps({"ui_lab": "OK", "axe": violacoes, "erros_js": erros,
                          "gravacoes_reais": 0, "viewport": "1440x900"},
                         ensure_ascii=False), flush=True)
        contexto.close()
        browser.close()


if __name__ == "__main__":
    main()
