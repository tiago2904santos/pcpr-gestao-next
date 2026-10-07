"""Endereços da lista de ofícios usados por outras telas (busca global, conflitos, vias
assinadas, ações do ciclo de vida) — um lugar só, para nenhum link ficar para trás quando o
vocabulário da lista muda (Lote 2: abas temporais + filtro Documento)."""

from __future__ import annotations

from urllib.parse import urlencode

from django.urls import reverse

from .dominio import recorte


def url_na_lista(oficio, **extra: object) -> str:
    """A lista filtrada neste ofício (pelo número). Arquivado não aparece em "Todos": o
    link já pede Documento = Arquivados para o ofício não sumir."""
    parametros: dict[str, object] = {}
    if oficio.arquivado_em:
        parametros["documento"] = recorte.ARQUIVADO
    parametros["q"] = oficio.numero_formatado
    parametros.update(extra)
    return f"{reverse('viagens:oficios')}?{urlencode(parametros, safe='/')}"
