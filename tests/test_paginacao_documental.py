"""Paginação mantém filtros e aceita rota explícita em respostas de formulários."""

import pytest
from django.core.paginator import Paginator
from django.template.loader import render_to_string


@pytest.mark.parametrize("destino", ["", "/viagens/justificativas/"])
def test_links_de_paginacao_preservam_destino_e_contexto(destino):
    html = render_to_string("componentes/paginacao.html", {
        "page_obj": Paginator([1, 2, 3], 1).page(2),
        "querystring_base": "aba=todas&q=Maring%C3%A1&",
        "paginacao_destino": destino,
    })
    assert f'href="{destino}?aba=todas&amp;q=Maring%C3%A1&amp;pagina=1"' in html
    assert f'href="{destino}?aba=todas&amp;q=Maring%C3%A1&amp;pagina=3"' in html
    assert 'aria-label="Página 2, atual"' in html
