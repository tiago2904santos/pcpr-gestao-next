"""Fase 13: orçamentos de desempenho medidos no navegador real.

Métricas: TTFB, FCP, LCP, CLS, INP (aproximado por Event Timing num clique real),
bytes de HTML/CSS/JS (sem compressão no servidor de teste) e CSS/JS comprimidos (gzip -6, o
que o WhiteNoise serve em produção),
número de requisições, consultas SQL e tempo de banco (Server-Timing).
Resultado gravado em artifacts/desempenho.json. Orçamentos em
docs/quality/performance-budgets.md.
"""

from __future__ import annotations

import gzip
import re

import pytest

from .conftest import salvar_relatorio
from .rotas import resolver

pytestmark = pytest.mark.perf

ORCAMENTO = {
    "ttfb_ms": 300, "fcp_ms": 1200, "lcp_ms": 1800, "cls": 0.05, "inp_ms": 200,
    "html_kb": 120, "css_kb": 140, "css_gzip_kb": 30, "js_kb": 130, "js_gzip_kb": 45,
    "requisicoes": 25,
    # Itinerário com mapa (ADR 0016): só nas telas que editam itinerário, depois da primeira
    # pintura (Leaflet sob demanda). Orçamento próprio para não esconder o do resto da tela.
    "itinerario_gzip_kb": 64, "itinerario_requisicoes": 6,
    "sql": 25, "db_ms": 80,
}

ITINERARIO = re.compile(r"/vendor/leaflet/|/itinerario\.(css|js)|/api/rota/")

ROTAS = ["/", "/viagens/", "/viagens/oficios/",
         "/viagens/oficios/{oficio_emitido}/", "/viagens/oficios/{oficio_rascunho}/editar/",
         "/viagens/roteiros/{roteiro}/editar/"]

OBSERVADORES = """() => {
  window.__lcp = 0; window.__cls = 0; window.__inp = 0;
  new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lcp = e.startTime; })
    .observe({type: 'largest-contentful-paint', buffered: true});
  new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
    .observe({type: 'layout-shift', buffered: true});
  new PerformanceObserver(l => { for (const e of l.getEntries()) window.__inp = Math.max(window.__inp, e.duration); })
    .observe({type: 'event', buffered: true, durationThreshold: 16});
}"""


@pytest.mark.parametrize("rota", ROTAS)
def test_orcamento_de_desempenho(logado, dados_e2e, rota):
    pg = logado
    url = resolver(rota, dados_e2e.ids)
    recursos: list[dict] = []
    def anotar(r):
        corpo = (r.body() or b"") if r.status < 300 else b""
        recursos.append({"url": r.url, "tipo": r.request.resource_type, "tamanho": len(corpo),
                         "gzip": len(gzip.compress(corpo, 6)) if corpo else 0,
                         "server_timing": r.headers.get("server-timing", "")})
    pg.on("response", anotar)
    pg.add_init_script(f"({OBSERVADORES})()")
    pg.goto(url, wait_until="networkidle")
    # Interação real para INP: abre e fecha o menu do usuário; na lista, expande um registro.
    pg.click(".perfil")
    pg.keyboard.press("Escape")
    if pg.locator(".registro__link").count():
        pg.locator(".registro__link").first.click()
        pg.wait_for_selector("#dialogo-resumo[open] .resumo")
    pg.wait_for_timeout(200)
    nav = pg.evaluate("""() => { const n = performance.getEntriesByType('navigation')[0];
        const fcp = performance.getEntriesByName('first-contentful-paint')[0];
        return {ttfb: n.responseStart - n.requestStart, fcp: fcp ? fcp.startTime : 0,
                lcp: window.__lcp, cls: window.__cls, inp: window.__inp}; }""")
    doc = next(r for r in recursos if r["tipo"] == "document")
    timing = doc["server_timing"]
    sql = int(re.search(r'"(\d+) consultas"', timing).group(1)) if "consultas" in timing else 0
    db_ms = float(re.search(r"db;dur=([\d.]+)", timing).group(1)) if "db;dur" in timing else 0.0

    itinerario = [r for r in recursos if ITINERARIO.search(r["url"])]
    recursos = [r for r in recursos if not ITINERARIO.search(r["url"])]

    def kb(tipo: str) -> float:
        return round(sum(r["tamanho"] for r in recursos if r["tipo"] == tipo) / 1024, 1)

    medido = {
        "ttfb_ms": round(nav["ttfb"]), "fcp_ms": round(nav["fcp"]), "lcp_ms": round(nav["lcp"]),
        "cls": round(nav["cls"], 3), "inp_ms": round(nav["inp"]),
        "html_kb": kb("document"), "css_kb": kb("stylesheet"), "js_kb": kb("script"),
        "css_gzip_kb": round(sum(r["gzip"] for r in recursos
                                 if r["tipo"] == "stylesheet") / 1024, 1),
        "js_gzip_kb": round(sum(r["gzip"] for r in recursos if r["tipo"] == "script") / 1024, 1),
        "requisicoes": len(recursos), "sql": sql, "db_ms": db_ms,
        "itinerario_gzip_kb": round(sum(r["gzip"] for r in itinerario) / 1024, 1),
        "itinerario_requisicoes": len(itinerario),
    }
    salvar_relatorio(f"desempenho-{url.strip('/').replace('/', '_') or 'raiz'}.json", medido)
    estourados = {k: (v, ORCAMENTO[k]) for k, v in medido.items() if v > ORCAMENTO[k]}
    assert not estourados, f"{url}: orçamento estourado {estourados}"
