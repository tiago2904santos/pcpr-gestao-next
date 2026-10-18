"""Validador JSON Schema (2020-12) mínimo, só biblioteca padrão, para o envelope de eventos.

Cobre exatamente as palavras-chave que `evento-integracao.schema.json` usa — `allOf`,
`if`/`then`/`else`, `$ref` local (`#/$defs/...`), `const`, `enum`, `required`, `properties`,
`additionalProperties` (falso ou esquema), `type`, `format` (`uuid`, `date-time`), `pattern`,
`minimum`/`maximum`, `minLength`/`maxLength`, `items`, `minItems`/`maxItems` — e **recusa** um
esquema com palavra-chave que não conhece (em vez de ignorá-la e "aprovar" o que o esquema
rejeitaria; foi o defeito apontado no PR #23, C2). Anotações (`description`, `title`, `x-*`,
`$schema`, `$id`, `$comment`, `examples`, `default`) são aceitas e ignoradas.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

SUPORTADAS = {
    "type",
    "const",
    "enum",
    "required",
    "properties",
    "additionalProperties",
    "allOf",
    "if",
    "then",
    "else",
    "$ref",
    "$defs",
    "format",
    "pattern",
    "minimum",
    "maximum",
    "minLength",
    "maxLength",
    "items",
    "minItems",
    "maxItems",
}
ANOTACOES = {"description", "title", "$schema", "$id", "$comment", "examples", "default"}
_TIPOS: dict[str, Any] = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_DATA_HORA = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$")


class EsquemaNaoSuportado(ValueError):
    """O esquema usa uma palavra-chave que este validador não implementa."""


def _numero(valor: Any) -> bool:
    return isinstance(valor, int | float) and not isinstance(valor, bool)


def _tipo_ok(valor: Any, tipo: str) -> bool:
    if tipo == "integer":  # JSON Schema: 1.0 é inteiro (vale o valor, não a grafia)
        return _numero(valor) and float(valor).is_integer()
    if tipo == "number":
        return _numero(valor)
    if tipo not in _TIPOS:
        raise EsquemaNaoSuportado(f"type {tipo!r}")
    return isinstance(valor, _TIPOS[tipo])


def _igual(a: Any, b: Any) -> bool:
    """Igualdade de instâncias JSON (const/enum): `true` ≠ `1` (no Python, True == 1) e
    `1` == `1.0`; listas e objetos comparados elemento a elemento com a mesma regra."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a is b
    if _numero(a) or _numero(b):
        return _numero(a) and _numero(b) and a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_igual(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_igual(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


def _resolver(ref: str, raiz: dict) -> dict:
    if not ref.startswith("#/"):
        raise EsquemaNaoSuportado(f"$ref não local: {ref}")
    alvo: Any = raiz
    for parte in ref[2:].split("/"):
        parte = parte.replace("~1", "/").replace("~0", "~")
        if not isinstance(alvo, dict) or parte not in alvo:
            raise EsquemaNaoSuportado(f"$ref inexistente: {ref}")
        alvo = alvo[parte]
    return alvo


def _formato_ok(valor: str, formato: str) -> bool:
    if formato == "uuid":
        return bool(_UUID.match(valor))
    if formato == "date-time":
        if not _DATA_HORA.match(valor):
            return False
        try:
            datetime.fromisoformat(valor.replace("Z", "+00:00").replace("z", "+00:00"))
        except ValueError:
            return False
        return True
    raise EsquemaNaoSuportado(f"format {formato!r}")


def validar(valor: Any, esquema: Any, caminho: str = "$", raiz: dict | None = None) -> list[str]:
    """Lista de erros (vazia = válido). `raiz` resolve os `$ref` locais."""
    if esquema is True:
        return []
    if esquema is False:
        return [f"{caminho}: proibido pelo esquema"]
    if not isinstance(esquema, dict):
        raise EsquemaNaoSuportado(f"esquema inválido em {caminho}: {esquema!r}")
    raiz = esquema if raiz is None else raiz
    desconhecidas = [
        k for k in esquema if k not in SUPORTADAS and k not in ANOTACOES and not k.startswith("x-")
    ]
    if desconhecidas:
        raise EsquemaNaoSuportado(f"{caminho}: palavras-chave não suportadas {desconhecidas}")
    erros: list[str] = []
    if "$ref" in esquema:
        erros += validar(valor, _resolver(esquema["$ref"], raiz), caminho, raiz)
    if "type" in esquema:
        tipos = esquema["type"] if isinstance(esquema["type"], list) else [esquema["type"]]
        if not any(_tipo_ok(valor, t) for t in tipos):
            return [*erros, f"{caminho}: tipo {type(valor).__name__} fora de {tipos}"]
    if "const" in esquema and not _igual(valor, esquema["const"]):
        erros.append(f"{caminho}: {valor!r} ≠ const {esquema['const']!r}")
    if "enum" in esquema and not any(_igual(valor, op) for op in esquema["enum"]):
        erros.append(f"{caminho}: {valor!r} fora do enum")
    if isinstance(valor, str):
        if "format" in esquema and not _formato_ok(valor, esquema["format"]):
            erros.append(f"{caminho}: {valor!r} não é {esquema['format']}")
        if "pattern" in esquema and not re.search(esquema["pattern"], valor):
            erros.append(f"{caminho}: {valor!r} não casa com {esquema['pattern']}")
        if "minLength" in esquema and len(valor) < esquema["minLength"]:
            erros.append(f"{caminho}: menor que {esquema['minLength']} caracteres")
        if "maxLength" in esquema and len(valor) > esquema["maxLength"]:
            erros.append(f"{caminho}: maior que {esquema['maxLength']} caracteres")
    if _numero(valor):
        if "minimum" in esquema and valor < esquema["minimum"]:
            erros.append(f"{caminho}: {valor} < {esquema['minimum']}")
        if "maximum" in esquema and valor > esquema["maximum"]:
            erros.append(f"{caminho}: {valor} > {esquema['maximum']}")
    if isinstance(valor, list):
        if "minItems" in esquema and len(valor) < esquema["minItems"]:
            erros.append(f"{caminho}: menos de {esquema['minItems']} itens")
        if "maxItems" in esquema and len(valor) > esquema["maxItems"]:
            erros.append(f"{caminho}: mais de {esquema['maxItems']} itens")
        if "items" in esquema:
            for i, item in enumerate(valor):
                erros += validar(item, esquema["items"], f"{caminho}[{i}]", raiz)
    if isinstance(valor, dict):
        props = esquema.get("properties", {})
        for req in esquema.get("required", []):
            if req not in valor:
                erros.append(f"{caminho}: falta {req}")
        for k, sub in props.items():
            if k in valor:
                erros += validar(valor[k], sub, f"{caminho}.{k}", raiz)
        extra = esquema.get("additionalProperties", True)
        for k in valor:
            if k in props:
                continue
            if extra is False:
                erros.append(f"{caminho}: campo extra {k}")
            elif isinstance(extra, dict):
                erros += validar(valor[k], extra, f"{caminho}.{k}", raiz)
    for i, sub in enumerate(esquema.get("allOf", [])):
        erros += validar(valor, sub, f"{caminho}(allOf[{i}])", raiz)
    if "if" in esquema:
        if not validar(valor, esquema["if"], caminho, raiz):
            if "then" in esquema:
                erros += validar(valor, esquema["then"], caminho, raiz)
        elif "else" in esquema:
            erros += validar(valor, esquema["else"], caminho, raiz)
    return erros
