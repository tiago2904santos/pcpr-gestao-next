"""Mensagem de envio manual: sem rede, banco ou IA."""

from __future__ import annotations

import re
from collections.abc import Sequence
from urllib.parse import urlencode


def telefone_whatsapp(valor: str) -> str:
    numero = re.sub(r"\D", "", valor or "")
    if len(numero) in (10, 11):
        numero = "55" + numero
    return numero if len(numero) in (12, 13) and numero.startswith("55") else ""


def mensagem(nome: str, oficio: str, aviso: str, itens: Sequence[tuple[str, str, str]]) -> str:
    partes = [f"Olá, {nome}. Seguem as informações do Ofício {oficio}."]
    if aviso:
        partes.append(f"Saque das diárias: {aviso}")
    for titulo, explicacao, url in itens:
        partes.append(f"{titulo}: {explicacao}" + (f"\n{url}" if url else ""))
    partes.append("Se algum item estiver incorreto ou indisponível, fale com o setor responsável.")
    return "\n\n".join(partes)


def url_whatsapp(telefone: str, texto: str) -> str:
    numero = telefone_whatsapp(telefone)
    return f"https://wa.me/{numero}?{urlencode({'text': texto})}" if numero else ""
