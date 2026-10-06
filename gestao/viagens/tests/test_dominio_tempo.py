"""Selo de tempo das listas (D3) e orçamento de selos da linha (D4) — domínio puro."""

from __future__ import annotations

from datetime import date

import pytest

from gestao.viagens.dominio.selos import TipoAlerta, alerta_da_linha
from gestao.viagens.dominio.tempo import Momento, selo_tempo

HOJE = date(2026, 10, 6)


def _dia(n: int) -> date:
    return date.fromordinal(HOJE.toordinal() + n)


@pytest.mark.parametrize(("inicio", "fim", "texto", "momento", "aviso"), [
    # Futuro: a contagem, com aviso a partir do prazo (10 dias, inclusive).
    (_dia(30), _dia(32), "faltam 30 dias", Momento.FUTURO, False),
    (_dia(11), _dia(12), "faltam 11 dias", Momento.FUTURO, False),
    (_dia(10), _dia(12), "faltam 10 dias", Momento.FUTURO, True),
    (_dia(2), _dia(2), "faltam 2 dias", Momento.FUTURO, True),
    # Iminente: amanhã e hoje pedem atenção.
    (_dia(1), _dia(3), "amanhã", Momento.IMINENTE, True),
    (HOJE, HOJE, "hoje", Momento.IMINENTE, True),               # viagem de um dia
    (HOJE, _dia(3), "começa hoje", Momento.IMINENTE, True),     # vários dias
    # Em andamento: nunca "há N dias" (era o defeito da lista de ofícios).
    (_dia(-1), _dia(9), "em andamento · até 15/10", Momento.EM_ANDAMENTO, False),
    (_dia(-2), _dia(1), "em andamento · até 07/10", Momento.EM_ANDAMENTO, False),
    (_dia(-3), HOJE, "volta hoje", Momento.EM_ANDAMENTO, False),
])
def test_selo_por_fronteira(inicio, fim, texto, momento, aviso):
    selo = selo_tempo(inicio, fim, HOJE)
    assert selo is not None
    assert (selo.texto, selo.momento, selo.aviso) == (texto, momento, aviso)


@pytest.mark.parametrize(("inicio", "fim"), [
    (_dia(-5), _dia(-1)),      # terminou ontem
    (_dia(-671), _dia(-669)),  # "há 671 dias" era ruído: o passado não pede ação
    (_dia(-1), None),          # sem volta: vale o dia da saída, que já passou
    (None, None),              # sem data
    (None, _dia(3)),           # só a volta não basta para contar
])
def test_sem_selo(inicio, fim):
    assert selo_tempo(inicio, fim, HOJE) is None


def test_sem_volta_conta_como_viagem_de_um_dia():
    assert selo_tempo(HOJE, None, HOJE).texto == "hoje"
    assert selo_tempo(_dia(4), None, HOJE).texto == "faltam 4 dias"


def test_volta_antes_da_saida_nao_inventa_andamento():
    """Dado incoerente (volta antes da saída) vira viagem de um dia, nunca "em andamento"."""
    assert selo_tempo(HOJE, _dia(-2), HOJE).texto == "hoje"
    assert selo_tempo(_dia(-2), _dia(-4), HOJE) is None


def test_prazo_da_unidade():
    assert selo_tempo(_dia(12), None, HOJE, prazo_dias=15).aviso is True
    assert selo_tempo(_dia(5), None, HOJE, prazo_dias=3).aviso is False
    # amanhã/hoje pedem atenção qualquer que seja o prazo
    assert selo_tempo(_dia(1), None, HOJE, prazo_dias=0).aviso is True


def test_dias_ate_o_inicio():
    assert selo_tempo(_dia(7), None, HOJE).dias == 7
    assert selo_tempo(_dia(-1), _dia(2), HOJE).dias == -1


# ---------------------------------------------------------------- orçamento de selos (D4)
def test_justificativa_pendente_vence_o_tempo():
    tempo = selo_tempo(_dia(3), None, HOJE)
    alerta = alerta_da_linha(justificativa_pendente=True, tempo=tempo)
    assert alerta.tipo is TipoAlerta.JUSTIFICATIVA and alerta.tempo is None


def test_prazo_e_depois_o_tempo():
    assert alerta_da_linha(justificativa_pendente=False,
                           tempo=selo_tempo(_dia(3), None, HOJE)).tipo is TipoAlerta.PRAZO
    assert alerta_da_linha(justificativa_pendente=False,
                           tempo=selo_tempo(_dia(30), None, HOJE)).tipo is TipoAlerta.TEMPO
    andamento = alerta_da_linha(justificativa_pendente=False,
                                tempo=selo_tempo(_dia(-1), _dia(2), HOJE))
    assert andamento.tipo is TipoAlerta.TEMPO and andamento.tempo.momento is Momento.EM_ANDAMENTO


def test_sem_nada_a_dizer_nao_ha_alerta():
    assert alerta_da_linha(justificativa_pendente=False, tempo=None) is None
