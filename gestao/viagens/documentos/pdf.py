"""Renderização HTML → PDF/A-2a com WeasyPrint (fontes embutidas, PDF marcado)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from django.template.loader import render_to_string

ASSETS = Path(__file__).resolve().parent.parent / "documentos_assets"
TEMPLATES = {"oficio": "viagens/documentos/oficio.html",
             "justificativa": "viagens/documentos/justificativa.html"}


def html_do_documento(tipo: str, dados: dict[str, Any], *, previa: bool = False) -> str:
    return render_to_string(TEMPLATES[tipo], {"d": dados, "assets": ASSETS.as_uri(),
                                              "previa": previa})


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
