"""Diárias: casos dos demonstrativos oficiais (especificação comportamental).

Os valores esperados vêm dos demonstrativos do sistema oficial de solicitação de
diárias, usados como caracterização no sistema de referência
(docs/product/documents.md, seção Diárias). Se um destes quebrar, a regressão é de dinheiro.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gestao.viagens.dominio.diarias import (
    CAPITAIS,
    Destino,
    Faixa,
    RoteiroIncalculavel,
    SemTabelaDeDiarias,
    ValorVigente,
    calcular,
    decompor,
    faixa_do_destino,
    valor_percentual,
)

INTERIOR, CAPITAL, BRASILIA = Decimal("290.55"), Decimal("371.26"), Decimal("468.12")
SP, ABATIA, FLORIPA = ("São Paulo", "SP"), ("Abatiá", "PR"), ("Florianópolis", "SC")
ADRIANOPOLIS, CURITIBA, ARAPONGAS = ("Adrianópolis", "PR"), ("Curitiba", "PR"), ("Arapongas", "PR")


def tabelas(_data: date):
    desde = date(2026, 1, 1)
    if _data < desde:
        return {}
    return {
        Faixa.INTERIOR: ValorVigente(Faixa.INTERIOR, INTERIOR, desde, "t-interior"),
        Faixa.CAPITAL: ValorVigente(Faixa.CAPITAL, CAPITAL, desde, "t-capital"),
        Faixa.BRASILIA: ValorVigente(Faixa.BRASILIA, BRASILIA, desde, "t-brasilia"),
    }


def d(dia, h, m=0, mes=8, ano=2026):
    return datetime(ano, mes, dia, h, m)


def destino(lugar, saida, chegada=None):
    return Destino(lugar[0], lugar[1], saida, chegada)


def calc(destinos, chegada, servidores=1):
    return calcular(destinos, chegada, buscar_tabelas=tabelas, servidores=servidores,
                    sede=CURITIBA)


class TestDemonstrativosOficiais:
    def test_curitiba_sao_paulo_abatia_curitiba_773_19(self):
        r = calc([destino(SP, d(12, 8), d(12, 18)), destino(ABATIA, d(13, 8), d(13, 18)),
                  destino(CURITIBA, d(14, 8), d(14, 18))], d(14, 18))
        assert r.total == Decimal("773.19")
        capital, interior = r.trechos
        assert (capital.faixa, capital.inicio, capital.fim) == (Faixa.CAPITAL, d(12, 8), d(13, 18))
        assert (capital.dias, capital.percentual, capital.subtotal) == (1, 30, Decimal("482.64"))
        assert (interior.faixa, interior.inicio) == (Faixa.INTERIOR, d(13, 18))
        assert (interior.dias, interior.percentual, interior.subtotal) == (1, 0, INTERIOR)

    def test_retorno_passando_pela_capital_1144_45(self):
        r = calc([destino(SP, d(12, 8), d(12, 18)), destino(ABATIA, d(13, 8), d(13, 18)),
                  destino(SP, d(14, 8), d(14, 18)), destino(CURITIBA, d(15, 8), d(15, 18))],
                 d(15, 18))
        assert r.total == Decimal("1144.45")
        assert [t.faixa for t in r.trechos] == [Faixa.CAPITAL, Faixa.INTERIOR, Faixa.CAPITAL]

    def test_destinos_seguidos_da_mesma_faixa_formam_um_trecho_1169_47(self):
        r = calc([destino(SP, d(12, 8), d(12, 18)), destino(FLORIPA, d(13, 8), d(13, 14)),
                  destino(SP, d(14, 8), d(14, 16)), destino(CURITIBA, d(15, 8), d(15, 16))],
                 d(15, 16))
        assert r.total == Decimal("1169.47")
        (t,) = r.trechos
        assert (t.faixa, t.inicio, t.fim, t.dias, t.percentual) == (
            Faixa.CAPITAL, d(12, 8), d(15, 16), 3, 15)

    def test_deslocamento_entre_destinos_e_cobrado_na_faixa_de_origem(self):
        r = calc([destino(SP, d(12, 8), d(12, 18)), destino(ABATIA, d(13, 8), d(13, 18)),
                  destino(CURITIBA, d(14, 8), d(14, 18))], d(14, 18))
        assert [t.percentual for t in r.trechos if t.percentual] == [30]


class TestEscadaDoResto:
    def test_12h01_no_mesmo_dia_vale_diaria_inteira(self):
        r = calc([destino(ADRIANOPOLIS, d(12, 8), d(12, 12)),
                  destino(CURITIBA, d(12, 19), d(12, 20, 1))], d(12, 20, 1))
        assert r.total == INTERIOR
        assert (r.trechos[0].dias, r.trechos[0].percentual) == (0, 100)
        assert r.resumo == "1 x 100%"

    def test_16h_atravessando_a_madrugada_na_capital(self):
        r = calc([destino(SP, d(12, 20), d(13, 2)), destino(CURITIBA, d(13, 6), d(13, 12))],
                 d(13, 12))
        assert r.total == CAPITAL

    @pytest.mark.parametrize(("horas", "esperado"), [
        (5, 0), (6, 0), (7, 15), (8, 15), (9, 30), (12, 30), (13, 100), (20, 100)])
    def test_escada_completa(self, horas, esperado):
        base = d(12, 6)
        assert decompor(base, base + timedelta(hours=horas)).percentual == esperado

    def test_limites_exatos_em_minutos(self):
        base = d(12, 6)
        assert decompor(base, base + timedelta(hours=6, minutes=1)).percentual == 15
        assert decompor(base, base + timedelta(hours=8, minutes=1)).percentual == 30
        assert decompor(base, base + timedelta(hours=12, minutes=1)).percentual == 100

    def test_cruzar_meia_noite_nao_e_criterio(self):
        r = decompor(d(12, 23, 59), d(13, 0, 1))
        assert (r.dias, r.percentual) == (0, 0)

    def test_44_horas_sao_duas_diarias(self):
        r = decompor(d(12, 8), d(14, 4))
        assert (r.dias, r.percentual) == (1, 100)


class TestOficioDeReferencia:
    """Ofício 131/2026 observado no sistema de referência (2 servidores, Arapongas)."""

    def test_arapongas_08_a_12_10_com_dois_servidores(self):
        r = calc([destino(ARAPONGAS, d(8, 9, mes=10), d(8, 16, 30, mes=10)),
                  destino(CURITIBA, d(12, 9, mes=10), d(12, 16, 30, mes=10))],
                 d(12, 16, 30, mes=10), servidores=2)
        assert r.resumo == "4 x 100% + 1 x 15%"
        assert r.total == Decimal("2411.56")
        assert r.tipo_destino == "INTERIOR"
        assert r.extenso == "dois mil quatrocentos e onze reais e cinquenta e seis centavos"
        assert [(p.percentual, p.quantidade, p.valor_unitario, p.subtotal) for p in r.parcelas] == [
            (100, 4, Decimal("290.55"), Decimal("2324.40")),
            (15, 1, Decimal("43.58"), Decimal("87.16")),
        ]


class TestComposicaoEReconciliacao:
    @pytest.mark.parametrize("servidores", [0, 1, 2, 3, 7])
    def test_parcelas_somam_o_total_e_por_servidor_reconstroi(self, servidores):
        r = calc([destino(SP, d(12, 8), d(12, 18)), destino(ABATIA, d(13, 8), d(13, 18)),
                  destino(CURITIBA, d(14, 8), d(14, 18))], d(14, 18), servidores)
        assert sum((p.subtotal for p in r.parcelas), Decimal(0)) == r.total
        assert r.por_servidor * servidores == r.total
        if servidores == 0:
            assert r.total == Decimal("0.00")

    def test_cada_parcela_guarda_a_vigencia(self):
        r = calc([destino(SP, d(12, 8), d(12, 18)), destino(ABATIA, d(13, 8), d(13, 18)),
                  destino(CURITIBA, d(14, 8), d(14, 18))], d(14, 18))
        assert [(p.faixa, p.percentual, p.quantidade) for p in r.parcelas] == [
            (Faixa.CAPITAL, 100, 1), (Faixa.CAPITAL, 30, 1), (Faixa.INTERIOR, 100, 1)]
        assert {p.vigente_desde for p in r.parcelas} == {date(2026, 1, 1)}

    def test_instantaneo_serializavel(self):
        r = calc([destino(ARAPONGAS, d(8, 9, mes=10), d(8, 16, 30, mes=10))],
                 d(12, 16, 30, mes=10), servidores=2)
        dados = r.como_dict()
        assert dados["total"] == "2411.56" and len(dados["parcelas"]) == 2


class TestFaixas:
    def test_brasilia_capital_interior(self):
        assert faixa_do_destino("Brasília", "DF") is Faixa.BRASILIA
        assert faixa_do_destino("SAO PAULO", "sp") is Faixa.CAPITAL
        assert faixa_do_destino("Abatiá", "PR") is Faixa.INTERIOR
        assert faixa_do_destino("Curitiba", "SP") is Faixa.INTERIOR
        assert faixa_do_destino("Qualquer", "") is Faixa.INTERIOR

    def test_27_capitais(self):
        assert len(CAPITAIS) == 27

    @pytest.mark.parametrize(("valor", "pct", "esperado"), [
        ("290.55", 15, "43.58"), ("290.55", 30, "87.17"), ("371.26", 15, "55.69"),
        ("371.26", 30, "111.38"), ("468.12", 15, "70.22"), ("468.12", 30, "140.44")])
    def test_percentuais_da_tabela_vigente(self, valor, pct, esperado):
        """Mesmos valores exibidos na tela de cadastro de diárias da referência."""
        assert valor_percentual(Decimal(valor), pct) == Decimal(esperado)


class TestErrosVisiveis:
    def test_sem_vigencia_recusa_e_diz_o_que_falta(self):
        with pytest.raises(SemTabelaDeDiarias, match="Interior, Capital, Brasília"):
            calc([destino(SP, d(12, 8, ano=2025), d(12, 18, ano=2025))], d(13, 18, ano=2025))

    def test_sem_destinos(self):
        with pytest.raises(RoteiroIncalculavel):
            calc([], d(13, 18))

    def test_chegada_antes_da_saida(self):
        with pytest.raises(RoteiroIncalculavel, match="fora de ordem"):
            calc([destino(SP, d(12, 8), d(12, 18))], d(11, 18))

    def test_vigencia_e_decidida_pela_data_local_da_primeira_saida(self):
        """Saída 22h de 31/12/2025 (local) usa a tabela de 2025 → sem vigência."""
        with pytest.raises(SemTabelaDeDiarias):
            calc([destino(SP, datetime(2025, 12, 31, 22), datetime(2026, 1, 1, 6))],
                 datetime(2026, 1, 2, 18))


# Sem prazo por exemplo: o teste é de propriedades, e sob a suíte paralela um exemplo
# passava dos 200 ms padrão do Hypothesis (falha intermitente, não regra quebrada).
@settings(deadline=None)
@given(
    horas=st.lists(st.integers(min_value=1, max_value=96), min_size=1, max_size=5),
    servidores=st.integers(min_value=0, max_value=10),
)
def test_propriedades_total_nao_negativo_e_reconciliado(horas, servidores):
    instante = d(1, 8)
    destinos = []
    lugares = [SP, ABATIA, FLORIPA, ("Brasília", "DF"), ARAPONGAS]
    for i, h in enumerate(horas):
        destinos.append(destino(lugares[i % len(lugares)], instante, instante + timedelta(hours=2)))
        instante += timedelta(hours=h + 2)
    r = calc(destinos, instante, servidores)
    assert r.total >= 0
    assert sum((p.subtotal for p in r.parcelas), Decimal(0)) == r.total
    assert r.por_servidor * servidores == r.total
