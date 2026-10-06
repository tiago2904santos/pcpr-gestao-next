"""Peças comuns da leitura de um e-mail colado (Python puro, sem Django): o texto "dobrado"
(minúsculo e sem acento, com o mesmo comprimento — as posições valem para o original), os
cabeçalhos do primeiro bloco (De, Enviado em, Assunto…), a data/hora do envio, o corpo sem
cabeçalhos e sem a despedida, e-mails e telefones. Cada contexto monta a sua leitura em cima
disto (imprensa, publicações, coffee break)."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

CABECALHOS = ("de", "from", "para", "to", "cc", "cco", "bcc", "enviado em", "enviada em",
              "sent", "date", "data", "assunto", "subject")
DESPEDIDAS = ("att", "atenciosamente", "abs", "abraco", "abracos", "obrigad", "grat",
              "cordialmente", "sds", "saudacoes", "--")
MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
         "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11,
         "dezembro": 12}
R_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
R_TELEFONE = re.compile(r"(?:\+?55\s?)?\(?\b\d{2}\)?\s?9?\d{4}[-.\s]?\d{4}\b")
_R_CABECALHO = re.compile(r"^\s*(" + "|".join(re.escape(c) for c in CABECALHOS)
                          + r")\s*:\s*(.*)$")
_R_DATA_HORA = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})(?:\D{1,8}(\d{1,2})[:h](\d{2}))?")
_R_DATA_EXT = re.compile(r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})"
                         r"(?:\D{1,8}(\d{1,2})[:h](\d{2}))?")
_R_PREFIXO_ASSUNTO = re.compile(r"^(?:\s*(?:re|res|fw|fwd|enc)\s*:\s*)+", re.IGNORECASE)


def dobrar(texto: str) -> str:
    """Minúsculo e sem acento, caractere a caractere (o comprimento não muda)."""
    return "".join(unicodedata.normalize("NFD", c)[0].lower() for c in texto)


def eh_cabecalho(linha: str) -> bool:
    return bool(_R_CABECALHO.match(dobrar(linha)))


def cabecalhos(texto: str) -> dict[str, str]:
    """Os cabeçalhos do primeiro bloco de e-mail colado (a primeira ocorrência de cada)."""
    saida: dict[str, str] = {}
    for linha in texto.splitlines()[:30]:
        m = _R_CABECALHO.match(dobrar(linha))
        if m and m.group(1) not in saida:
            saida[m.group(1)] = linha[m.start(2):].strip()
    return saida


def quando(valor: str) -> datetime | None:
    """Data (e hora) de "Enviado em: 5 de outubro de 2026 10:42" ou "05/10/2026 10:42"."""
    d = dobrar(valor or "")
    m = _R_DATA_HORA.search(d)
    if m:
        dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = _R_DATA_EXT.search(d)
        if not m or m.group(2) not in MESES:
            return None
        dia, mes, ano = int(m.group(1)), MESES[m.group(2)], int(m.group(3))
    ano = ano + 2000 if ano < 100 else ano
    try:
        return datetime(ano, mes, dia, int(m.group(4) or 0), int(m.group(5) or 0))
    except ValueError:
        return None


def enviado_em(cab: dict[str, str]) -> datetime | None:
    return quando(cab.get("enviado em") or cab.get("enviada em") or cab.get("sent")
                  or cab.get("date") or cab.get("data") or "")


def assunto(cab: dict[str, str]) -> str:
    return _R_PREFIXO_ASSUNTO.sub("", cab.get("assunto") or cab.get("subject") or "").strip()


def corpo(texto: str) -> str:
    """O texto sem as linhas de cabeçalho e sem a despedida/assinatura."""
    linhas = [linha for linha in texto.splitlines() if not eh_cabecalho(linha)]
    for i, linha in enumerate(linhas):
        if i > 0 and any(dobrar(linha).strip().startswith(x) for x in DESPEDIDAS):
            return "\n".join(linhas[:i]).strip()
    return "\n".join(linhas).strip()


def assinatura(texto: str) -> list[str]:
    """As linhas depois da despedida (quem assina, cargo, unidade, contato)."""
    linhas = [linha for linha in texto.splitlines() if not eh_cabecalho(linha)]
    for i, linha in enumerate(linhas):
        if i > 0 and any(dobrar(linha).strip().startswith(x) for x in DESPEDIDAS):
            return [x.strip() for x in linhas[i + 1:] if x.strip()][:6]
    return []


def nome_do_remetente(de: str) -> str:
    nome = R_EMAIL.sub("", de or "").replace("<", "").replace(">", "").replace('"', "")
    return " ".join(nome.strip(" ,;").split())[:150]
