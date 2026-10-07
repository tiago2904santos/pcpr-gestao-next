from datetime import date

import pytest

from gestao.viagens.dominio.emissao import data_da_emissao


def test_data_automatica_acompanha_dia_da_emissao():
    assert data_da_emissao(date(2026, 10, 1), date(2026, 10, 7), manual=False,
                          ano=2026) == date(2026, 10, 7)


def test_data_manual_preservada():
    assert data_da_emissao(date(2026, 10, 1), date(2026, 10, 7), manual=True,
                          ano=2026) == date(2026, 10, 1)


def test_virada_do_ano_nao_muda_numero_silenciosamente():
    with pytest.raises(ValueError, match="ano atual"):
        data_da_emissao(date(2026, 12, 31), date(2027, 1, 1), manual=False, ano=2026)
