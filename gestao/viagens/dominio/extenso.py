"""Valor monetário por extenso em português do Brasil.

Ex.: Decimal("2411.56") → "dois mil quatrocentos e onze reais e cinquenta e seis centavos".
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_UNIDADES = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove",
             "dez", "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete",
             "dezoito", "dezenove"]
_DEZENAS = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta",
            "oitenta", "noventa"]
_CENTENAS = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos",
             "setecentos", "oitocentos", "novecentos"]
_ESCALAS = [("", ""), ("mil", "mil"), ("milhão", "milhões"), ("bilhão", "bilhões")]


def _ate_999(n: int) -> str:
    if n == 0:
        return ""
    if n == 100:
        return "cem"
    c, resto = divmod(n, 100)
    partes = []
    if c:
        partes.append(_CENTENAS[c])
    if resto:
        if resto < 20:
            partes.append(_UNIDADES[resto])
        else:
            d, u = divmod(resto, 10)
            partes.append(_DEZENAS[d] + (f" e {_UNIDADES[u]}" if u else ""))
    return " e ".join(partes)


def inteiro_por_extenso(n: int) -> str:
    if n == 0:
        return "zero"
    grupos: list[int] = []
    while n:
        n, g = divmod(n, 1000)
        grupos.append(g)
    partes: list[tuple[int, str]] = []
    for i in range(len(grupos) - 1, -1, -1):
        g = grupos[i]
        if not g:
            continue
        if i == 1 and g == 1:
            texto = "mil"
        else:
            singular, plural = _ESCALAS[i]
            nome = singular if g == 1 else plural
            texto = _ate_999(g) + (f" {nome}" if nome else "")
        partes.append((g, texto))
    if len(partes) == 1:
        return partes[0][1]
    # "e" antes do último grupo quando ele é < 100 ou centena exata (ex.: "mil e cem").
    ultimo_valor, ultimo_texto = partes[-1]
    inicio = " ".join(t for _, t in partes[:-1])
    if ultimo_valor < 100 or ultimo_valor % 100 == 0:
        return f"{inicio} e {ultimo_texto}"
    return f"{inicio} {ultimo_texto}"


def reais_por_extenso(valor: Decimal) -> str:
    valor = Decimal(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if valor < 0:
        return "menos " + reais_por_extenso(-valor)
    reais = int(valor)
    centavos = int((valor - reais) * 100)
    partes = []
    if reais:
        texto = inteiro_por_extenso(reais)
        # "um milhão de reais", "dois milhões de reais"
        sufixo = "real" if reais == 1 else "reais"
        if reais % 1_000_000 == 0:
            sufixo = "de " + sufixo
        partes.append(f"{texto} {sufixo}")
    if centavos:
        partes.append(f"{inteiro_por_extenso(centavos)} centavo{'s' if centavos > 1 else ''}")
    if not partes:
        return "zero real"
    return " e ".join(partes)
