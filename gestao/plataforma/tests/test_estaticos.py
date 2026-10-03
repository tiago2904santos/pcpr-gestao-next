"""CSS minificado de produção: menor e com o mesmo significado."""

from __future__ import annotations

import re
import shutil
import subprocess  # nosec B404 — só `node --check` nos testes
from pathlib import Path

import pytest

from gestao.plataforma.estaticos import minificar, minificar_css

ESTATICOS = Path(__file__).resolve().parents[3] / "static"
CSS = ESTATICOS / "css"


def test_tira_comentarios_e_espacos_sem_mudar_o_sentido():
    fonte = """/* título */
.a :hover , .b > .c {
  width: calc(100% - 2rem);   /* espaço do calc fica */
  content: "a /* não é comentário */ , b";
}
@media (max-width: 767.98px) {
  .d { margin: 0 auto ; }
}
"""
    saida = minificar_css(fonte)
    assert "título" not in saida and "espaço do calc" not in saida
    assert ".a :hover,.b>.c{" in saida  # descendente preservado
    assert "calc(100% - 2rem)" in saida
    assert '"a /* não é comentário */ , b"' in saida  # string intocada
    assert "@media (max-width: 767.98px){.d{margin: 0 auto}}" in saida


def test_os_pacotes_reais_ficam_bem_menores():
    total, minificado = 0, 0
    for arquivo in CSS.glob("*.css"):
        texto = arquivo.read_text(encoding="utf-8")
        total += len(texto)
        minificado += len(minificar_css(texto))
        assert minificado <= total
        # Nada de regra foi cortado: as chaves de abertura continuam todas lá.
        saida = minificar_css(texto)
        assert saida.count("{") - saida.count("}") == texto.count("{") - texto.count("}")
        assert "*/" not in saida
    assert minificado < total * 0.8


def test_js_minificado_mantem_as_exportacoes_e_encolhe():
    for arquivo in (ESTATICOS / "js").rglob("*.js"):
        fonte = arquivo.read_text(encoding="utf-8")
        saida = minificar(arquivo.name, fonte)
        assert saida is not None and len(saida) < len(fonte)
        for nome in re.findall(r"^export (?:async )?(?:function|class|const) (\w+)", fonte, re.M):
            assert nome in saida, f"{arquivo.name}: perdeu a exportação {nome}"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node indisponível")
def test_js_minificado_continua_valido(tmp_path):
    """Cada módulo minificado passa pela checagem de sintaxe do Node."""
    for arquivo in (ESTATICOS / "js").rglob("*.js"):
        destino = tmp_path / f"{arquivo.stem}.mjs"
        destino.write_text(minificar(arquivo.name, arquivo.read_text(encoding="utf-8")) or "",
                           encoding="utf-8")
        r = subprocess.run(["node", "--check", str(destino)], capture_output=True, text=True)  # noqa: S603, S607  # nosec
        assert r.returncode == 0, f"{arquivo.name}: {r.stderr[:300]}"


def test_htmx_ja_minificado_nao_e_mexido():
    assert minificar("vendor/htmx.min.js", "var a = 1;") is None
