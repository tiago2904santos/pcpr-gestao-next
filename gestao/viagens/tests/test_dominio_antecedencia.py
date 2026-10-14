from datetime import date

import pytest

from gestao.viagens.dominio.prazos import antecedencia_do_inicio


@pytest.mark.parametrize(("inicio", "hoje", "esperado"), [
    (None, date(2026, 10, 14), (None, "defina o período")),
    (date(2026, 10, 17), date(2026, 10, 14), (3, "dias de antecedência")),
    (date(2026, 10, 15), date(2026, 10, 14), (1, "dia de antecedência")),
    (date(2026, 10, 14), date(2026, 10, 14), (0, "começa hoje")),
    (date(2026, 10, 12), date(2026, 10, 14), (2, "dias desde o início")),
    (date(2026, 10, 13), date(2026, 10, 14), (1, "dia desde o início")),
    (date(2027, 1, 2), date(2026, 12, 31), (2, "dias de antecedência")),
])
def test_contagem_do_inicio(inicio, hoje, esperado):
    assert antecedencia_do_inicio(inicio, hoje) == esperado
