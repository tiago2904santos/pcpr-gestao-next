"""Renderização HTML → PDF/A-2a com WeasyPrint (fontes embutidas, PDF marcado).

O mesmo HTML serve três usos: o PDF (arquivado ou minuta), a **folha** que o navegador
mostra dentro do editor (ADR 0018) e a contagem de páginas. Nos três, o texto editado em
vigor (regiões) entra no lugar do que o modelo gera, e os campos vinculados são reescritos
com o valor atual do cadastro.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from django.template.loader import render_to_string
from django.templatetags.static import static

from .campos import campos_do_documento
from .regioes import (
    aplicar_regioes,
    extrair_regioes,
    marcar_blocos_alterados,
    sincronizar_campos,
)

ASSETS = Path(__file__).resolve().parent.parent / "documentos_assets"
TEMPLATES = {"oficio": "viagens/documentos/oficio.html",
             "justificativa": "viagens/documentos/justificativa.html"}
FONTES = {"regular": "LiberationSerif-Regular.ttf", "negrito": "LiberationSerif-Bold.ttf",
          "italico": "LiberationSerif-Italic.ttf",
          "negrito_italico": "LiberationSerif-BoldItalic.ttf",
          # Sem serifa (o diário de bordo e o relatório técnico saem em Arial na referência).
          "sans_regular": "LiberationSans-Regular.ttf", "sans_negrito": "LiberationSans-Bold.ttf",
          "sans_italico": "LiberationSans-Italic.ttf",
          "sans_negrito_italico": "LiberationSans-BoldItalic.ttf"}


def _so_recursos_dos_documentos():
    """Buscador de recursos do WeasyPrint que só entrega arquivos da pasta dos documentos
    (brasão, fontes). Nenhum dado do cadastro vira URL hoje; isto garante que nunca vire."""
    from urllib.parse import urlsplit
    from urllib.request import url2pathname

    from weasyprint.urls import URLFetcher

    class Buscador(URLFetcher):
        def fetch(self, url, headers=None):
            partes = urlsplit(url)
            if partes.scheme != "file":
                raise ValueError(f"Recurso externo recusado: {url[:80]}")
            caminho = Path(url2pathname(partes.path)).resolve()
            if not caminho.is_relative_to(ASSETS.resolve()):
                raise ValueError(f"Recurso fora dos documentos recusado: {url[:80]}")
            return super().fetch(url, headers)

    return Buscador(allowed_protocols=("file",))


def buscar_recurso():
    """Um buscador novo por renderização (ele guarda estado da requisição: não se compartilha
    entre threads)."""
    return _so_recursos_dos_documentos()


# Documentos que devem caber numa página (o ofício, como no sistema modelo): quantos degraus
# de compactação o CSS do modelo define (`.doc-compacto-1`, `.doc-compacto-2` no <body>). Se o
# PDF passar de uma página é refeito com o degrau seguinte; esgotados, sai como couber.
CABER_EM_UMA_PAGINA = {"oficio": 2}
_BODY = re.compile(r"<body\b")


def _recursos(folha: bool) -> dict[str, Any]:
    if folha:
        return {"brasao": static("documentos/brasao-pcpr.png"),
                "marca": static("documentos/marca-pcpr.png"),
                "fontes": {k: static(f"documentos/fontes/{v}") for k, v in FONTES.items()}}
    base = ASSETS.as_uri()
    return {"brasao": f"{base}/brasao-pcpr.png", "marca": f"{base}/marca-pcpr.png",
            "fontes": {k: f"{base}/fontes/{v}" for k, v in FONTES.items()}}


def renderizar(tipo: str, html: str):
    """O documento paginado pelo WeasyPrint. Um tipo que deve caber numa página é refeito
    com os degraus de compactação do seu CSS enquanto passar de uma."""
    from weasyprint import HTML

    def paginar(texto: str):
        return HTML(string=texto, base_url=str(ASSETS), url_fetcher=buscar_recurso()).render(
            presentational_hints=True)

    documento = paginar(html)
    for degrau in range(1, CABER_EM_UMA_PAGINA.get(tipo, 0) + 1):
        if len(documento.pages) <= 1:
            break
        documento = paginar(_BODY.sub(f'<body class="doc-compacto-{degrau}"', html, count=1))
    return documento


def valores_dos_campos(tipo: str, dados: dict[str, Any]) -> dict[str, str]:
    valores = {c.chave: str(dados.get(c.chave) or "") for c in campos_do_documento(tipo)}
    valores["destinos"] = ", ".join(dados.get("destinos") or [])
    trechos = [*(dados.get("ida") or []), *(dados.get("volta") or []),
               *(dados.get("trechos") or [])]
    for t in trechos:
        if isinstance(t, dict) and t.get("ordem"):
            for lado in ("saida", "chegada"):
                momento = t.get(lado) or {}
                texto = f"{momento.get('data', '')} {momento.get('hora', '')}".strip()
                valores[f"trecho_{t['ordem']}_{lado}"] = texto
    return valores


def html_do_modelo(tipo: str, dados: dict[str, Any], *, previa: bool = False,
                   folha: bool = False, nonce: str = "") -> str:
    """O documento como o modelo o gera, sem nenhuma edição aplicada."""
    return render_to_string(TEMPLATES[tipo], {"d": dados, "previa": previa, "folha": folha,
                                              "nonce": nonce, **_recursos(folha)})


def regioes_do_modelo(tipo: str, dados: dict[str, Any]) -> dict[str, str]:
    return extrair_regioes(html_do_modelo(tipo, dados))


def html_do_documento(tipo: str, dados: dict[str, Any], *, previa: bool = False,
                      folha: bool = False, nonce: str = "",
                      regioes: dict[str, str] | None = None,
                      blocos_alterados: set[str] | None = None) -> str:
    """HTML final: modelo + regiões editadas (as do instantâneo, se não vierem) + campos vivos."""
    if regioes is None:
        regioes = (dados.get("edicao") or {}).get("regioes") or {}
    html = html_do_modelo(tipo, dados, previa=previa, folha=folha, nonce=nonce)
    if regioes:
        html = aplicar_regioes(html, regioes)
    html = sincronizar_campos(html, valores_dos_campos(tipo, dados))
    if blocos_alterados:
        html = marcar_blocos_alterados(html, blocos_alterados)
    return html


def gerar_pdf(tipo: str, dados: dict[str, Any]) -> tuple[bytes, str]:
    """Retorna (bytes do PDF/A-2a, sha256 hexadecimal)."""
    html = html_do_documento(tipo, dados)
    identificador = hashlib.sha256(
        f"{tipo}:{dados['numero']}:{dados['emitido_em']}".encode()
    ).digest()[:16]
    pdf = renderizar(tipo, html).write_pdf(
        pdf_variant="pdf/a-2a",
        pdf_identifier=identificador,
        pdf_tags=True,
        custom_metadata=True,
        optimize_images=True,
    )
    return pdf, hashlib.sha256(pdf).hexdigest()


_BLOCO = re.compile(r'<([a-z0-9]+)\b([^>]*\bdata-bloco="([a-z0-9_-]+)"[^>]*)>')


def paginas_do_documento(tipo: str, dados: dict[str, Any],
                         regioes: dict[str, str] | None = None) -> dict[str, Any]:
    """Quantas páginas o documento tem e em qual página cada bloco começa (com a mesma
    compactação do PDF: a contagem é a do arquivo que sai)."""
    html = html_do_documento(tipo, dados, previa=True, regioes=regioes)
    html = _BLOCO.sub(lambda m: f'<{m.group(1)} id="b-{m.group(3)}"{m.group(2)}>', html)
    doc = renderizar(tipo, html)
    blocos: dict[str, int] = {}
    for numero, pagina in enumerate(doc.pages, start=1):
        for ancora in pagina.anchors:
            if ancora.startswith("b-"):
                blocos.setdefault(ancora[2:], numero)
    return {"total": len(doc.pages), "blocos": blocos}
