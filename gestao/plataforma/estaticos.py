"""Estáticos de produção: CSS e JS minificados no `collectstatic`.

Os fontes ficam comentados e legíveis (é como o time trabalha); o que vai para o navegador
em produção perde comentários e espaços — cerca de 1/3 do peso e quase metade do gzip.
JS passa pelo `rjsmin` (analisador que respeita strings, template strings e expressões
regulares); cada módulo continua um arquivo próprio — minificar não é empacotar (ADR 0002).
"""

from __future__ import annotations

import re

import rjsmin
from django.core.files.base import ContentFile
from whitenoise.storage import CompressedManifestStaticFilesStorage

# Só onde o espaço nunca tem significado. Fora de propósito: ":" (".a :hover" é
# descendente), "+" e "-" (calc exige os espaços), ")" e "(" (seletores e funções).
_ESPACO_EM_VOLTA = re.compile(r"\s*([{};,>])\s*")


def _pedacos(fonte: str):
    """Separa o CSS em (é_string, texto), descartando comentários. Lê caractere a caractere:
    um apóstrofo dentro de comentário não abre string, e "/*" dentro de string não é comentário."""
    i, n, inicio = 0, len(fonte), 0
    while i < n:
        c = fonte[i]
        if c == "/" and fonte.startswith("/*", i):
            yield False, fonte[inicio:i]
            fim = fonte.find("*/", i + 2)
            i = n if fim < 0 else fim + 2
            inicio = i
            continue
        if c in "\"'":
            yield False, fonte[inicio:i]
            j = i + 1
            while j < n and fonte[j] != c:
                j += 2 if fonte[j] == "\\" else 1
            yield True, fonte[i:j + 1]
            i = inicio = j + 1
            continue
        i += 1
    yield False, fonte[inicio:]


def minificar_js(fonte: str) -> str:
    return rjsmin.jsmin(fonte).strip()


def minificar_css(fonte: str) -> str:
    """Tira comentários e espaços redundantes sem tocar no conteúdo de strings."""
    saida = []
    for e_string, texto in _pedacos(fonte):
        if not e_string:
            texto = _ESPACO_EM_VOLTA.sub(r"\1", re.sub(r"\s+", " ", texto))
        saida.append(texto)
    return "".join(saida).replace(";}", "}").strip()


def minificar(nome: str, texto: str) -> str | None:
    """O texto minificado, ou None quando o arquivo não é minificável (ou já veio pronto)."""
    if nome.endswith(".min.js") or nome.endswith(".min.css"):
        return None
    if nome.endswith(".css"):
        return minificar_css(texto)
    if nome.endswith(".js"):
        return minificar_js(texto)
    return None


class ArmazenamentoEstatico(CompressedManifestStaticFilesStorage):
    """WhiteNoise (hash no nome + gzip/brotli) com CSS e JS minificados antes do hash."""

    def _save(self, name, content):
        if name.endswith((".css", ".js")):
            # O manifesto calcula o hash lendo o arquivo: ele chega aqui já lido até o fim.
            if hasattr(content, "seek"):
                content.seek(0)
            texto = content.read().decode("utf-8")
            pronto = minificar(name, texto)
            content = ContentFile((texto if pronto is None else pronto).encode("utf-8"))
        return super()._save(name, content)
