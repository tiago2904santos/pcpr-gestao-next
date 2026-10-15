"""Prontidão completa não deve empurrar divergências para baixo de nove cartões."""

import pytest
from django.template.loader import render_to_string

from gestao.viagens.viagem_conferencia import Etapa, Item, Quadro


@pytest.mark.parametrize("pronta", [True, False])
def test_etapas_so_recolhem_em_conjunto_quando_todas_estao_prontas(pronta):
    etapas = [Etapa(str(i), f"Etapa {i}") for i in range(9)]
    if not pronta:
        etapas[0].itens.append(Item("Informe o destino.", "/viagens/viagens/1/#destinos"))
    html = render_to_string("viagens/viagem/_conferencia.html", {
        "quadro": Quadro(etapas), "diferencas": [], "editavel": False,
    })
    assert html.count('class="viagem-etapa__nome"') == 9
    if pronta:
        assert '<details class="viagem-conferencia__concluidas">' in html
        assert "Ver as 9 etapas concluídas" in html
    else:
        assert 'class="viagem-conferencia__concluidas"' not in html
        assert '<details class="viagem-etapa" open>' in html
        assert "Informe o destino." in html
