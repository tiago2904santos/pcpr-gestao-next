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

from gestao.plataforma.estaticos import minificar

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

# Folhas de edição usam quase todos os componentes (módulos ES sem empacotador, ADR 0002).
# Decisão D8: teto até 40, condicionado à validação. Validado em 03/10/2026 (rede emulada,
# docs/quality/performance-budgets.md): a folha precisa de 30; o teto fica em 32 (medido +
# margem), mais estrito que os 40 autorizados. Peso e tempo seguem o orçamento geral.
FOLHAS_DE_EDICAO = re.compile(r"/(oficios|roteiros)/\d+/editar/")
REQUISICOES_FOLHA = 32

ITINERARIO = re.compile(r"/vendor/leaflet/|/itinerario\.(css|js)|/api/rota/")

# A leitura de um ofício é a janela de resumo na lista (não há página de detalhe).
ROTAS = ["/", "/viagens/", "/viagens/oficios/",
         "/viagens/oficios/?resumo={oficio_emitido}", "/viagens/oficios/{oficio_rascunho}/editar/",
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


# Tempo de servidor e de banco são tempo de relógio: com a suíte em paralelo (4 navegadores e
# um Postgres na mesma máquina) uma amostra só estoura por disputa de CPU. Mede-se 3 vezes e
# vale a mediana; o número de consultas (determinístico — o sinal de regressão de verdade)
# vale em TODAS as amostras.
AMOSTRAS = 3


def _amostra_do_servidor(pg, url: str) -> tuple[float, float, int]:
    resposta = pg.goto(url, wait_until="domcontentloaded")
    timing = (resposta.headers.get("server-timing", "") if resposta else "") or ""
    ttfb = pg.evaluate("() => { const n = performance.getEntriesByType('navigation')[0];"
                       " return n.responseStart - n.requestStart; }")
    db = float(re.search(r"db;dur=([\d.]+)", timing).group(1)) if "db;dur" in timing else 0.0
    sql = int(re.search(r'"(\d+) consultas"', timing).group(1)) if "consultas" in timing else 0
    return ttfb, db, sql


@pytest.mark.parametrize("rota", ROTAS)
def test_orcamento_de_desempenho(logado, dados_e2e, rota):
    pg = logado
    url = resolver(rota, dados_e2e.ids)
    recursos: list[dict] = []
    def anotar(r):
        corpo = (r.body() or b"") if r.status < 300 else b""
        # Em produção CSS e JS saem minificados do collectstatic (gestao/plataforma/
        # estaticos.py); o servidor de teste serve os fontes comentados — mede-se o que o
        # usuário recebe em produção.
        if corpo and r.request.resource_type in ("stylesheet", "script"):
            pronto = minificar(r.url.split("?")[0], corpo.decode("utf-8"))
            corpo = corpo if pronto is None else pronto.encode("utf-8")
        recursos.append({"url": r.url, "tipo": r.request.resource_type, "tamanho": len(corpo),
                         "gzip": len(gzip.compress(corpo, 6)) if corpo else 0,
                         "server_timing": r.headers.get("server-timing", "")})
    pg.on("response", anotar)
    pg.add_init_script(f"({OBSERVADORES})()")
    pg.goto(url, wait_until="networkidle")
    # Interação real para INP: abre e fecha o menu do usuário; na lista, expande um registro.
    if pg.locator("dialog:modal").count():  # janela aberta pela URL: fecha antes (resto inerte)
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('dialog:modal')")
    pg.click(".perfil")
    pg.keyboard.press("Escape")
    janela = pg.locator("#dialogo-resumo")
    if janela.count() and not janela.evaluate("d => d.open") and pg.locator(".registro__link").count():
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
    amostras = [(medido["ttfb_ms"], db_ms, sql)]
    amostras += [_amostra_do_servidor(pg, url) for _ in range(AMOSTRAS - 1)]
    medido["ttfb_ms"] = round(sorted(a[0] for a in amostras)[len(amostras) // 2])
    medido["db_ms"] = round(sorted(a[1] for a in amostras)[len(amostras) // 2], 1)
    medido["sql"] = max(a[2] for a in amostras)
    medido["amostras"] = [[round(a[0]), round(a[1], 1), a[2]] for a in amostras]
    salvar_relatorio(f"desempenho-{url.strip('/').replace('/', '_') or 'raiz'}.json", medido)
    orcamento = dict(ORCAMENTO)
    if FOLHAS_DE_EDICAO.search(url):
        orcamento["requisicoes"] = REQUISICOES_FOLHA
    estourados = {k: (v, orcamento[k]) for k, v in medido.items()
                  if k in orcamento and v > orcamento[k]}
    assert not estourados, f"{url}: orçamento estourado {estourados}"
