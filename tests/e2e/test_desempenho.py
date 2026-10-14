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
from playwright.sync_api import Error, Request

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
# Exceções PROVISÓRIAS (docs/quality/performance-budgets.md, "Exceções provisórias"): a
# migração visual levou o CSS das telas migradas (operacional.css) e o JS das folhas além do
# orçamento. Teto = medido em 13/10/2026 + ~3%, para segurar regressão; a meta segue sendo o
# ORCAMENTO — cada redução baixa (ou apaga) a linha daqui. Nunca suba um teto destes.
EXCECOES_PROVISORIAS: dict[str, dict[str, float]] = {
    "/viagens/": {"css_kb": 228, "css_gzip_kb": 40},
    "/viagens/oficios/": {"css_kb": 252, "css_gzip_kb": 44},
    "/viagens/oficios/?resumo={oficio_emitido}": {"css_kb": 252, "css_gzip_kb": 44},
    "/viagens/oficios/{oficio_rascunho}/editar/": {
        "html_kb": 140, "css_kb": 237, "js_kb": 164, "css_gzip_kb": 43, "js_gzip_kb": 57,
        "requisicoes": 37},
    "/viagens/roteiros/{roteiro}/editar/": {
        "css_kb": 224, "js_kb": 144, "css_gzip_kb": 40, "js_gzip_kb": 50},
}

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


def _medir_recursos(requisicoes: list[Request], terminadas: list[Request],
                    falhas: list[Request]) -> list[dict]:
    """Lê corpos concluídos fora dos callbacks, antes de qualquer outra navegação.

    Cada entrada representa uma requisição, inclusive repetições da mesma URL. Não
    deduplicamos URLs: downloads repetidos na navegação/interação também custam rede.
    Erros ficam no relatório e reprovam a coleta; nunca viram uma medição menor aprovada.
    """
    recursos = []
    for request in requisicoes:
        recurso = {"url": request.url, "tipo": request.resource_type,
                   "metodo": request.method, "status": None, "tamanho": 0,
                   "fonte_bytes": 0, "gzip": 0, "server_timing": "",
                   "itinerario": bool(ITINERARIO.search(request.url))}
        try:
            if request in falhas:
                recurso["erro"] = request.failure or "Requisição falhou sem motivo informado."
            elif request not in terminadas:
                recurso["erro"] = "Requisição ainda não terminou ao encerrar a coleta."
            else:
                resposta = request.response()
                if resposta is None:
                    recurso["erro"] = "Requisição concluída sem resposta."
                else:
                    recurso["status"] = resposta.status
                    recurso["server_timing"] = resposta.headers.get("server-timing", "")
                    if resposta.status >= 400:
                        recurso["erro"] = f"Resposta HTTP {resposta.status}."
                    if request.resource_type == "font" and not recurso["itinerario"]:
                        # Chromium pode descartar o body de uma fonte já reutilizada por
                        # outros documentos. Fontes contam como requisições, mas não têm
                        # orçamento de conteúdo/minificação/gzip. Não fingir tamanho zero.
                        recurso.update(tamanho=None, fonte_bytes=None, gzip=None,
                                       medicao_conteudo="Não aplicável ao orçamento: body de "
                                       "fonte não lido; bytes de rede medidos separadamente.")
                        recurso["rede_tamanhos"] = request.sizes()
                        recursos.append(recurso)
                        continue
                    corpo = resposta.body() if resposta.status < 300 else b""
                    recurso["fonte_bytes"] = len(corpo)
                    # Mesmo tratamento do collectstatic: o teste serve fontes comentados.
                    if corpo and request.resource_type in ("stylesheet", "script"):
                        pronto = minificar(request.url.split("?")[0], corpo.decode("utf-8"))
                        corpo = corpo if pronto is None else pronto.encode("utf-8")
                    recurso["tamanho"] = len(corpo)
                    recurso["gzip"] = len(gzip.compress(corpo, 6)) if corpo else 0
        except Error as exc:
            # Preserva diagnóstico específico do Playwright, mas a asserção abaixo falha.
            recurso["erro"] = str(exc)
        recursos.append(recurso)
    return recursos


@pytest.mark.parametrize("rota", ROTAS)
def test_orcamento_de_desempenho(logado, dados_e2e, rota):
    pg = logado
    url = resolver(rota, dados_e2e.ids)
    relatorio = f"desempenho-{url.strip('/').replace('/', '_') or 'raiz'}.json"
    requisicoes: list[Request] = []
    terminadas: list[Request] = []
    falhas: list[Request] = []
    # Drena a entrada da fixture antes de delimitar a navegação medida. Callbacks só
    # guardam referências: body() dentro de response pode continuar pendente no goto
    # das amostras seguintes, perdendo o identificador do recurso no Chromium.
    pg.wait_for_load_state("networkidle")
    # Playwright anota o handler com metadados; métodos nativos de list não aceitam
    # esses atributos. As funções também preservam a mesma referência na remoção.
    listeners = {"request": lambda r: requisicoes.append(r),
                 "requestfinished": lambda r: terminadas.append(r),
                 "requestfailed": lambda r: falhas.append(r)}
    for evento, callback in listeners.items():
        pg.on(evento, callback)
    try:
        pg.add_init_script(f"({OBSERVADORES})()")
        pg.goto(url, wait_until="networkidle")
        # Interação real para INP: menu do usuário e, na lista, resumo de um registro.
        if pg.locator("dialog:modal").count():  # fecha a janela aberta pela URL (resto inerte)
            pg.keyboard.press("Escape")
            pg.wait_for_function("() => !document.querySelector('dialog:modal')")
        pg.click(".perfil")
        pg.keyboard.press("Escape")
        janela = pg.locator("#dialogo-resumo")
        if (janela.count() and not janela.evaluate("d => d.open")
                and pg.locator(".registro__link").count()):
            pg.locator(".registro__link").first.click()
            pg.wait_for_selector("#dialogo-resumo[open] .resumo")
        pg.wait_for_timeout(200)
        pg.wait_for_load_state("networkidle")
        nav = pg.evaluate("""() => { const n = performance.getEntriesByType('navigation')[0];
            const fcp = performance.getEntriesByName('first-contentful-paint')[0];
            return {ttfb: n.responseStart - n.requestStart, fcp: fcp ? fcp.startTime : 0,
                    lcp: window.__lcp, cls: window.__cls, inp: window.__inp}; }""")
    finally:
        for evento, callback in listeners.items():
            pg.remove_listener(evento, callback)
    recursos = _medir_recursos(requisicoes, terminadas, falhas)
    salvar_relatorio(f"recursos-{relatorio}", {"rota": url,
                     "escopo": "Uma navegação e as interações, antes das amostras de servidor.",
                     "recursos": recursos})
    erros = [{"url": r["url"], "erro": r["erro"]} for r in recursos if "erro" in r]
    assert not erros, f"{url}: coleta de recursos incompleta: {erros}"
    todos_recursos = recursos
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
    medido["recursos"] = todos_recursos
    salvar_relatorio(relatorio, medido)
    orcamento = dict(ORCAMENTO)
    if FOLHAS_DE_EDICAO.search(url):
        orcamento["requisicoes"] = REQUISICOES_FOLHA
    orcamento.update(EXCECOES_PROVISORIAS.get(rota, {}))
    estourados = {k: (v, orcamento[k]) for k, v in medido.items()
                  if k in orcamento and v > orcamento[k]}
    assert not estourados, f"{url}: orçamento estourado {estourados}"
