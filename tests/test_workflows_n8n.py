"""Workflows n8n para a API real (`docs/automacao/n8n/pcpr/`): os exportados são o que o
gerador produz (nós e ligações), e o W7 V1 não baixa mídia acima do limite do PCPR — confere
o `file_size` dos metadados e manda o anexo grande para `/recebimentos/sem-arquivo`."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from gestao.integracoes.whatsapp.config import TAMANHO_MAXIMO_MIDIA

RAIZ = Path(__file__).resolve().parents[1]
PROTOTIPO = RAIZ / "docs" / "automacao" / "prototipo"
EXPORTADOS = RAIZ / "docs" / "automacao" / "n8n" / "pcpr"


def _gerador():
    spec = importlib.util.spec_from_file_location("construir_workflows",
                                                  PROTOTIPO / "construir_workflows.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("construir_workflows", modulo)
    spec.loader.exec_module(modulo)
    return modulo


def _ligacoes(wf: dict, origem: str) -> list[list[str]]:
    return [[c["node"] for c in saida] for saida in wf["connections"][origem]["main"]]


def test_exportados_para_o_pcpr_sao_os_do_gerador(tmp_path):
    gerador = _gerador()
    for gerado in gerador.construir(tmp_path, alvo="pcpr"):
        exportado = json.loads((EXPORTADOS / gerado.name).read_text(encoding="utf-8"))
        novo = json.loads(gerado.read_text(encoding="utf-8"))
        assert exportado["nodes"] == novo["nodes"], gerado.name
        assert exportado["connections"] == novo["connections"], gerado.name
        assert exportado["active"] is False


def test_w7_nao_baixa_midia_acima_do_limite():
    gerador = _gerador()
    assert gerador.LIMITE_MIDIA_PADRAO == TAMANHO_MAXIMO_MIDIA
    wf = gerador.w7("pcpr")
    nos = {n["name"]: n for n in wf["nodes"]}
    assert _ligacoes(wf, "Obter URL da mídia") == [["Cabe no limite?"]]  # nunca direto
    assert _ligacoes(wf, "Cabe no limite?") == [["Baixar mídia"],
                                                ["Registrar mídia acima do limite"]]
    acima = nos["Registrar mídia acima do limite"]["parameters"]
    assert acima["url"].endswith("/recebimentos/sem-arquivo")
    assert "motivo: 'acima_do_limite'" in acima["jsonBody"]
    assert _ligacoes(wf, "Registrar mídia acima do limite") == [["Juntar"]]
    condicao = nos["Cabe no limite?"]["parameters"]["conditions"]["conditions"][0]["leftValue"]
    assert str(TAMANHO_MAXIMO_MIDIA) in condicao
    outra = {n["name"]: n for n in gerador.w7("pcpr", 5000)["nodes"]}
    assert "> 5000)" in outra["Cabe no limite?"]["parameters"]["conditions"]["conditions"][0][
        "leftValue"]
    no_node = shutil.which("node")
    if no_node is None:
        pytest.skip("Node indisponível para avaliar a expressão")
    expressao = condicao.removeprefix("={{").removesuffix("}}").strip()
    casos = {"grande": {"file_size": TAMANHO_MAXIMO_MIDIA + 1},
             "no_limite": {"file_size": TAMANHO_MAXIMO_MIDIA}, "sem_tamanho": {}}
    js = (f"const f = ($json) => {expressao};\n"
          f"const casos = {json.dumps(casos)};\n"
          "console.log(JSON.stringify(Object.fromEntries("
          "Object.entries(casos).map(([k, v]) => [k, f(v)]))));")
    r = subprocess.run([no_node, "-e", js], capture_output=True, text=True, timeout=30)  # noqa: S603  # nosec
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {"grande": False, "no_limite": True, "sem_tamanho": True}
