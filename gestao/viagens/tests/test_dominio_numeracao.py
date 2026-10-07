"""Por que o próximo número é este (página Numeração, LP-32): a explicação vem do domínio,
com a mesma regra de `proximo_numero` (D5: só lacuna de exclusão volta; piso não renumera)."""

from __future__ import annotations

import pytest

from gestao.viagens.dominio.numeracao import explicar_proximo


@pytest.mark.parametrize(("maior", "piso", "lacunas", "proximo", "origem", "validas", "abaixo"), [
    (None, 1, [], 1, "piso", [], []),            # ano sem ofício: começa no piso
    (None, 100, [], 100, "piso", [], []),
    (131, 1, [], 132, "sequencia", [], []),       # último ocupado + 1
    (131, 500, [], 500, "piso", [], []),          # piso acima do último: pula para ele
    (131, 50, [], 132, "sequencia", [], []),      # piso abaixo do último: nada muda agora
    (131, 1, [40, 12], 12, "lacuna", [12, 40], []),  # a menor lacuna primeiro
    (131, 20, [12, 40], 40, "lacuna", [40], [12]),   # lacuna abaixo do piso nunca volta
    (131, 200, [12, 40], 200, "piso", [], [12, 40]),
    (130, 1, [131], 131, "lacuna", [131], []),      # excluído o último: o número volta
])
def test_explicar_proximo(maior, piso, lacunas, proximo, origem, validas, abaixo):
    e = explicar_proximo(maior, piso, lacunas)
    assert (e.proximo, e.origem, e.lacunas_validas, e.lacunas_abaixo) == (
        proximo, origem, validas, abaixo)


def test_piso_que_nao_muda_nada_agora_e_dito():
    assert explicar_proximo(131, 50, []).piso_sem_efeito
    assert not explicar_proximo(131, 500, []).piso_sem_efeito
    assert not explicar_proximo(None, 50, []).piso_sem_efeito
