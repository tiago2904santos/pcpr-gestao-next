"""Recortes da lista de ofícios (D1/D2): abas temporais, documento e endereços antigos —
domínio puro, sem banco."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gestao.viagens.dominio import recorte
from gestao.viagens.dominio.recorte import SituacaoDoOficio as S

FIM_DE_HOJE = datetime(2026, 10, 7, 23, 59, 59, 999999, tzinfo=UTC)


def _s(**kw) -> S:
    base = {"cancelado": False, "contas_prestadas": False, "primeira_saida": None}
    return S(**{**base, **kw})


@pytest.mark.parametrize(("situacao", "aba"), [
    # Sem data: ainda não aconteceu — o rascunho sem roteiro fica entre os que vão acontecer.
    (_s(rascunho=True), recorte.FUTUROS),
    # Fronteira do fim de hoje: até ela, já começou; um instante depois, ainda vai acontecer.
    (_s(primeira_saida=FIM_DE_HOJE), recorte.ANDAMENTO),
    (_s(primeira_saida=FIM_DE_HOJE + timedelta(microseconds=1)), recorte.FUTUROS),
    (_s(primeira_saida=FIM_DE_HOJE - timedelta(days=400)), recorte.ANDAMENTO),
    # Contas prestadas vence o tempo; cancelado vence tudo.
    (_s(primeira_saida=FIM_DE_HOJE - timedelta(days=3), contas_prestadas=True),
     recorte.PRESTADAS),
    (_s(primeira_saida=FIM_DE_HOJE + timedelta(days=3), cancelado=True), recorte.CANCELADOS),
    (_s(cancelado=True, contas_prestadas=True), recorte.CANCELADOS),
])
def test_aba_do_oficio_segue_a_regra_da_referencia(situacao, aba):
    assert recorte.aba_do_oficio(situacao, FIM_DE_HOJE) == aba


def test_documento_e_arquivado_fora_de_todos():
    arquivado = _s(arquivado=True, rascunho=True)
    assert recorte.documento_do_oficio(arquivado) == recorte.ARQUIVADO
    assert not recorte.no_recorte(arquivado, "", "", FIM_DE_HOJE)
    assert recorte.no_recorte(arquivado, "", recorte.ARQUIVADO, FIM_DE_HOJE)
    # Arquivado continua nas abas temporais quando pedido (sem data → que vão acontecer).
    assert recorte.no_recorte(arquivado, recorte.FUTUROS, recorte.ARQUIVADO, FIM_DE_HOJE)
    assert not recorte.no_recorte(arquivado, recorte.ANDAMENTO, recorte.ARQUIVADO, FIM_DE_HOJE)


def test_documento_combina_com_a_aba():
    rascunho_futuro = _s(rascunho=True, primeira_saida=FIM_DE_HOJE + timedelta(days=2))
    assert recorte.no_recorte(rascunho_futuro, recorte.FUTUROS, recorte.RASCUNHO, FIM_DE_HOJE)
    assert not recorte.no_recorte(rascunho_futuro, recorte.FUTUROS, recorte.EMITIDO,
                                  FIM_DE_HOJE)
    assert not recorte.no_recorte(rascunho_futuro, recorte.ANDAMENTO, "", FIM_DE_HOJE)
    cancelado = _s(cancelado=True)
    assert recorte.no_recorte(cancelado, recorte.CANCELADOS, "", FIM_DE_HOJE)
    assert not recorte.no_recorte(cancelado, recorte.CANCELADOS, recorte.RASCUNHO,
                                  FIM_DE_HOJE)


@pytest.mark.parametrize(("antigo", "novo"), [
    ({"situacao": "rascunho"}, {"documento": "rascunho"}),
    ({"situacao": "emitido", "q": "x"}, {"documento": "emitido", "q": "x"}),
    ({"situacao": "arquivado", "q": "5/2026"}, {"documento": "arquivado", "q": "5/2026"}),
    ({"situacao": "cancelado", "pagina": "2"}, {"aba": "cancelados", "pagina": "2"}),
    ({"situacao": "proximos", "ordem": "saida"}, {"aba": "futuros", "ordem": "saida"}),
    ({"situacao": "prestadas"}, {"aba": "prestadas"}),
    ({"situacao": ""}, {}),
    ({"situacao": "inventada", "q": "a"}, {"q": "a"}),
    # O que já vem no vocabulário novo vale sobre a tradução.
    ({"situacao": "rascunho", "documento": "emitido"}, {"documento": "emitido"}),
])
def test_endereco_antigo_vira_o_recorte_equivalente(antigo, novo):
    assert recorte.traduzir_endereco_antigo(antigo) == novo


def test_endereco_novo_nao_e_traduzido():
    assert recorte.traduzir_endereco_antigo({"aba": "futuros"}) is None


def test_rotulos_honestos_da_ordem():
    assert recorte.rotulo(recorte.ORDENS, "saida") == "Saída, mais antiga primeiro"
    assert "próximas" not in " ".join(r for _, r in recorte.ORDENS)
    assert recorte.ORDEM_PADRAO in recorte.CHAVES_ORDENS
