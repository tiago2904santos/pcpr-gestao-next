"""O que um termo de busca pode querer dizer — Python puro, sem Django.

A busca ampla é útil para quem não sabe onde procurar, mas "26" casa com o número do
ofício, com o protocolo, com a placa e até com o RG de um servidor: dá cinquenta linhas e
nenhuma resposta. Aqui o termo é lido e devolvido em leituras possíveis ("Ofício 26",
"Protocolo com 26"…); quem conta quantos ofícios caem em cada uma é a camada de consulta,
e quem escolhe é a pessoa, num clique.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

NUMERO = re.compile(r"^(\d{1,5})\s*/?\s*(\d{4})?$")
PLACA = re.compile(r"^[A-Za-z]{3}[-\s]?\d[A-Za-z\d]\d{2}$")
PLACA_PARCIAL = re.compile(r"^[A-Za-z]{2,3}[-\s]?\d{1,4}[A-Za-z\d]*$")

# Escopos na ordem em que aparecem para quem busca: do mais específico ao mais aberto.
NUMERO_ESCOPO = "numero"
PROTOCOLO = "protocolo"
PLACA_ESCOPO = "placa"
DESTINO = "destino"
SERVIDOR = "servidor"
ESCOPOS = (NUMERO_ESCOPO, PROTOCOLO, PLACA_ESCOPO, DESTINO, SERVIDOR)


@dataclass(frozen=True)
class Leitura:
    """Uma maneira de entender o termo digitado."""

    escopo: str
    rotulo: str
    termo: str


def so_digitos(texto: str) -> str:
    return "".join(c for c in texto if c.isdigit())


def sem_acento(texto: str) -> str:
    sem = unicodedata.normalize("NFD", texto)
    return "".join(c for c in sem if unicodedata.category(c) != "Mn").lower()


def _protocolo_formatado(digitos: str) -> str:
    """00.366.136-8 quando vierem os nove dígitos; senão, o que a pessoa escreveu."""
    if len(digitos) != 9:
        return digitos
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}-{digitos[8]}"


def parece_placa(termo: str) -> bool:
    """"ABC1D23", "abc-1d23", "ABC 1234" — ou um pedaço com letras e algarismos ("ABC1")."""
    termo = (termo or "").strip()
    letras = sum(1 for c in termo if c.isalpha())
    return bool(PLACA.match(termo) or (letras and PLACA_PARCIAL.match(termo)))


def placa_normalizada(termo: str) -> str:
    """Como a frota guarda a placa: sem hífen nem espaço, em maiúsculas."""
    return termo.replace("-", "").replace(" ", "").upper()


def ler(termo: str, ano_corrente: int) -> list[Leitura]:
    """Leituras possíveis do termo, da mais específica para a mais ampla."""
    termo = (termo or "").strip()
    if not termo:
        return []
    leituras: list[Leitura] = []
    digitos = so_digitos(termo)
    letras = sum(1 for c in termo if c.isalpha())

    numero = NUMERO.match(termo)
    if numero:
        ano = numero.group(2) or str(ano_corrente)
        leituras.append(Leitura(NUMERO_ESCOPO, f"Ofício {int(numero.group(1))}/{ano}",
                                f"{int(numero.group(1))}/{ano}"))
    # Só oferece protocolo quando o termo é mesmo um número: em "ABC1D23" os dígitos
    # soltos não são protocolo nenhum, são parte da placa.
    if not letras and len(digitos) >= 2:
        leituras.append(Leitura(PROTOCOLO, f"Protocolo com {_protocolo_formatado(digitos)}",
                                digitos))
    if parece_placa(termo):
        leituras.append(Leitura(PLACA_ESCOPO, f"Placa {termo.upper()}", termo))
    if letras >= 2:
        leituras.append(Leitura(DESTINO, f"Destino “{termo}”", termo))
        leituras.append(Leitura(SERVIDOR, f"Servidor “{termo}”", termo))
    return leituras
