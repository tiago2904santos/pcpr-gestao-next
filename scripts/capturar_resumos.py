"""Captura as janelas de resumo (diálogo inteiro) de cada tipo e estado, em várias larguras.

Uso (contra o PREVIEW local, `scripts/preview.sh local`, entrada DEMO sem senha):
  uv run python scripts/capturar_resumos.py artifacts/resumos/depois
  uv run python scripts/capturar_resumos.py saida --larguras 1440 --filtro termo

Os números dos registros são os dos dados sintéticos de `semear_demo`
(docs/visual-agents/resumos/README.md, §1). Para cada captura, o relatório
(`relatorio.json`) traz a rolagem horizontal da página e do corpo do diálogo e os erros
de console — o que for diferente de zero é impresso como ATENÇÃO.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

CASOS = [  # nome, lista que abre a janela, fragmento do resumo
    ("oficio-rascunho-260", "/viagens/oficios/", "/viagens/oficios/260/resumo/"),
    ("oficio-emitido-258", "/viagens/oficios/", "/viagens/oficios/258/resumo/"),
    ("oficio-emitido-via-255", "/viagens/oficios/", "/viagens/oficios/255/resumo/"),
    ("oficio-cancelado-221", "/viagens/oficios/", "/viagens/oficios/221/resumo/"),
    ("os-gerada-assinada-5", "/viagens/ordens/", "/viagens/ordens/5/resumo/"),
    ("os-rascunho-2", "/viagens/ordens/", "/viagens/ordens/2/resumo/"),
    ("os-cancelada-4", "/viagens/ordens/", "/viagens/ordens/4/resumo/"),
    ("termo-assinado-1", "/viagens/termos/", "/viagens/termos/1/resumo/"),
    ("termo-rascunho-7", "/viagens/termos/", "/viagens/termos/7/resumo/"),
    ("termo-cancelado-6", "/viagens/termos/", "/viagens/termos/6/resumo/"),
    ("plano-gerado-1", "/viagens/planos/", "/viagens/planos/1/resumo/"),
    ("plano-vazio-4", "/viagens/planos/", "/viagens/planos/4/resumo/"),
    ("plano-cancelado-3", "/viagens/planos/", "/viagens/planos/3/resumo/"),
    ("viagem-preparacao-1", "/viagens/viagens/", "/viagens/viagens/1/resumo/"),
    ("viagem-vazia-5", "/viagens/viagens/", "/viagens/viagens/5/resumo/"),
    ("viagem-cancelada-3", "/viagens/viagens/", "/viagens/viagens/3/resumo/"),
    ("roteiro-com-oficio-1", "/viagens/roteiros/", "/viagens/roteiros/1/resumo/"),
    ("roteiro-6-trechos-60", "/viagens/roteiros/", "/viagens/roteiros/60/resumo/"),
    ("roteiro-cancelado-71", "/viagens/roteiros/", "/viagens/roteiros/71/resumo/"),
]

ABRIR = """async (url) => {
  await htmx.ajax('GET', url, {target: '#resumo-dialogo', swap: 'innerHTML'});
  document.getElementById('dialogo-resumo').showModal();
}"""
MEDIR = """() => {
  const c = document.querySelector('dialog[open] .dialogo__corpo');
  return {altura_corpo: c ? c.scrollHeight : 0,
          overflow_x: document.documentElement.scrollWidth - innerWidth,
          corpo_overflow_x: c ? c.scrollWidth - c.clientWidth : 0};
}"""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("saida")
    p.add_argument("--base", default="http://127.0.0.1:8000")
    p.add_argument("--larguras", default="1440,1024,390")
    p.add_argument("--filtro", default="")
    args = p.parse_args()
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    relatorio: dict[str, dict] = {}
    erros: list[str] = []
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        for largura in (int(x) for x in args.larguras.split(",")):
            contexto = navegador.new_context(viewport={"width": largura, "height": 900},
                                             locale="pt-BR", timezone_id="America/Sao_Paulo")
            pagina = contexto.new_page()
            pagina.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
            pagina.on("pageerror", lambda e: erros.append(str(e)))
            for nome, lista, url in CASOS:
                if args.filtro not in nome:
                    continue
                erros.clear()
                pagina.set_viewport_size({"width": largura, "height": 900})
                pagina.goto(args.base + lista, wait_until="networkidle")
                pagina.evaluate(ABRIR, url)
                pagina.wait_for_timeout(900)
                medida = pagina.evaluate(MEDIR)
                # A janela cresce até caber o corpo inteiro (só na captura).
                pagina.set_viewport_size({"width": largura,
                                          "height": min(900 + medida["altura_corpo"], 6000)})
                pagina.wait_for_timeout(400)
                pagina.locator("dialog[open]").screenshot(path=str(saida / f"{nome}-{largura}.png"))
                relatorio[f"{nome}-{largura}"] = {**medida, "erros_console": list(erros)}
                pagina.keyboard.press("Escape")
            contexto.close()
    (saida / "relatorio.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=1))
    for chave, valor in relatorio.items():
        if valor["overflow_x"] > 0 or valor["corpo_overflow_x"] > 0 or valor["erros_console"]:
            print("ATENÇÃO", chave, valor)
    print(len(relatorio), "capturas")


if __name__ == "__main__":
    main()
