"""Cada tela carrega os pacotes de CSS que usa (e só eles entram no orçamento daquela rota).

`components.css` é o compartilhado; `formulario`, `documento`, `listas`, `painel`, `assistente`
e `itinerario` entram por `{% block estilos %}`. Este teste renderiza as telas com a base DEMO
e confere: toda classe usada no HTML que só existe num pacote exige o `<link>` desse pacote —
inclusive as peças que o JavaScript monta a partir de `<pc-data>` e `<pc-hora>` (calendário e
relógio), que não aparecem no HTML servido. Combobox e lista própria (`<pc-select>`) ficam no
compartilhado porque as listas também os usam ("Ordenar por").
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.urls import reverse

from gestao.identidade.backends import LOGIN_DEMO
from gestao.viagens import demonstracao
from gestao.viagens.models import Oficio, Roteiro

CSS = Path(__file__).resolve().parents[1] / "static" / "css"
PACOTES = ["formulario", "documento", "listas", "painel", "assistente", "itinerario"]
COMPARTILHADOS = ["tokens", "base", "layout", "components"]
# Elementos cujo CSS é montado pelo JS (não está no HTML servido) → pacote exigido.
POR_ELEMENTO = {"pc-data": "formulario", "pc-hora": "formulario", "pc-itinerario": "itinerario"}

pytestmark = pytest.mark.django_db


def _classes_de(arquivo: str) -> set[str]:
    css = re.sub(r"/\*.*?\*/", "", (CSS / f"{arquivo}.css").read_text(encoding="utf-8"), flags=re.S)
    seletores = re.sub(r"\{[^{}]*\}", "{}", css)
    return set(re.findall(r"\.([a-zA-Z][\w-]*)", seletores))


def _mapa() -> dict[str, str]:
    """classe → único pacote que a define (classes compartilhadas não restringem nada)."""
    por_arquivo = {a: _classes_de(a) for a in PACOTES + COMPARTILHADOS}
    compartilhadas = set().union(*(por_arquivo[a] for a in COMPARTILHADOS))
    mapa: dict[str, str] = {}
    for a in PACOTES:
        for c in por_arquivo[a] - compartilhadas:
            if any(c in por_arquivo[o] for o in PACOTES if o != a):
                continue  # definida em mais de um pacote: não decide
            mapa[c] = a
    return mapa


@pytest.fixture(scope="module")
def mapa():
    return _mapa()


@pytest.fixture
def paginas(settings):
    demonstracao.semear(escala=0.1)
    emitido = Oficio.objects.filter(situacao="emitido").first()
    rascunho = Oficio.objects.filter(situacao="rascunho").first()
    roteiro = Roteiro.objects.first()
    assert emitido and rascunho and roteiro, "a base DEMO precisa de emitido, rascunho e roteiro"
    return [
        "/",
        reverse("viagens:painel"),
        reverse("viagens:oficios"),
        reverse("viagens:oficios") + "?q=zzz",
        reverse("viagens:editar", args=[rascunho.pk]),
        reverse("viagens:revisar_emissao", args=[rascunho.pk]),
        reverse("viagens:roteiros"),
        reverse("viagens:novo_roteiro"),
        reverse("viagens:editar_roteiro", args=[roteiro.pk]),
        reverse("cadastros:servidores"),
        reverse("cadastros:viaturas"),
        reverse("cadastros:diarias"),
        reverse("painel:notificacoes"),
        reverse("identidade:alterar_senha"),
        "/busca/?q=ofi",
        "/nao-existe/",
        reverse("ui_lab:indice"),
    ]


def test_cada_tela_carrega_os_pacotes_que_usa(client, paginas, mapa, django_user_model):
    client.force_login(django_user_model.objects.get(login=LOGIN_DEMO))
    faltas = []
    for url in paginas:
        html = client.get(url).content.decode()
        carregados = set(re.findall(r"css/([\w-]+)\.css", html))
        usadas: set[str] = set()
        for m in re.finditer(r'class="([^"]*)"', html):
            usadas.update(m.group(1).split())
        exigidos = {mapa[c] for c in usadas if c in mapa}
        exigidos |= {p for el, p in POR_ELEMENTO.items() if f"<{el}" in html}
        for p in sorted(exigidos - carregados):
            exemplos = sorted(c for c in usadas if mapa.get(c) == p)[:4]
            faltas.append(f"{url}: falta css/{p}.css (usa {exemplos or 'elemento com JS'})")
    assert faltas == [], "\n".join(faltas)

