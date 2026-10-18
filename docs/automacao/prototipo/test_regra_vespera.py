"""T11 — testes unitários da regra da véspera (stdlib unittest; roda também com pytest).

.venv/Scripts/python.exe -m unittest docs/automacao/prototipo/test_regra_vespera.py -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from regra_vespera import (
    AVISO_VIAGEM_JA_INICIADA,
    FUSO,
    ComunicacaoRef,
    ViagemRef,
    calcular_envio,
    instante_vespera,
    planejar,
)


def sp(*args: int) -> datetime:
    return datetime(*args, tzinfo=FUSO)


class CalcularEnvio(unittest.TestCase):
    def test_caso_normal_agenda_para_vespera_as_9h(self) -> None:
        d = calcular_envio(sp(2026, 11, 10, 6, 30), agora=sp(2026, 11, 1, 14, 0))
        self.assertEqual(d.enviar_em, sp(2026, 11, 9, 9, 0))
        self.assertFalse(d.imediato)
        self.assertIsNone(d.aviso)

    def test_inicio_a_meia_noite_usa_o_dia_anterior(self) -> None:
        d = calcular_envio(sp(2026, 11, 10, 0, 0), agora=sp(2026, 11, 1, 8, 0))
        self.assertEqual(d.enviar_em, sp(2026, 11, 9, 9, 0))

    def test_inicio_logo_apos_meia_noite_confirmado_na_noite_anterior_envia_ja(self) -> None:
        agora = sp(2026, 11, 9, 23, 50)
        d = calcular_envio(sp(2026, 11, 10, 0, 30), agora=agora)
        self.assertTrue(d.imediato)
        self.assertEqual(d.enviar_em, agora)
        self.assertIsNone(d.aviso)

    def test_data_local_e_nao_a_data_utc(self) -> None:
        # 02:30Z do dia 10 = 23:30 do dia 9 em São Paulo → véspera é o dia 8.
        inicio = datetime(2026, 11, 10, 2, 30, tzinfo=UTC)
        self.assertEqual(instante_vespera(inicio), sp(2026, 11, 8, 9, 0))

    def test_criacao_em_cima_da_hora_envia_imediatamente(self) -> None:
        inicio = sp(2026, 11, 10, 7, 0)
        d = calcular_envio(inicio, agora=inicio - timedelta(minutes=10))
        self.assertTrue(d.imediato)
        self.assertIsNone(d.aviso)

    def test_fronteira_exatamente_9h_envia_ja_e_um_microssegundo_antes_agenda(self) -> None:
        inicio = sp(2026, 11, 10, 8, 0)
        alvo = sp(2026, 11, 9, 9, 0)
        self.assertTrue(calcular_envio(inicio, agora=alvo).imediato)
        antes = calcular_envio(inicio, agora=alvo - timedelta(microseconds=1))
        self.assertFalse(antes.imediato)
        self.assertEqual(antes.enviar_em, alvo)

    def test_viagem_ja_iniciada_envia_com_aviso(self) -> None:
        inicio = sp(2026, 11, 10, 8, 0)
        d = calcular_envio(inicio, agora=inicio + timedelta(hours=3))
        self.assertTrue(d.imediato)
        self.assertEqual(d.aviso, AVISO_VIAGEM_JA_INICIADA)
        d0 = calcular_envio(inicio, agora=inicio)  # no instante exato do início
        self.assertEqual(d0.aviso, AVISO_VIAGEM_JA_INICIADA)

    def test_resultado_sempre_no_fuso_de_sao_paulo(self) -> None:
        agora_utc = datetime(2026, 11, 9, 13, 0, tzinfo=UTC)  # 10:00 em SP
        d = calcular_envio(sp(2026, 11, 10, 8, 0), agora=agora_utc)
        self.assertEqual(d.enviar_em.utcoffset(), timedelta(hours=-3))
        self.assertEqual(d.enviar_em, agora_utc)

    def test_horario_de_verao_historico_e_respeitado(self) -> None:
        # 2018: o horário de verão começou em 04/11 (00:00 virou 01:00), offset -02:00.
        d = calcular_envio(sp(2018, 11, 5, 8, 0), agora=sp(2018, 10, 20, 8, 0))
        self.assertEqual(d.enviar_em.utcoffset(), timedelta(hours=-2))
        self.assertEqual(d.enviar_em.astimezone(UTC), datetime(2018, 11, 4, 11, 0, tzinfo=UTC))

    def test_datetime_sem_fuso_e_recusado(self) -> None:
        with self.assertRaises(ValueError):
            calcular_envio(datetime(2026, 11, 10, 8, 0), agora=sp(2026, 11, 1, 8, 0))
        with self.assertRaises(ValueError):
            calcular_envio(sp(2026, 11, 10, 8, 0), agora=datetime(2026, 11, 1, 8, 0))


class Planejar(unittest.TestCase):
    agora = sp(2026, 11, 1, 10, 0)

    def test_confirmacao_cria_comunicacao(self) -> None:
        p = planejar(ViagemRef(versao=1, inicio=sp(2026, 11, 10, 6, 30)), None, self.agora)
        self.assertIsNotNone(p.criar)
        self.assertEqual(p.criar.enviar_em, sp(2026, 11, 9, 9, 0))
        self.assertIsNone(p.cancelar_id)

    def test_mudanca_de_data_recalcula_e_invalida_a_anterior_por_versao(self) -> None:
        atual = ComunicacaoRef(id=7, versao_viagem=1, estado="agendada")
        p = planejar(ViagemRef(versao=2, inicio=sp(2026, 11, 20, 6, 30)), atual, self.agora)
        self.assertEqual(p.cancelar_id, 7)
        self.assertEqual(p.motivo_cancelamento, "obsoleta")
        self.assertEqual(p.criar.enviar_em, sp(2026, 11, 19, 9, 0))

    def test_reagendar_para_dentro_da_janela_envia_ja(self) -> None:
        atual = ComunicacaoRef(id=7, versao_viagem=1, estado="agendada")
        p = planejar(ViagemRef(versao=2, inicio=sp(2026, 11, 1, 18, 0)), atual, self.agora)
        self.assertEqual(p.cancelar_id, 7)
        self.assertTrue(p.criar.imediato)

    def test_cancelamento_cancela_o_que_esta_agendado(self) -> None:
        atual = ComunicacaoRef(id=7, versao_viagem=1, estado="agendada")
        v = ViagemRef(versao=2, inicio=sp(2026, 11, 10, 6, 30), cancelada=True)
        p = planejar(v, atual, self.agora)
        self.assertEqual((p.cancelar_id, p.motivo_cancelamento), (7, "viagem_cancelada"))
        self.assertIsNone(p.criar)

    def test_cancelamento_sem_nada_pendente_nao_faz_nada(self) -> None:
        atual = ComunicacaoRef(id=7, versao_viagem=1, estado="enviada")
        v = ViagemRef(versao=2, inicio=sp(2026, 11, 10, 6, 30), cancelada=True)
        self.assertEqual(planejar(v, atual, self.agora).ignorado, "nada_pendente")

    def test_evento_fora_de_ordem_com_versao_antiga_e_ignorado(self) -> None:
        atual = ComunicacaoRef(id=7, versao_viagem=3, estado="agendada")
        p = planejar(ViagemRef(versao=2, inicio=sp(2026, 11, 10, 6, 30)), atual, self.agora)
        self.assertEqual(p.ignorado, "versao_antiga")
        self.assertIsNone(p.cancelar_id)
        self.assertIsNone(p.criar)

    def test_mesma_versao_e_idempotente(self) -> None:
        atual = ComunicacaoRef(id=7, versao_viagem=2, estado="agendada")
        p = planejar(ViagemRef(versao=2, inicio=sp(2026, 11, 10, 6, 30)), atual, self.agora)
        self.assertEqual(p.ignorado, "mesma_versao")

    def test_reagendamento_depois_de_enviada_cria_nova_sem_cancelar(self) -> None:
        atual = ComunicacaoRef(id=7, versao_viagem=1, estado="enviada")
        p = planejar(ViagemRef(versao=2, inicio=sp(2026, 11, 20, 6, 30)), atual, self.agora)
        self.assertIsNone(p.cancelar_id)
        self.assertIsNotNone(p.criar)


if __name__ == "__main__":
    unittest.main(verbosity=2)
