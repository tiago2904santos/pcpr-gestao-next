"""Testes unitários do validador stdlib do envelope de eventos (C2 do PR #23), sem Docker.

    .venv/Scripts/python.exe -m unittest docs/automacao/prototipo/test_validar_esquema.py -v

Usa o esquema real (`evento-integracao.schema.json`) e envelopes gerados pelo próprio simulador
do PCPR (só em memória, nada é entregue): prova que o simulador emite só o que o contrato aceita
e que o validador reprova o que o contrato rejeita — inclusive o que a igualdade do Python
deixaria passar (`True == 1`).
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from comum import agora_utc  # noqa: E402
from simulador_pcpr import Estado  # noqa: E402
from validar_esquema import EsquemaNaoSuportado, validar  # noqa: E402

SCHEMA = json.loads(
    (RAIZ.parents[1] / "automacao" / "contratos" / "evento-integracao.schema.json").read_text(
        encoding="utf-8"
    )
)


def _envelopes_do_simulador() -> list[dict]:
    est = Estado("token-sintetico", b"segredo-sintetico", "http://127.0.0.1:9/nada", 600)
    _, _, confirmacao = est.confirmar_viagem(agora_utc() + timedelta(days=3), "link_km")
    vid = next(e for e in confirmacao if e["tipo"] == "viagem.confirmada")["recurso"]["id"]
    _, _, reagendamento = est.reagendar_viagem(vid, agora_utc() + timedelta(days=5))
    cancelamento = est.cancelar_viagem(vid)
    _, avulsa = est.criar_comunicacao_avulsa("documentos_para_assinatura", agora_utc())
    return confirmacao + reagendamento + cancelamento + avulsa


class EnvelopesDoSimulador(unittest.TestCase):
    def test_todos_os_envelopes_emitidos_sao_validos(self) -> None:
        envelopes = _envelopes_do_simulador()
        tipos = {e["tipo"] for e in envelopes}
        self.assertTrue(
            {
                "viagem.confirmada",
                "comunicacao.agendada",
                "viagem.reagendada",
                "comunicacao.cancelada",
                "viagem.cancelada",
            }
            <= tipos,
            tipos,
        )
        for e in envelopes:
            with self.subTest(tipo=e["tipo"]):
                self.assertEqual(validar(e, SCHEMA), [])


class Negativos(unittest.TestCase):
    """O que o esquema rejeita tem de ser reprovado (o T1 antigo aprovava `dados.rotulo`)."""

    def setUp(self) -> None:
        self.base = next(
            e for e in _envelopes_do_simulador() if e["tipo"] == "comunicacao.agendada"
        )
        self.assertEqual(validar(self.base, SCHEMA), [])

    def reprova(self, muda: Callable[[dict], object], trecho: str) -> None:
        ev = copy.deepcopy(self.base)
        muda(ev)
        erros = validar(ev, SCHEMA)
        self.assertTrue(erros, "o validador aprovou um envelope que o esquema rejeita")
        self.assertTrue(any(trecho in m for m in erros), erros)

    def test_campo_extra_em_dados(self) -> None:
        self.reprova(lambda ev: ev["dados"].update(rotulo="véspera"), "campo extra rotulo")

    def test_enum(self) -> None:
        self.reprova(lambda ev: ev["dados"].update(tipo_comunicacao="sms"), "fora do enum")

    def test_obrigatorio_em_dados(self) -> None:
        self.reprova(lambda ev: ev["dados"].pop("comunicacao_id"), "falta comunicacao_id")

    def test_then_do_tipo(self) -> None:
        self.reprova(lambda ev: ev["recurso"].update(tipo="viagem"), "")

    def test_campo_extra_na_raiz(self) -> None:
        self.reprova(lambda ev: ev.update(extra=1), "campo extra extra")

    def test_data_sem_fuso(self) -> None:
        self.reprova(lambda ev: ev.update(ocorrido_em="2026-10-17T12:00:00"), "date-time")

    def test_id_nao_uuid(self) -> None:
        self.reprova(lambda ev: ev.update(id="nao-e-uuid"), "uuid")

    def test_const_nao_aceita_booleano_no_lugar_de_numero(self) -> None:
        # no Python True == 1: a igualdade ingênua aprovaria (achado da 2ª verificação)
        self.reprova(lambda ev: ev.update(versao_contrato=True), "const")

    def test_const_nao_aceita_texto(self) -> None:
        self.reprova(lambda ev: ev.update(versao_contrato="1"), "const")

    def test_enum_nao_aceita_numero_no_lugar_de_booleano(self) -> None:
        self.reprova(lambda ev: ev["dados"].update(imediato=1), "imediato")

    def test_integer_recusa_booleano_e_fracao(self) -> None:
        self.reprova(lambda ev: ev["recurso"].update(id=True), "recurso.id")
        self.reprova(lambda ev: ev["recurso"].update(id=1.5), "recurso.id")


class Positivos(unittest.TestCase):
    def test_inteiro_com_ponto_decimal_e_inteiro(self) -> None:
        # JSON Schema: 1.0 é um inteiro (e é igual ao const 1)
        ev = next(e for e in _envelopes_do_simulador() if e["tipo"] == "comunicacao.agendada")
        ev = copy.deepcopy(ev)
        ev["versao_contrato"] = 1.0
        ev["recurso"]["id"] = float(ev["recurso"]["id"])
        self.assertEqual(validar(ev, SCHEMA), [])


class PalavraChaveDesconhecida(unittest.TestCase):
    def test_recusa_em_vez_de_ignorar(self) -> None:
        with self.assertRaises(EsquemaNaoSuportado):
            validar({"a": 1}, {"type": "object", "oneOf": [{"required": ["a"]}]})

    def test_ref_nao_local(self) -> None:
        with self.assertRaises(EsquemaNaoSuportado):
            validar(1, {"$ref": "https://exemplo.invalid/s.json"})


if __name__ == "__main__":
    unittest.main()
