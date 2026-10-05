"""Prazos da prestação de contas (domínio puro): Páscoa, feriados, dias úteis e selos."""

from __future__ import annotations

from datetime import date

from gestao.viagens.dominio import prestacao as p


def test_pascoa_e_moveis():
    assert p.pascoa(2026) == date(2026, 4, 5)
    assert p.pascoa(2027) == date(2027, 3, 28)
    f = p.feriados_nacionais(2026)
    assert date(2026, 2, 16) in f and date(2026, 2, 17) in f  # Carnaval
    assert date(2026, 4, 3) in f  # Sexta-feira Santa
    assert date(2026, 6, 4) in f  # Corpus Christi
    assert date(2026, 11, 20) in f and date(2026, 9, 7) in f


def test_somar_dias_uteis_pula_fim_de_semana_e_feriado():
    # Sexta 02/10/2026 + 3 úteis: seg 05, ter 06, qua 07.
    assert p.somar_dias_uteis(date(2026, 10, 2), 3) == date(2026, 10, 7)
    # Sexta 09/10 + 3: seg 12 é feriado → ter 13, qua 14, qui 15.
    assert p.somar_dias_uteis(date(2026, 10, 9), 3) == date(2026, 10, 15)
    # Feriado extra (da unidade) também conta.
    assert p.somar_dias_uteis(date(2026, 10, 2), 1, [date(2026, 10, 5)]) == date(2026, 10, 6)


def test_prazo_para_prestar_conta_do_fim_do_saque():
    assert p.prazo_para_prestar(date(2026, 10, 2)) == date(2026, 10, 7)
    assert p.prazo_para_prestar(None) is None


def test_selos_do_saque():
    hoje = date(2026, 10, 5)
    assert p.selo_do_saque(date(2026, 10, 1), finalizada=False, tem_comprovante=False,
                           hoje=hoje).texto == "Prazo de saque vencido"
    assert p.selo_do_saque(hoje, finalizada=False, tem_comprovante=False,
                           hoje=hoje).texto == "Saque vence hoje"
    assert p.selo_do_saque(date(2026, 10, 7), finalizada=False, tem_comprovante=False,
                           hoje=hoje).texto == "Saque vence em 2 dias"
    assert p.selo_do_saque(date(2026, 10, 20), finalizada=False, tem_comprovante=False,
                           hoje=hoje) is None
    assert p.selo_do_saque(date(2026, 10, 1), finalizada=False, tem_comprovante=True,
                           hoje=hoje) is None


def test_selos_da_prestacao():
    # Saque até 02/10 → prestar até 07/10.
    assert p.selo_da_prestacao(date(2026, 10, 2), finalizada=False,
                               hoje=date(2026, 10, 9)).texto == "Prestação vencida em 07/10"
    assert p.selo_da_prestacao(date(2026, 10, 2), finalizada=False,
                               hoje=date(2026, 10, 7)).texto == "Prestar contas hoje (07/10)"
    s = p.selo_da_prestacao(date(2026, 10, 2), finalizada=False, hoje=date(2026, 10, 6))
    assert s.texto == "Prestar contas até 07/10 — falta 1 dia útil" and s.tom == "alerta"
    assert p.selo_da_prestacao(date(2026, 10, 2), finalizada=True, hoje=date(2026, 10, 9)) is None


def test_feriados_com_nome_iguais_aos_que_contam_nos_prazos():
    nomes = p.feriados_nacionais_com_nome(2026)
    assert set(nomes) == p.feriados_nacionais(2026)
    assert nomes[date(2026, 6, 4)] == "Corpus Christi"
    assert nomes[date(2026, 10, 12)] == "Nossa Senhora Aparecida"
