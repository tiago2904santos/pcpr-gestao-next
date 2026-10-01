"""Normalização e validação de documentos e identificadores (sem Django)."""

from __future__ import annotations

import re
import unicodedata

PLACA = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")  # antiga (AAA9999) e Mercosul (AAA9A99)


def somente_digitos(valor: str | None) -> str:
    return re.sub(r"\D", "", valor or "")


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
