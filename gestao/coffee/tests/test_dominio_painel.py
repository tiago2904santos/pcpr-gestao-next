"""CB6a: regras puras do painel e das entregas — ritmo dos 3 meses completos, projeção do
saldo (exemplo da especificação), limite de 15%, faixas de vigência, "parada há N dias" e os
grupos de "O que fazer hoje"."""

from __future__ import annotations

from datetime import date, timedelta

from gestao.coffee import dominio_painel as r

HOJE = date(2026, 10, 6)


def test_meses_completos_e_ritmo():
    assert r.meses_completos(HOJE) == [(2026, 7), (2026, 8), (2026, 9)]
    assert r.meses_completos(date(2026, 2, 15)) == [(2025, 11), (2025, 12), (2026, 1)]
    consumo = {(2026, 7): 90, (2026, 8): 120, (2026, 9): 90, (2026, 10): 500, (2026, 6): 999}
    assert r.ritmo(consumo, HOJE) == 100  # o mês corrente e os anteriores não entram
    assert r.ritmo({}, HOJE) == 0


def test_alerta_de_saldo_exemplo_da_especificacao():
    # restante 300, ritmo 100/mês, fim em 120 dias → acaba em ~91 dias (antes) → alerta.
    fim = HOJE + timedelta(days=120)
    alerta = r.alerta_de_saldo(300, 1000, 100.0, fim, HOJE)
    assert alerta is not None
    assert alerta.acaba_em == HOJE + timedelta(days=91)
    assert alerta.texto == (
        f"No ritmo dos últimos 3 meses (100,0 por mês), os 300 de saldo acabam por volta de "
        f"{HOJE + timedelta(days=91):%d/%m/%Y}, antes do fim do contrato ({fim:%d/%m/%Y}): "
        "providencie o aditivo ou o reforço.")
    sobra = r.sobra_no_fim(300, 100.0, fim, HOJE)
    assert sobra is not None and round(sobra) == -94


def test_alerta_de_saldo_sem_projecao_e_folgado():
    fim = HOJE + timedelta(days=120)
    assert r.alerta_de_saldo(900, 1000, 100.0, fim, HOJE) is None  # acaba depois do fim
    # Sem ritmo: só o limite de 15%.
    assert r.alerta_de_saldo(150, 1000, 0, fim, HOJE).texto == (
        "Restam apenas 150 de 1000 unidades (limite de alerta: 15%).")
    assert r.alerta_de_saldo(151, 1000, 0, fim, HOJE) is None
    assert r.alerta_de_saldo(100, 1000, 50.0, None, HOJE) is not None  # sem fim: limite
    assert r.sobra_no_fim(100, 0, fim, HOJE) is None
    assert r.alerta_de_saldo(0, 0, 0, fim, HOJE) is None  # lote sem quantidade não alerta


def test_alerta_de_vigencia_faixas():
    assert r.alerta_de_vigencia(None, HOJE) == ""
    assert r.alerta_de_vigencia(HOJE + timedelta(days=91), HOJE) == ""
    fim = HOJE + timedelta(days=45)
    assert r.alerta_de_vigencia(fim, HOJE) == (
        f"A vigência termina em {fim:%d/%m/%Y} (em 45 dias, faixa de 60 dias). Providencie o "
        "aditivo de prorrogação.")
    assert "faixa de 30 dias" in r.alerta_de_vigencia(HOJE, HOJE)
    assert "faixa de 90 dias" in r.alerta_de_vigencia(HOJE + timedelta(days=90), HOJE)
    vencido = HOJE - timedelta(days=1)
    assert r.alerta_de_vigencia(vencido, HOJE) == (
        f"Vigência encerrada em {vencido:%d/%m/%Y}. Novas solicitações com evento depois dessa "
        "data não são aceitas neste contrato.")


def test_parada():
    assert r.dias_parada(HOJE - timedelta(days=10), None, HOJE) == 10
    # O fim do evento conta quando é posterior ao último histórico.
    assert r.dias_parada(HOJE - timedelta(days=10), HOJE - timedelta(days=3), HOJE) == 3
    assert r.dias_parada(HOJE, HOJE + timedelta(days=2), HOJE) == 0
    assert r.texto_parada(0) == "Parada hoje"
    assert r.texto_parada(1) == "Parada há 1 dia"
    assert r.texto_parada(8) == "Parada há 8 dias"


def test_grupos_na_ordem_do_fluxo():
    base = {"cancelada": False, "concluida": False, "data_evento": None, "nota": False,
            "oficio": False, "protocolo": False, "ob": False, "hoje": HOJE}
    assert r.grupo_de(**base) is None  # sem data e sem nota: nada a fazer hoje
    assert r.grupo_de(**{**base, "data_evento": HOJE + timedelta(days=7)}) == "entregas"
    assert r.grupo_de(**{**base, "data_evento": HOJE + timedelta(days=8)}) is None
    assert r.grupo_de(**{**base, "data_evento": HOJE - timedelta(days=1)}) == "sem_nota"
    assert r.grupo_de(**{**base, "nota": True}) == "sem_oficio"
    assert r.grupo_de(**{**base, "nota": True, "oficio": True}) == "sem_protocolo"
    assert r.grupo_de(**{**base, "nota": True, "oficio": True, "protocolo": True}) == "sem_ob"
    assert r.grupo_de(**{**base, "protocolo": True, "ob": True}) == "ob_nao_enviada"
    assert r.grupo_de(**{**base, "ob": True, "concluida": True}) is None
    assert r.grupo_de(**{**base, "ob": True, "cancelada": True}) is None
    assert [g[0] for g in r.GRUPOS] == ["entregas", "sem_nota", "sem_oficio", "sem_protocolo",
                                        "sem_ob", "ob_nao_enviada"]
