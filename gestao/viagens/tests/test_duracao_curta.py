from datetime import datetime, timedelta

import pytest

from gestao.viagens.templatetags.viagens import duracao_curta

INICIO = datetime(2026, 12, 13, 7, 0)


@pytest.mark.parametrize("delta, esperado", [
    (timedelta(hours=9, minutes=30), "9h30"),
    (timedelta(hours=2), "2h00"),
    (timedelta(minutes=45), "45 min"),
    (timedelta(hours=26, minutes=5), "26h05"),
    (timedelta(0), "0 min"),
])
def test_duracao_curta_formata_horas_e_minutos(delta, esperado):
    assert duracao_curta(INICIO + delta, INICIO) == esperado


def test_duracao_curta_vazia_sem_dado_ou_negativa():
    assert duracao_curta(None, INICIO) == ""
    assert duracao_curta(INICIO, None) == ""
    assert duracao_curta(INICIO - timedelta(minutes=1), INICIO) == ""
