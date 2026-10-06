"""Regras do Coffee Break em Python puro (sem Django): CNPJ, nome curto do fornecedor,
referência documental do contrato, vigência efetiva e o selo de vigência (paridade com
`coffee_break/models.py`, `presenters.py` e `services.py` da referência; mensagens como lá).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

MSG_CNPJ = "O CNPJ deve ter 14 dígitos."
MSG_EM_USO = "Não é possível excluir: {singular} em uso (contratos, lotes ou solicitações)."
MSG_VERSAO = "Este cadastro foi alterado por outra pessoa. Recarregue a página antes de salvar."
MSG_VIGENCIA = "O fim da vigência não pode ser anterior ao início."
MSG_MUNICIPIOS = "Município não encontrado no Paraná: {lista}."
SUFIXOS_EMPRESA = ("LTDA", "EIRELI", "ME", "EPP", "S.A.", "S/A", "SA")


def so_digitos(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def normalizar_cnpj(texto: str | None) -> str:
    """Aceita com ou sem pontuação; devolve os 14 dígitos ("" quando vazio)."""
    digitos = so_digitos(texto)
    if not digitos:
        return ""
    if len(digitos) != 14:
        raise ValueError(MSG_CNPJ)
    return digitos


def formatar_cnpj(digitos: str) -> str:
    d = so_digitos(digitos)
    if len(d) != 14:
        return digitos or ""
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def nome_curto(razao_social: str) -> str:
    """Razão social em maiúsculas sem o tipo da empresa (LTDA, EIRELI, ME, EPP, S.A.)."""
    palavras = [p for p in (razao_social or "").upper().replace(",", " ").split()
                if p.strip("-") not in SUFIXOS_EMPRESA]
    while palavras and palavras[-1] in ("-", "–"):
        palavras.pop()
    return " ".join(palavras)


def referencia_documental(numero: str, gms: str = "", aditivo: str = "") -> str:
    """"<número> – GMS <gms> - TERMO ADITIVO Nº <aditivo>", só com as partes que existem."""
    texto = numero or ""
    if gms:
        texto += f" – GMS {gms}"
    if aditivo:
        texto += f" - TERMO ADITIVO Nº {aditivo}"
    return texto


def fim_efetivo(fim_contrato: date | None, fins_aditivos: list[date]) -> date | None:
    """O maior fim entre o do contrato e os dos termos aditivos."""
    datas = [d for d in (fim_contrato, *fins_aditivos) if d]
    return max(datas) if datas else None


@dataclass(frozen=True)
class SeloVigencia:
    texto: str
    tom: str  # sucesso | perigo | neutro
    nota: str  # "Vigente até dd/mm/aaaa (estimada)"


def selo_vigencia(fim: date | None, hoje: date, estimada: bool = False) -> SeloVigencia:
    if fim is None:
        return SeloVigencia("Sem vigência", "neutro", "Vigência não informada")
    sufixo = " (estimada)" if estimada else ""
    if fim < hoje:
        return SeloVigencia("Vencido", "perigo", f"Vencido em {fim:%d/%m/%Y}{sufixo}")
    return SeloVigencia("Vigente", "sucesso", f"Vigente até {fim:%d/%m/%Y}{sufixo}")


def chave_de_nome(texto: str) -> str:
    """Para casar nomes de municípios: sem acento, sem caixa, espaços simples."""
    sem = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem.lower().replace("’", "'").split())


def separar_municipios(texto: str) -> list[str]:
    """Nomes separados por vírgula, ponto e vírgula, " e " ou linha; sem repetir; o "/PR"
    no fim é aceito."""
    partes = re.split(r"[,;\n]|\s+e\s+", texto or "")
    vistos: dict[str, str] = {}
    for p in partes:
        nome = re.sub(r"\s*/\s*PR\s*$", "", p.strip(), flags=re.IGNORECASE).strip(" .")
        if nome and chave_de_nome(nome) not in vistos:
            vistos[chave_de_nome(nome)] = nome
    return list(vistos.values())
