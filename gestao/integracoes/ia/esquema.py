"""Validação de saída por JSON Schema (subconjunto) em Python puro — sem dependência nova.

Cobre o que os esquemas dos usos usam: `type` (object, array, string, integer, number,
boolean, null, ou lista deles), `properties`, `required`, `additionalProperties: false`,
`enum`, `const`, `items`, `minItems`/`maxItems`, `minLength`/`maxLength`, `pattern`,
`minimum`/`maximum`. Campo fora do esquema é erro (a saída só pode conter o permitido).

`para_api` tira do esquema as restrições que a API de saída estruturada não aceita (tamanhos,
limites numéricos); elas continuam valendo aqui, na validação local.
"""

from __future__ import annotations

import re
from typing import Any

_TIPOS = {
    "object": dict, "array": list, "string": str, "boolean": bool, "null": type(None),
}
NAO_SUPORTADOS_NA_API = ("minLength", "maxLength", "minItems", "maxItems", "minimum",
                         "maximum", "pattern")


def _tipo_ok(valor: Any, tipo: str) -> bool:
    if tipo == "integer":
        return isinstance(valor, int) and not isinstance(valor, bool)
    if tipo == "number":
        return isinstance(valor, int | float) and not isinstance(valor, bool)
    esperado = _TIPOS.get(tipo)
    return esperado is not None and isinstance(valor, esperado)


def validar(valor: Any, esquema: dict[str, Any], caminho: str = "$") -> list[str]:
    erros: list[str] = []
    tipo = esquema.get("type")
    if tipo is not None:
        tipos = tipo if isinstance(tipo, list) else [tipo]
        if not any(_tipo_ok(valor, t) for t in tipos):
            return [f"{caminho}: tipo inválido (esperado {'/'.join(tipos)})"]
    if "const" in esquema and valor != esquema["const"]:
        erros.append(f"{caminho}: valor diferente do fixo")
    if "enum" in esquema and valor not in esquema["enum"]:
        erros.append(f"{caminho}: valor fora da lista permitida")
    if isinstance(valor, str):
        if "maxLength" in esquema and len(valor) > esquema["maxLength"]:
            erros.append(f"{caminho}: texto acima de {esquema['maxLength']} caracteres")
        if "minLength" in esquema and len(valor) < esquema["minLength"]:
            erros.append(f"{caminho}: texto curto demais")
        if "pattern" in esquema and not re.fullmatch(esquema["pattern"], valor):
            erros.append(f"{caminho}: formato inválido")
    if isinstance(valor, int | float) and not isinstance(valor, bool):
        if "minimum" in esquema and valor < esquema["minimum"]:
            erros.append(f"{caminho}: abaixo do mínimo")
        if "maximum" in esquema and valor > esquema["maximum"]:
            erros.append(f"{caminho}: acima do máximo")
    if isinstance(valor, list):
        if "maxItems" in esquema and len(valor) > esquema["maxItems"]:
            erros.append(f"{caminho}: mais de {esquema['maxItems']} itens")
        if "minItems" in esquema and len(valor) < esquema["minItems"]:
            erros.append(f"{caminho}: itens de menos")
        if isinstance(esquema.get("items"), dict):
            for i, item in enumerate(valor):
                erros.extend(validar(item, esquema["items"], f"{caminho}[{i}]"))
    if isinstance(valor, dict):
        props = esquema.get("properties", {})
        for nome in esquema.get("required", []):
            if nome not in valor:
                erros.append(f"{caminho}.{nome}: obrigatório")
        if esquema.get("additionalProperties") is False:
            for nome in valor:
                if nome not in props:
                    erros.append(f"{caminho}.{nome}: campo não permitido")
        for nome, sub in props.items():
            if nome in valor:
                erros.extend(validar(valor[nome], sub, f"{caminho}.{nome}"))
    return erros


def para_api(esquema: Any) -> Any:
    if isinstance(esquema, dict):
        return {k: para_api(v) for k, v in esquema.items() if k not in NAO_SUPORTADOS_NA_API}
    if isinstance(esquema, list):
        return [para_api(v) for v in esquema]
    return esquema
