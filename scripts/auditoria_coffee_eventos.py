"""Auditoria visual de Coffee Break e Eventos Sociais contra as telas aprovadas de Viagens:
captura reprodutível de cada página do inventário (docs/auditorias/viagens-coffee-eventos/),
em várias larguras, com o que dá para medir sozinho — rolagem horizontal, erros de console e
violações do axe (WCAG 2.2 AA).

Uso (servidor PREVIEW/DEMO no ar, ex.: scripts/preview.sh local):
  uv run python scripts/auditoria_coffee_eventos.py capturar antes [--base URL] [--so CB-P01]
  ...mudanças...
  uv run python scripts/auditoria_coffee_eventos.py capturar depois
  uv run python scripts/auditoria_coffee_eventos.py compor
  uv run python scripts/auditoria_coffee_eventos.py medir antes|depois   (consultas e tempo)

Saída em artifacts/auditoria-coffee-eventos/{antes,depois}/<id>-<largura>.png, um
`medidas.json` por rodada e, em `comparacoes/index.html`, antes × depois × referência.
Só dados DEMO/sintéticos: nada aqui escreve no banco.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "artifacts" / "auditoria-coffee-eventos"
LARGURAS = [360, 768, 1440]
AXE = RAIZ / "tests" / "_vendor" / "axe.min.js"

# (id, rota, descrição, id da referência em Viagens). As referências entram também como
# cenários (VI-*) para a comparação lado a lado e para a regressão de Viagens.
CENARIOS: list[tuple[str, str, str, str]] = [
    # Viagens (referência aprovada)
    ("VI-L01", "/viagens/oficios/", "Ofícios — lista", ""),
    ("VI-L02", "/viagens/prestacoes/", "Prestação de contas — lista", ""),
    ("VI-D01", "/viagens/oficios/247/editar/", "Ofício — folha (rascunho, edição)", ""),
    ("VI-D02", "/viagens/oficios/1/resumo/", "Ofício — resumo", ""),
    ("VI-P01", "/viagens/", "Viagens — painel", ""),
    ("VI-C01", "/cadastros/servidores/", "Cadastros — servidores", ""),
    # Eventos sociais
    ("EV-P01", "/eventos/", "Eventos — painel", "VI-P01"),
    ("EV-L01", "/eventos/solicitacoes/", "Solicitações — lista", "VI-L01"),
    ("EV-L02", "/eventos/solicitacoes/?fila=despacho", "Solicitações — fila de despacho", "VI-L01"),
    ("EV-L03", "/eventos/solicitacoes/?q=zzzz-nada", "Solicitações — busca vazia", "VI-L01"),
    ("EV-N01", "/eventos/solicitacoes/nova/", "Solicitação — nova", "VI-D01"),
    ("EV-D01", "/eventos/solicitacoes/1/", "Solicitação — rascunho (edição)", "VI-D01"),
    ("EV-D02", "/eventos/solicitacoes/7/", "Solicitação — aguardando despacho", "VI-D02"),
    ("EV-D03", "/eventos/solicitacoes/9/", "Solicitação — devolvida", "VI-D01"),
    ("EV-D04", "/eventos/solicitacoes/14/", "Solicitação — deferida", "VI-D02"),
    ("EV-D05", "/eventos/solicitacoes/16/", "Solicitação — atendida", "VI-D02"),
    ("EV-D06", "/eventos/solicitacoes/7/?reabrir=1", "Solicitação — alterar após envio", "VI-D01"),
    ("EV-C01", "/eventos/cadastros/", "Cadastros de eventos — índice", "VI-C01"),
    ("EV-C02", "/eventos/cadastros/tipos-evento/", "Catálogo — tipos de evento", "VI-C01"),
    ("EV-C03", "/eventos/cadastros/tipos-evento/1/modelo/", "Modelo do tipo de evento", "VI-D01"),
    # Coffee break
    ("CB-P01", "/coffee/painel/", "Coffee — painel", "VI-P01"),
    ("CB-L01", "/coffee/", "Solicitações — lista", "VI-L01"),
    ("CB-L02", "/coffee/?situacao=aguardando_nota", "Solicitações — aguardando nota", "VI-L01"),
    ("CB-L03", "/coffee/?q=zzzz-nada", "Solicitações — busca sem resultado", "VI-L01"),
    ("CB-N01", "/coffee/nova/", "OS — nova", "VI-D01"),
    ("CB-D01", "/coffee/solicitacoes/1/", "OS — aguardando nota (edição)", "VI-D01"),
    ("CB-D02", "/coffee/solicitacoes/6/", "OS — aguardando atesto (dados travados)", "VI-D01"),
    ("CB-D03", "/coffee/solicitacoes/9/", "OS — concluída (só consulta)", "VI-D02"),
    ("CB-D04", "/coffee/solicitacoes/12/", "OS — cancelada", "VI-D02"),
    ("CB-D05", "/coffee/solicitacoes/5/protocolo/", "OS — protocolo de pagamento", "VI-D02"),
    ("CB-D06", "/coffee/solicitacoes/1/email/os/", "OS — e-mail ao fornecedor", "VI-D01"),
    ("CB-L04", "/coffee/lotes/", "Lotes — lista", "VI-L01"),
    ("CB-D07", "/coffee/lotes/2/", "Lote — detalhe", "VI-D02"),
    ("CB-D08", "/coffee/lotes/contrato/1/relatorio/", "Relatório do contrato", "VI-D02"),
    ("CB-L05", "/coffee/certidoes/", "Certidões — quadro", "VI-L01"),
    ("CB-C01", "/coffee/cadastros/fornecedores/", "Cadastros — fornecedores", "VI-C01"),
    ("CB-C02", "/coffee/cadastros/contratos/", "Cadastros — contratos", "VI-C01"),
    ("CB-C03", "/coffee/cadastros/lotes/", "Cadastros — lotes", "VI-C01"),
    ("CB-C04", "/coffee/cadastros/oficio/", "Cadastros — ofício e protocolo", "VI-D01"),
    ("CB-C05", "/coffee/lotes/abrir-exercicio/", "Abrir o exercício seguinte", "VI-D01"),
]


def _entrar(pg, base: str) -> None:
    pg.goto(f"{base}/conta/entrar/")
    pg.click("button[type=submit]")  # DEMO: entra sem senha
    pg.wait_for_load_state("networkidle")


def _axe(pg) -> list[dict]:
    if not AXE.exists():
        return []
    with contextlib.suppress(Exception):
        pg.evaluate(AXE.read_text() + "\n;true")
        resultado = pg.evaluate("""async () => (await axe.run(document, {
            runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']},
            resultTypes: ['violations']})).violations.map(v => ({id: v.id, impacto: v.impact,
            alvos: v.nodes.slice(0, 3).map(n => n.target.join(' '))}))""")
        return list(resultado)
    return []


def capturar(rodada: str, base: str, so: set[str]) -> None:
    from playwright.sync_api import sync_playwright

    destino = SAIDA / rodada
    destino.mkdir(parents=True, exist_ok=True)
    medidas: dict[str, dict] = {}
    arquivo_medidas = destino / "medidas.json"
    if so and arquivo_medidas.exists():
        medidas = json.loads(arquivo_medidas.read_text())
    with sync_playwright() as pw:
        nav = pw.chromium.launch()
        pg = nav.new_context(viewport={"width": 1440, "height": 900}, locale="pt-BR",
                             timezone_id="America/Sao_Paulo").new_page()
        erros: list[str] = []
        pg.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
        _entrar(pg, base)
        for ident, rota, descricao, referencia in CENARIOS:
            if so and ident not in so:
                continue
            item = {"rota": rota, "descricao": descricao, "referencia": referencia,
                    "larguras": {}}
            for largura in LARGURAS:
                erros.clear()
                pg.set_viewport_size({"width": largura, "height": 900})
                resposta = pg.goto(base + rota, wait_until="networkidle")
                # A barra fixa entra na captura da página inteira no lugar dela.
                pg.evaluate("document.querySelectorAll('.barra-acoes')"
                            ".forEach(e => e.style.position = 'static')")
                pg.screenshot(path=str(destino / f"{ident}-{largura}.png"), full_page=True)
                item["larguras"][str(largura)] = {
                    "status": resposta.status if resposta else None,
                    "rolagem_horizontal": pg.evaluate(
                        "document.documentElement.scrollWidth - innerWidth"),
                    "erros_console": list(erros),
                    "axe": _axe(pg) if largura in (360, 1440) else [],
                }
            medidas[ident] = item
            larg = item["larguras"]
            print(ident, rota, " ".join(
                f"{w}:{v['status']}/rol{v['rolagem_horizontal']}/axe{len(v['axe'])}"
                f"/err{len(v['erros_console'])}" for w, v in larg.items()))
        nav.close()
    arquivo_medidas.write_text(json.dumps(medidas, ensure_ascii=False, indent=2))


def medir(rodada: str, repeticoes: int) -> None:
    """Consultas SQL e tempo de resposta de cada página (no processo, contra o banco do
    PREVIEW, como o usuário demo): a mediana de N repetições, depois de uma de aquecimento."""
    import os
    import statistics
    import time

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.preview")
    sys.path.insert(0, str(RAIZ))
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.db import connection
    from django.test import Client
    from django.test.utils import CaptureQueriesContext

    usuario = get_user_model().objects.get(login="demo")
    cliente = Client(HTTP_HOST="127.0.0.1")
    cliente.force_login(usuario)
    saida: dict[str, dict] = {}
    for ident, rota, _descricao, _ref in CENARIOS:
        cliente.get(rota)  # aquecimento
        tempos, consultas, status = [], [], 0
        for _ in range(repeticoes):
            with CaptureQueriesContext(connection) as ctx:
                t = time.perf_counter()
                r = cliente.get(rota)
                tempos.append((time.perf_counter() - t) * 1000)
            consultas.append(len(ctx.captured_queries))
            status = r.status_code
        saida[ident] = {"rota": rota, "status": status, "consultas": max(consultas),
                        "ms_mediana": round(statistics.median(tempos), 1)}
        print(f"{ident:7} {status} {max(consultas):4} consultas {statistics.median(tempos):7.1f} ms"
              f"  {rota}")
    destino = SAIDA / rodada
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "desempenho.json").write_text(json.dumps(saida, ensure_ascii=False, indent=2))


def compor() -> None:
    destino = SAIDA / "comparacoes"
    destino.mkdir(parents=True, exist_ok=True)
    linhas = []
    for ident, rota, descricao, referencia in CENARIOS:
        celulas = []
        for rodada in ("antes", "depois"):
            arq = SAIDA / rodada / f"{ident}-1440.png"
            celulas.append(f'<figure><figcaption>{rodada}</figcaption><a href="../{rodada}/'
                           f'{ident}-1440.png"><img loading="lazy" src="../{rodada}/{ident}'
                           f'-1440.png" alt="{ident} {rodada}"></a></figure>'
                           if arq.exists() else f"<figure><figcaption>{rodada}: —</figcaption>"
                           "</figure>")
        if referencia:
            celulas.append(f'<figure><figcaption>referência {referencia}</figcaption><a href='
                           f'"../depois/{referencia}-1440.png"><img loading="lazy" src="../'
                           f'depois/{referencia}-1440.png" alt="{referencia}"></a></figure>')
        linhas.append(f"<section><h2>{ident} — {descricao} <code>{rota}</code></h2>"
                      f"<div class=g>{''.join(celulas)}</div></section>")
    (destino / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Auditoria Coffee e Eventos</title>"
        "<style>body{font:14px system-ui;margin:16px}.g{display:grid;grid-template-columns:"
        "repeat(3,1fr);gap:8px}img{width:100%;border:1px solid #ccc}figure{margin:0}"
        "</style>" + "".join(linhas))
    print(destino / "index.html")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capturar")
    c.add_argument("rodada", choices=["antes", "depois"])
    c.add_argument("--base", default="http://127.0.0.1:8000")
    c.add_argument("--so", default="")
    sub.add_parser("compor")
    m = sub.add_parser("medir")
    m.add_argument("rodada", choices=["antes", "depois"])
    m.add_argument("--repeticoes", type=int, default=5)
    args = ap.parse_args()
    if args.cmd == "medir":
        medir(args.rodada, args.repeticoes)
    elif args.cmd == "capturar":
        capturar(args.rodada, args.base.rstrip("/"), {x for x in args.so.split(",") if x})
    else:
        compor()
    return 0


if __name__ == "__main__":
    sys.exit(main())
