"""Os tokens que vão na URL (feed ICS, link do fornecedor, link pessoal da automação) são
credenciais: o filtro do Django, o log de acesso do Gunicorn e os modelos de proxy (nginx e
Caddy) mascaram os mesmos prefixos — um prefixo novo num lugar só deixaria o token no log."""

from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
PREFIXOS = ("agenda/ics", "fornecedor", "p")


def test_filtro_do_django_mascara_todos():
    from gestao.plataforma.logs import _mascarar

    for prefixo in PREFIXOS:
        texto = f"GET /{prefixo}/AbCdEfGhIjKlMnOpQrStUvWxYz0123456789/ 200"
        assert "AbCdEfGh" not in _mascarar(texto), prefixo


def test_gunicorn_mascara_todos():
    """O padrão é lido do arquivo (o gunicorn não importa no Windows)."""
    import re

    texto = (RAIZ / "deploy" / "docker" / "gunicorn_conf.py").read_text(encoding="utf-8")
    padrao = re.compile(re.search(r'PADRAO = re.compile\(r"(.+)"\)', texto).group(1))
    for prefixo in PREFIXOS:
        assert "segredo" not in padrao.sub(r"[token]", f"/{prefixo}/segredo123/")


@pytest.mark.parametrize("arquivo", ["deploy/proxy/nginx-site.conf.modelo",
                                     "deploy/proxy/site.caddy.modelo"])
def test_proxies_mascaram_todos(arquivo):
    texto = (RAIZ / arquivo).read_text(encoding="utf-8")
    if "nginx" in arquivo:
        assert texto.count("(?:agenda/ics|fornecedor|p)/") == 2
    else:
        assert texto.count("(/agenda/ics/|/fornecedor/|/p/)") == 2


def test_preview_usa_o_log_mascarado():
    assert "gunicorn_conf.py" in (RAIZ / "scripts" / "preview-entrypoint.sh").read_text(
        encoding="utf-8")
