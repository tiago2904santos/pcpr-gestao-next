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
          "negrito_italico": "LiberationSerif-BoldItalic.ttf"}


def _recursos(folha: bool) -> dict[str, Any]:
    if folha:
        return {"brasao": static("documentos/brasao-pcpr.png"),
                "fontes": {k: static(f"documentos/fontes/{v}") for k, v in FONTES.items()}}
    base = ASSETS.as_uri()
    return {"brasao": f"{base}/brasao-pcpr.png",
            "fontes": {k: f"{base}/fontes/{v}" for k, v in FONTES.items()}}


def valores_dos_campos(tipo: str, dados: dict[str, Any]) -> dict[str, str]:
    return {c.chave: str(dados.get(c.chave) or "") for c in campos_do_documento(tipo)}


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
    from weasyprint import HTML

    html = html_do_documento(tipo, dados)
    identificador = hashlib.sha256(
        f"{tipo}:{dados['numero']}:{dados['emitido_em']}".encode()
    ).digest()[:16]
    pdf = HTML(string=html, base_url=str(ASSETS)).write_pdf(
        pdf_variant="pdf/a-2a",
        pdf_identifier=identificador,
        pdf_tags=True,
        custom_metadata=True,
        presentational_hints=True,
        optimize_images=True,
    )
    return pdf, hashlib.sha256(pdf).hexdigest()


_BLOCO = re.compile(r'<([a-z0-9]+)\b([^>]*\bdata-bloco="([a-z0-9_-]+)"[^>]*)>')


def paginas_do_documento(tipo: str, dados: dict[str, Any],
                         regioes: dict[str, str] | None = None) -> dict[str, Any]:
    """Quantas páginas o documento tem e em qual página cada bloco começa."""
    from weasyprint import HTML

    html = html_do_documento(tipo, dados, previa=True, regioes=regioes)
    html = _BLOCO.sub(lambda m: f'<{m.group(1)} id="b-{m.group(3)}"{m.group(2)}>', html)
    doc = HTML(string=html, base_url=str(ASSETS)).render()
    blocos: dict[str, int] = {}
    for numero, pagina in enumerate(doc.pages, start=1):
        for ancora in pagina.anchors:
            if ancora.startswith("b-"):
                blocos.setdefault(ancora[2:], numero)
    return {"total": len(doc.pages), "blocos": blocos}
