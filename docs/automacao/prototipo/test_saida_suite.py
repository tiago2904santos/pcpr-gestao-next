"""Código de saída da suíte principal (C8 do PR #23), sem Docker nem simuladores.

    .venv/Scripts/python.exe -m unittest docs/automacao/prototipo/test_saida_suite.py -v

Roda o `main()` de verdade de `testar_prototipo.py` com a infraestrutura trocada por dublês
(n8n, simuladores, medições) e um cenário que sempre passa. Afirma: export com erro → saída 1;
export ok → 0; cenário que falha → 1. Nada sobe, nada é escrito em `docs/automacao/n8n/`.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from io import BytesIO, TextIOWrapper
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import testar_prototipo as tp  # noqa: E402


def _rodar(export_falha: bool, cenario_passa: bool = True) -> tuple[int, dict]:
    def cenario() -> dict:
        if not cenario_passa:
            raise tp.Falha("falha simulada no cenário")
        return {"ok": True}

    def exportar(_tmp: Path) -> dict:
        if export_falha:
            raise tp.Falha("export simulado com erro")
        return {"arquivos": {}}

    with tempfile.TemporaryDirectory() as d, ExitStack() as pilha:
        relatorio = Path(d) / "relatorio.json"
        dubles = {
            (tp, "rodar_t11"): lambda: {"id": "T11", "nome": "dublê", "passou": True},
            (tp, "rodar_t20"): lambda: {"id": "T20", "nome": "dublê", "passou": True},
            (tp, "subir_simuladores"): lambda _d: [],
            (tp.cw, "construir"): lambda destino, *_a, **_k: destino.mkdir(parents=True),
            (tp, "memoria_em_repouso"): lambda *_a, **_k: {"mediana": 1.0},
            (tp, "exportar_workflows"): exportar,
            (tp, "portas_abertas"): lambda: [],
            (tp, "est_canal"): lambda: {"inbound": [], "downloads": []},
            (tp, "CENARIOS"): [("TX", "cenário dublê", cenario)],
            (tp.n8n_local, "preparar"): lambda *_a, **_k: "ok",
            (tp.n8n_local, "subir"): lambda *_a, **_k: None,
            (tp.n8n_local, "esperar_pronto"): lambda *_a, **_k: 0.1,
            (tp.n8n_local, "config_efetiva"): lambda: {},
            (tp.n8n_local, "memoria_bytes"): lambda: None,
            (tp.n8n_local, "tamanho_banco"): lambda: {},
            (tp.n8n_local, "logs"): lambda *_a, **_k: "",
            (tp.n8n_local, "parar"): lambda: None,
            (tp.n8n_local, "remover"): lambda: None,
            (tp.n8n_local, "existe"): lambda: False,
            (tp.time, "sleep"): lambda *_a: None,
        }
        for (alvo, nome), valor in dubles.items():
            pilha.enter_context(mock.patch.object(alvo, nome, valor))
        argv = ["testar_prototipo.py", "--apenas", "TX", "--relatorio", str(relatorio)]
        pilha.enter_context(mock.patch.object(sys, "argv", argv))
        with redirect_stdout(TextIOWrapper(BytesIO(), encoding="utf-8")):
            codigo = tp.main()
        return codigo, json.loads(relatorio.read_text(encoding="utf-8"))


class CodigoDeSaida(unittest.TestCase):
    def test_export_com_erro_reprova(self) -> None:
        codigo, rel = _rodar(export_falha=True)
        self.assertIn("erro", rel["exportacao"])
        self.assertTrue(all(c["passou"] for c in rel["cenarios"]))
        self.assertEqual(codigo, 1)

    def test_export_ok_aprova(self) -> None:
        codigo, rel = _rodar(export_falha=False)
        self.assertNotIn("erro", rel["exportacao"])
        self.assertEqual(codigo, 0)

    def test_cenario_que_falha_reprova(self) -> None:
        codigo, rel = _rodar(export_falha=False, cenario_passa=False)
        self.assertFalse(rel["cenarios"][-1]["passou"])
        self.assertEqual(codigo, 1)


if __name__ == "__main__":
    unittest.main()
