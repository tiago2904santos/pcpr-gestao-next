from __future__ import annotations

from datetime import date

import pytest

from gestao.viagens.dominio.extenso import inteiro_por_extenso, reais_por_extenso
from gestao.viagens.dominio.numeracao import formatar_numero, proximo_numero
from gestao.viagens.dominio.prazos import SituacaoPrazo, avaliar_prazo

OFICIO = date(2026, 9, 28)


@pytest.mark.parametrize(("saida", "situacao", "obrigatoria"), [
    (None, SituacaoPrazo.INDEFINIDA, False),
    (date(2026, 9, 27), SituacaoPrazo.RETROATIVA, True),
    (date(2026, 9, 28), SituacaoPrazo.FORA_DO_PRAZO, True),
    (date(2026, 10, 8), SituacaoPrazo.FORA_DO_PRAZO, True),   # 10 dias = ainda obrigatória
    (date(2026, 10, 9), SituacaoPrazo.NO_PRAZO, False),       # 11 dias = dispensada
])
def test_regra_de_antecedencia(saida, situacao, obrigatoria):
    """Caso de referência: ofício de 28/09 com saída em 08/10 (10 dias) exige justificativa."""
    r = avaliar_prazo(OFICIO, saida, 10)
    assert r.situacao is situacao and r.justificativa_obrigatoria is obrigatoria
    assert r.mensagem


def test_mensagens_dizem_o_que_fazer():
    assert "Justificativa obrigatória" in avaliar_prazo(OFICIO, date(2026, 10, 1), 10).mensagem
    assert "1 dia de" in avaliar_prazo(OFICIO, date(2026, 9, 29), 10).mensagem
    assert "dispensada" in avaliar_prazo(OFICIO, date(2026, 12, 1), 10).mensagem


@pytest.mark.parametrize(("ocupados", "piso", "lacunas", "esperado"), [
    ([], 1, [], 1),
    ([1, 2, 3], 1, [], 4),
    ([1, 3], 1, [], 4),            # D5: buraco sem exclusão não é reaproveitado
    ([1, 3], 1, [2], 2),           # lacuna registrada (rascunho excluído) é reaproveitada
    ([1, 2, 4, 6], 1, [5, 3], 3),  # a menor lacuna primeiro
    ([1, 2, 3], 1, [2], 4),        # lacuna já ocupada de novo é ignorada
    ([1, 2, 3], 100, [], 100),     # piso acima dos ocupados
    ([100, 101, 5], 100, [3], 102),  # lacuna abaixo do piso é ignorada
])
def test_proximo_numero(ocupados, piso, lacunas, esperado):
    assert proximo_numero(ocupados, piso, lacunas) == esperado


def test_formatar_numero_com_dois_digitos():
    """Decisão D2: "05/2026", como na referência; acima de 99 o número cresce."""
    assert formatar_numero(7, 2026) == "07/2026"
    assert formatar_numero(131, 2026) == "131/2026"
    assert formatar_numero(None, 2026) == "Sem número"


@pytest.mark.parametrize(("n", "texto"), [
    (0, "zero"), (1, "um"), (16, "dezesseis"), (21, "vinte e um"), (100, "cem"),
    (101, "cento e um"), (1000, "mil"), (1100, "mil e cem"), (1050, "mil e cinquenta"),
    (2411, "dois mil quatrocentos e onze"), (1_000_000, "um milhão"),
    (2_500_000, "dois milhões e quinhentos mil")])
def test_inteiro_por_extenso(n, texto):
    assert inteiro_por_extenso(n) == texto


@pytest.mark.parametrize(("valor", "texto"), [
    ("2411.56", "dois mil quatrocentos e onze reais e cinquenta e seis centavos"),
    ("1.00", "um real"), ("0.01", "um centavo"), ("0", "zero real"),
    ("2000000", "dois milhões de reais"),
    ("624.68", "seiscentos e vinte e quatro reais e sessenta e oito centavos")])
def test_reais_por_extenso(valor, texto):
    from decimal import Decimal

    assert reais_por_extenso(Decimal(valor)) == texto


from gestao.viagens.dominio.assunto import Marcador, resolver_assunto  # noqa: E402


@pytest.mark.parametrize(("saida", "marcador", "rotulo", "termo"), [
    (date(2026, 10, 8), "", "(Autorização)", "autorização"),
    (None, "", "(Autorização)", "autorização"),
    (date(2026, 9, 28), "", "(Convalidação)", "convalidação"),   # mesmo dia = convalidação
    (date(2026, 9, 1), "", "(Convalidação)", "convalidação"),
    (date(2026, 10, 8), Marcador.RETIFICADO, "(Retificado)", "autorização"),
    (date(2026, 9, 1), Marcador.RETIFICADO, "(Convalidação)", "convalidação"),  # ignorado
    (date(2026, 10, 8), Marcador.COMPLEMENTAR, "(Complementar)", "autorização"),
    (date(2026, 9, 1), Marcador.COMPLEMENTAR, "(Complementar)", "convalidação"),
])
def test_assunto_autorizacao_ou_convalidacao(saida, marcador, rotulo, termo):
    a = resolver_assunto(OFICIO, saida, marcador)
    assert (a.rotulo, a.termo) == (rotulo, termo)
    assert a.linha == f"Solicitação de {termo} e concessão de diárias."


# ---------------------------------------------------------------- tipo do ofício (LP-07)
from gestao.viagens.dominio.assunto import tipo_do_oficio  # noqa: E402


@pytest.mark.parametrize(("saida", "marcador", "completo", "selo"), [
    (date(2026, 10, 8), "", "Autorização", ""),                   # o comum: sem selo
    (None, "", "Autorização", ""),
    (date(2026, 9, 28), "", "Convalidação", "Convalidação"),      # mesmo dia
    (date(2026, 9, 1), "", "Convalidação", "Convalidação"),
    (date(2026, 10, 8), Marcador.RETIFICADO, "Autorização · Retificado", "Retificado"),
    (date(2026, 9, 1), Marcador.RETIFICADO, "Convalidação", "Convalidação"),  # não vale
    (date(2026, 10, 8), Marcador.COMPLEMENTAR, "Autorização · Complementar", "Complementar"),
    (date(2026, 9, 1), Marcador.COMPLEMENTAR, "Convalidação · Complementar",
     "Convalidação · Complementar"),
])
def test_tipo_do_oficio(saida, marcador, completo, selo):
    tipo = tipo_do_oficio(OFICIO, saida, marcador)
    assert (tipo.completo, tipo.selo) == (completo, selo)
    assert tipo.incomum is bool(selo)
    # coerente com o assunto que vai no documento
    assert tipo.autorizacao is resolver_assunto(OFICIO, saida, marcador).autorizacao


def test_tipo_explica_o_porque():
    assert "8 dias depois do ofício" in tipo_do_oficio(OFICIO, date(2026, 10, 6)).porque
    assert "no mesmo dia do ofício" in tipo_do_oficio(OFICIO, date(2026, 9, 28)).porque
    assert "antes do ofício" in tipo_do_oficio(OFICIO, date(2026, 9, 1)).porque
    assert "Sem data de saída" in tipo_do_oficio(OFICIO, None).porque
    assert "1 dia depois" in tipo_do_oficio(OFICIO, date(2026, 9, 29)).porque
    retificado_ignorado = tipo_do_oficio(OFICIO, date(2026, 9, 1), Marcador.RETIFICADO)
    assert "não vale na convalidação" in retificado_ignorado.porque
    assert "acrescenta" in tipo_do_oficio(OFICIO, date(2026, 10, 8),
                                          Marcador.COMPLEMENTAR).porque
