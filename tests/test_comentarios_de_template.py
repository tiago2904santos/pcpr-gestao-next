"""O comentário curto do Django (`{# … #}`) não atravessa linhas.

Quando alguém abre `{#` numa linha e fecha `#}` na seguinte, o Django não reconhece o
comentário: o texto vai parar **na tela do usuário**. Já escapou três vezes neste projeto.
Comentário de mais de uma linha é `{% comment %}` / `{% endcomment %}`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
TEMPLATES = sorted([
    *RAIZ.glob("templates/**/*.html"),
    *RAIZ.glob("gestao/**/templates/**/*.html"),
])


@pytest.mark.parametrize("arquivo", TEMPLATES, ids=lambda p: str(p.relative_to(RAIZ)))
def test_comentario_curto_fecha_na_mesma_linha(arquivo: Path):
    abertos = [
        f"linha {numero}: {linha.strip()[:80]}"
        for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1)
        for achado in re.finditer(r"\{#", linha)
        if "#}" not in linha[achado.start():]
    ]
    assert not abertos, (
        f"{arquivo.relative_to(RAIZ)}: `{{#` sem `#}}` na mesma linha — o texto vaza para a "
        f"tela. Use {{% comment %}}…{{% endcomment %}}.\n" + "\n".join(abertos))


def test_a_varredura_encontrou_templates():
    """Rede de segurança: se o glob parar de achar arquivos, o teste acima vira enfeite."""
    assert len(TEMPLATES) > 20
