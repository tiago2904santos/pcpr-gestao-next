"""Conferência da viagem: as etapas abertas em cartões com os atalhos; as concluídas numa
fileira compacta; a barra conta as concluídas; as divergências lado a lado."""

import pytest
from django.template.loader import render_to_string

from gestao.viagens.viagem_conferencia import Etapa, Item, Quadro


def _html(quadro, diferencas=()):
    return render_to_string("viagens/viagem/_conferencia.html", {
        "quadro": quadro, "diferencas": list(diferencas), "editavel": False,
    })


@pytest.mark.parametrize("pronta", [True, False])
def test_abertas_em_cartoes_e_concluidas_numa_fileira(pronta):
    etapas = [Etapa(str(i), f"Etapa {i}") for i in range(9)]
    if not pronta:
        etapas[0].itens.append(Item("Informe o destino.", "/viagens/viagens/1/#destinos"))
    html = _html(Quadro(etapas))
    assert 'max="9"' in html and f'value="{9 if pronta else 8}"' in html
    if pronta:
        assert 'class="viagem-etapas"' not in html
        assert html.count('class="viagem-concluida"') == 9
        assert "Todas as etapas concluídas" in html and "Tudo pronto para a viagem" in html
    else:
        assert html.count('<li class="viagem-etapa">') == 1
        assert html.count('class="viagem-concluida"') == 8
        assert 'href="/viagens/viagens/1/#destinos"' in html and "Informe o destino." in html


def test_divergencias_mostram_documento_e_viagem_lado_a_lado():
    etapas = [Etapa("dados", "Dados da viagem")]
    diferencas = [{"documento": "OS 001/2026", "link": "/os/1/", "campo": "período",
                   "atual": "25/10/2026 a 30/10/2026", "esperado": "27/10/2026 a 29/10/2026",
                   "aplicavel": False}]
    html = _html(Quadro(etapas), diferencas)
    assert "falta acertar as divergências" in html
    assert "No documento</small>25/10/2026 a 30/10/2026" in html
    assert "Na viagem</small>27/10/2026 a 29/10/2026" in html
    assert "Corrija no próprio documento" in html and ">Período<" in html
