"""Escrita dos documentos (Python puro): datas por extenso, listas com "e", plural de cargos,
capitalização legível e valores em reais. Compartilhado pela OS e pelo plano de trabalho."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro")

# Palavras que ficam em minúsculas no meio de um nome ("Juliana Villela de Barros").
CONECTORES = {"de", "da", "do", "das", "dos", "e", "em", "na", "no", "nas", "nos", "a", "o",
              "as", "os", "para", "com"}

# Siglas que se mantêm mesmo quando o texto vem todo em maiúsculas ("PCPR NA COMUNIDADE").
SIGLAS = {"PCPR", "PR", "ASCOM", "CIN", "BO", "NOC", "SESP", "PM", "PC", "PCI", "DPC", "SEAP",
          "DETO", "IML", "GOE", "TIGRE", "COPE"}

# Plurais em "-ães" de cargos (a regra simples daria "escrivões").
_PLURAIS_ESPECIAIS = {"escrivão": "escrivães", "capitão": "capitães", "tabelião": "tabeliães"}
_VOGAIS = "aeiouáéíóúàâêîôûãõ"


def data_por_extenso(d: date) -> str:
    """"5 de março de 2026" (local e data do documento)."""
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def lista_com_e(itens: list[str]) -> str:
    if not itens:
        return ""
    if len(itens) == 1:
        return itens[0]
    return f"{', '.join(itens[:-1])} e {itens[-1]}"


def eh_sigla(palavra: str) -> bool:
    letras = "".join(c for c in palavra if c.isalpha())
    return (bool(letras) and letras.lower() not in CONECTORES and letras.isascii()
            and letras.isupper() and len(letras) <= 5)


def plural_palavra(palavra: str) -> str:
    """Plural de uma palavra minúscula (regras regulares + os "-ães" dos cargos)."""
    if not palavra:
        return palavra
    if palavra in _PLURAIS_ESPECIAIS:
        return _PLURAIS_ESPECIAIS[palavra]
    if palavra.endswith("ão"):
        return palavra[:-2] + "ões"
    if palavra.endswith("il"):
        return palavra[:-2] + "is"
    ultima = palavra[-1]
    if ultima in _VOGAIS:
        return palavra + "s"
    if ultima == "l" and len(palavra) >= 2:
        return palavra[:-1] + ("is" if palavra[-2] in _VOGAIS else "eis")
    if ultima in "rzn":
        return palavra + "es"
    if ultima == "m":
        return palavra[:-1] + "ns"
    if ultima == "s":
        return palavra
    return palavra + "s"


def _maiuscula_inicial(palavra: str) -> str:
    return "-".join(p[:1].upper() + p[1:].lower() for p in palavra.split("-"))


def legivel(texto: str) -> str:
    """Capitalização legível: "PAPILOSCOPISTA JULIANA VILLELA DE BARROS" -> "Papiloscopista
    Juliana Villela de Barros"; conectores em minúsculas no meio; siglas mantidas (as
    conhecidas sempre; as outras só quando o texto não vem todo em maiúsculas)."""
    todo_maiusculo = texto.isupper()
    saida = []
    for i, palavra in enumerate(texto.split()):
        if palavra.upper() in SIGLAS or (not todo_maiusculo and eh_sigla(palavra)):
            saida.append(palavra.upper() if palavra.upper() in SIGLAS else palavra)
        elif i > 0 and palavra.lower() in CONECTORES:
            saida.append(palavra.lower())
        else:
            saida.append(_maiuscula_inicial(palavra))
    return " ".join(saida)


def cargo_no_plural(cargo: str) -> str:
    """"Policial Civil" -> "Policiais Civis"; "Agente de Polícia Judiciária" -> "Agentes de
    Polícia Judiciária": só o núcleo (as palavras antes da primeira preposição) vai ao plural
    — a referência pluralizava palavra por palavra ("Agentes de Polícias Judiciárias")."""
    palavras = legivel(cargo).split()
    saida = []
    nucleo = True
    for palavra in palavras:
        if palavra.lower() in CONECTORES:
            nucleo = False
        if nucleo and not eh_sigla(palavra):
            plural = plural_palavra(palavra.lower())
            saida.append(_maiuscula_inicial(plural))
        else:
            saida.append(palavra)
    return " ".join(saida)


def moeda(valor: Decimal) -> str:
    """"1.205,78" (sem o símbolo, como sai no texto: "R$1.205,78")."""
    numero = Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    inteiro, centavos = f"{abs(numero):.2f}".split(".")
    grupos: list[str] = []
    while inteiro:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    return f"{'-' if numero < 0 else ''}{'.'.join(grupos)},{centavos}"
