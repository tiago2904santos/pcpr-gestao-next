"""Identidades e reconciliação de cadastros; domínio puro, sem transporte ou ORM."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping

from .validacoes import (
    cpf_valido,
    espacos,
    normalizar_placa,
    normalizar_rg,
    somente_digitos,
)


def codigo_da_atividade(nome: str, existentes: set[str]) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Z0-9]+", "_", sem_acento.upper()).strip("_")[:34] or "ATIVIDADE"
    codigo, numero = base, 2
    while codigo in existentes:
        codigo, numero = f"{base}_{numero}", numero + 1
    return codigo


class ConflitoDeCadastro(ValueError):
    """Um campo mudou localmente e também na fonte desde o último estado conhecido."""

    def __init__(self, campos: list[str]):
        self.campos = sorted(campos)
        super().__init__("Há alterações locais em: " + ", ".join(self.campos)
                         + ". Revise o conflito antes de atualizar pela fonte.")


def reconciliar(base: Mapping, local: Mapping, recebido: Mapping) -> dict:
    """Atualiza só campos alterados na origem, sem sobrescrever mudanças locais."""
    conflitos = [campo for campo, valor in recebido.items()
                 if valor != base[campo] and local[campo] != base[campo]
                 and local[campo] != valor]
    if conflitos:
        raise ConflitoDeCadastro(conflitos)
    return {campo: valor for campo, valor in recebido.items()
            if valor != base[campo] and valor != local[campo]}


def normalizar_da_origem(entidade: str, valores: dict) -> dict:
    """A origem passa pelas mesmas regras puras de identificação dos formulários."""
    for campo, valor in valores.items():
        if ((campo == "ativo" and not isinstance(valor, bool))
                or (campo != "ativo" and not isinstance(valor, str))):
            raise ValueError(f"Tipo inválido para {campo} na fonte. Confira o contrato de dados.")
    limpos = valores.copy()
    if "nome" in limpos:
        limpos["nome"] = espacos(limpos["nome"])
    if entidade == "servidor":
        for campo in ("cpf", "telefone"):
            if campo in limpos:
                limpos[campo] = somente_digitos(limpos[campo])
        if limpos.get("cpf") and not cpf_valido(limpos["cpf"]):
            raise ValueError("CPF inválido na fonte. Confira os dígitos antes de atualizar.")
        if limpos.get("telefone") and len(limpos["telefone"]) not in (10, 11):
            raise ValueError("Telefone inválido na fonte. Informe o número com DDD.")
        if "rg" in limpos:
            limpos["rg"] = normalizar_rg(limpos["rg"])
    if entidade == "viatura" and "placa" in limpos:
        limpos["placa"] = normalizar_placa(limpos["placa"])
    return limpos
