"""Normalização e validação de documentos e identificadores (sem Django)."""

from __future__ import annotations

import re
import unicodedata

PLACA = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")  # antiga (AAA9999) e Mercosul (AAA9A99)

# Marca de "a pessoa não tem RG" (diferente de vazio, que é "não informado").
RG_NAO_POSSUI = "NÃO POSSUI RG"
_RG_NAO_POSSUI_VARIANTES = {"NAO POSSUI RG", "NÃO POSSUI RG", "NAO POSSUI", "NÃO POSSUI"}


def somente_digitos(valor: str | None) -> str:
    return re.sub(r"[^0-9]", "", valor or "")  # \D aceitaria dígitos de outros alfabetos


def cpf_valido(valor: str | None) -> bool:
    cpf = somente_digitos(valor)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[tamanho]):
            return False
    return True


def formatar_cpf(valor: str | None) -> str:
    cpf = somente_digitos(valor)
    if len(cpf) != 11:
        return valor or ""
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def normalizar_placa(valor: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (valor or "").upper())


def placa_valida(valor: str | None) -> bool:
    return bool(PLACA.match(normalizar_placa(valor)))


def formatar_placa(valor: str | None) -> str:
    placa = normalizar_placa(valor)
    if re.match(r"^[A-Z]{3}[0-9]{4}$", placa):
        return f"{placa[:3]}-{placa[3:]}"
    return placa


def sem_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def espacos(texto: str | None) -> str:
    """Tira as pontas e junta espaços repetidos."""
    return " ".join((texto or "").split())


def normalizar_rg(valor: str | None) -> str:
    """RG não tem formato único no país: guarda só letras e números, em maiúsculas.
    "não possui RG" (com ou sem acento) vira a marca RG_NAO_POSSUI."""
    texto = espacos(valor).upper()
    if not texto:
        return ""
    if texto in _RG_NAO_POSSUI_VARIANTES:
        return RG_NAO_POSSUI
    return re.sub(r"[^A-Z0-9]", "", sem_acentos(texto))


def formatar_rg(valor: str | None) -> str:
    texto = (valor or "").strip()
    digitos = somente_digitos(texto)
    if texto == RG_NAO_POSSUI or not texto.isalnum():
        return texto
    if len(digitos) == len(texto) == 8:
        return f"{texto[0]}.{texto[1:4]}.{texto[4:7]}-{texto[7]}"
    if len(digitos) == len(texto) == 9:
        return f"{texto[:2]}.{texto[2:5]}.{texto[5:8]}-{texto[8]}"
    return texto


def formatar_telefone(valor: str | None) -> str:
    digitos = somente_digitos(valor)
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    return valor or ""


# Partículas que ficam em minúscula no meio de um nome próprio (nunca na primeira palavra).
_PARTICULAS = {"de", "da", "do", "das", "dos", "e", "di", "du", "del", "della",
               "van", "von", "der", "la", "le", "y"}


def titulo(texto: str | None) -> str:
    """Nome próprio com a inicial de cada palavra em maiúscula.

    Padrão dos cadastros: quem digita "ana maria da silva" grava "Ana Maria da Silva" —
    assim a lista, a equipe do ofício e o documento saem sempre com a mesma cara, sem
    depender de quem digitou estar com o Caps Lock certo.

    Uma sigla no meio de um nome em caixa mista fica como está ("Núcleo NUCRIA"): quem a
    escreveu assim quis a sigla. Já o texto inteiro em caixa alta é Caps Lock, não sigla —
    "JOÃO DOS SANTOS" vira "João dos Santos". Hífen e apóstrofo também separam palavras
    ("Costa-Silva", "D'Ávila").
    """
    limpo = espacos(texto)
    palavras = limpo.split(" ")
    # Tudo em caixa alta: Caps Lock. Só então as "siglas" perdem a proteção.
    siglas_valem = not limpo.isupper()
    saida = []
    for i, palavra in enumerate(palavras):
        if siglas_valem and len(palavra) > 1 and palavra.isupper():
            saida.append(palavra)
            continue
        minuscula = palavra.lower()
        if i > 0 and minuscula in _PARTICULAS:
            saida.append(minuscula)
            continue
        saida.append(re.sub(r"(^|[-'’])(\w)",
                            lambda m: m.group(1) + m.group(2).upper(), minuscula))
    return " ".join(saida)
