"""Bate-volta: viagens que saem da sede e voltam no mesmo dia, repetidas por vários dias.

Especificação: docs/superpowers/specs/2026-10-02-bate-volta-design.md
"""

from __future__ import annotations

from datetime import date, time

import pytest
from django.urls import reverse

from gestao.cadastros.models import Municipio
from gestao.viagens.dominio.bate_volta import BateVoltaInvalido, Bloco, expandir
from gestao.viagens.models import Roteiro

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    return cenario_completo()


@pytest.fixture
def operador(client, cenario):
    client.force_login(cenario.usuarios["operador"])
    return client


class TestExpansao:
    """Domínio puro: só calendário, sem banco."""

    def test_um_dia_vira_ida_e_volta(self):
        bloco = Bloco(2, date(2026, 10, 1), date(2026, 10, 1), time(8), time(18))
        pernas = expandir([bloco], sede_id=1)
        assert [(p.origem_id, p.destino_id) for p in pernas] == [(1, 2), (2, 1)]
        assert [p.saida_em.hour for p in pernas] == [8, 18]

    def test_dias_corridos_geram_duas_pernas_por_dia(self):
        bloco = Bloco(2, date(2026, 10, 1), date(2026, 10, 3), time(8), time(18))
        pernas = expandir([bloco], sede_id=1)
        assert len(pernas) == 6
        assert [p.saida_em.day for p in pernas] == [1, 1, 2, 2, 3, 3]

    def test_dois_blocos_seguem_a_ordem(self):
        """O caso do dono: São José dos Pinhais de 1 a 3, Rio Branco em 4 e 5."""
        blocos = [Bloco(2, date(2026, 10, 1), date(2026, 10, 3), time(8), time(18)),
                  Bloco(3, date(2026, 10, 4), date(2026, 10, 5), time(8), time(18))]
        pernas = expandir(blocos, sede_id=1)
        assert len(pernas) == 10
        assert {p.destino_id for p in pernas[:6]} == {1, 2}
        assert {p.destino_id for p in pernas[6:]} == {1, 3}

    def test_recusa_periodo_invertido(self):
        bloco = Bloco(2, date(2026, 10, 3), date(2026, 10, 1), time(8), time(18))
        with pytest.raises(BateVoltaInvalido, match="último dia"):
            expandir([bloco], sede_id=1)

    def test_recusa_volta_antes_da_saida(self):
        bloco = Bloco(2, date(2026, 10, 1), date(2026, 10, 1), time(18), time(8))
        with pytest.raises(BateVoltaInvalido, match="depois da saída"):
            expandir([bloco], sede_id=1)

    def test_recusa_periodos_sobrepostos(self):
        blocos = [Bloco(2, date(2026, 10, 1), date(2026, 10, 3), time(8), time(18)),
                  Bloco(3, date(2026, 10, 3), date(2026, 10, 5), time(8), time(18))]
        with pytest.raises(BateVoltaInvalido, match="sobrepor"):
            expandir(blocos, sede_id=1)

    def test_recusa_destino_igual_a_sede(self):
        bloco = Bloco(1, date(2026, 10, 1), date(2026, 10, 1), time(8), time(18))
        with pytest.raises(BateVoltaInvalido, match="própria sede"):
            expandir([bloco], sede_id=1)


def _post(**extra) -> dict:
    dados = {
        "sede-uf": "PR", "sede-cidade": "Curitiba/PR",
        "bate_volta": "on",
        "destino-TOTAL_FORMS": "0", "destino-INITIAL_FORMS": "0",
        "destino-MIN_NUM_FORMS": "0", "destino-MAX_NUM_FORMS": "10",
        "bv-TOTAL_FORMS": "2", "bv-INITIAL_FORMS": "0",
        "bv-MIN_NUM_FORMS": "1", "bv-MAX_NUM_FORMS": "10",
        "bv-0-uf": "PR", "bv-0-cidade": "São José dos Pinhais/PR", "bv-0-ORDER": "1",
        "bv-0-dia_inicial": "01/10/2026", "bv-0-dia_final": "03/10/2026",
        "bv-0-hora_saida": "08:00", "bv-0-hora_volta": "18:00",
        "bv-1-uf": "PR", "bv-1-cidade": "Rio Branco do Sul/PR", "bv-1-ORDER": "2",
        "bv-1-dia_inicial": "04/10/2026", "bv-1-dia_final": "05/10/2026",
        "bv-1-hora_saida": "08:00", "bv-1-hora_volta": "18:00",
    }
    dados.update(extra)
    return dados


class TestTela:
    def test_salva_blocos_e_trechos_expandidos(self, operador):
        r = operador.post(reverse("viagens:novo_roteiro"), _post())
        assert r.status_code == 302, r.content.decode()[:900]
        roteiro = Roteiro.objects.latest("pk")
        assert roteiro.bate_volta
        blocos = list(roteiro.bate_voltas.select_related("destino"))
        assert [(b.destino.nome, b.dia_inicial.day, b.dia_final.day) for b in blocos] == [
            ("São José dos Pinhais", 1, 3), ("Rio Branco do Sul", 4, 5)]
        trechos = list(roteiro.trechos.select_related("origem", "destino"))
        assert len(trechos) == 10  # cinco dias x ida e volta
        assert trechos[0].origem.nome == "Curitiba"
        assert trechos[0].destino.nome == "São José dos Pinhais"
        assert trechos[1].origem.nome == "São José dos Pinhais"
        assert trechos[1].destino.nome == "Curitiba"

    def test_reabrir_mostra_os_blocos_como_foram_digitados(self, operador):
        """A regressão que o R3 ensinou a vigiar: reabrir não pode perder o agrupamento."""
        operador.post(reverse("viagens:novo_roteiro"), _post())
        roteiro = Roteiro.objects.latest("pk")
        html = operador.get(reverse("viagens:editar_roteiro", args=[roteiro.pk])).content.decode()
        assert 'value="São José dos Pinhais/PR"' in html
        assert 'value="Rio Branco do Sul/PR"' in html
        assert 'value="01/10/2026"' in html and 'value="05/10/2026"' in html

    def test_desligar_o_modo_apaga_os_blocos(self, operador):
        operador.post(reverse("viagens:novo_roteiro"), _post())
        roteiro = Roteiro.objects.latest("pk")
        operador.post(reverse("viagens:editar_roteiro", args=[roteiro.pk]), {
            "sede-uf": "PR", "sede-cidade": "Curitiba/PR",
            "destino-TOTAL_FORMS": "0", "destino-INITIAL_FORMS": "0",
            "destino-MIN_NUM_FORMS": "0", "destino-MAX_NUM_FORMS": "10",
            "bv-TOTAL_FORMS": "0", "bv-INITIAL_FORMS": "0",
            "bv-MIN_NUM_FORMS": "1", "bv-MAX_NUM_FORMS": "10",
        })
        roteiro.refresh_from_db()
        assert not roteiro.bate_volta and roteiro.bate_voltas.count() == 0

    def test_recusa_acima_do_teto_de_trechos(self, operador):
        """Vinte e cinco dias passam dos 40 trechos."""
        r = operador.post(reverse("viagens:novo_roteiro"), _post(**{
            "bv-TOTAL_FORMS": "1",
            "bv-0-dia_inicial": "01/10/2026", "bv-0-dia_final": "25/10/2026",
        }))
        assert r.status_code == 422
        assert "limite é 40" in r.content.decode()


def test_dormir_em_casa_evita_a_diaria_inteira(operador):
    """Voltar para casa toda noite faz cada dia entrar sozinho na escada do resto: dez horas
    fora não viram diária de 24 h."""
    operador.post(reverse("viagens:novo_roteiro"), _post(**{
        "bv-TOTAL_FORMS": "1",
        "bv-0-cidade": "São José dos Pinhais/PR",
        "bv-0-dia_inicial": "01/10/2026", "bv-0-dia_final": "03/10/2026",
    }))
    roteiro = Roteiro.objects.latest("pk")
    assert roteiro.diarias_resumo, roteiro.diarias_erro
    parcelas = roteiro.diarias_calculo["parcelas"]
    assert all(p["percentual"] < 100 for p in parcelas), parcelas


def test_municipios_do_caso_existem():
    assert Municipio.objects.filter(nome="São José dos Pinhais", uf="PR").exists()
    assert Municipio.objects.filter(nome="Rio Branco do Sul", uf="PR").exists()
