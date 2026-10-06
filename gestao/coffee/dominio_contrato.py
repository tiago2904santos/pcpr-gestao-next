"""Leitura do contrato ou do termo aditivo da SESP a partir do texto do PDF, em Python puro
(CB5d; comportamento da referência, `coffee_break/contratos_pdf.py` §2.2 — implementação
própria): o que o documento é (contrato ou aditivo), de quem é (CNPJ e razão social do
contratado), número, GMS, aditivo, lote, quantidade, valores e vigência.

A vigência do aditivo vem escrita ("prorrogada a vigência … a partir de dd/mm/aaaa até
dd/mm/aaaa"); a do contrato inicial só tem o prazo ("1 (um) ano"): sai estimada a partir
da inserção no protocolo, e o aditivo seguinte a corrige."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

CNPJ_SESP = "76416932000181"
_DATA = r"(\d{2})/(\d{2})/(\d{4})"
_NUM = r"(\d{1,5}/\d{4})"
_GMS = r"(\d{1,6}/\d{4})"


def _plano(texto: str) -> str:
    """Sem acento, traços e ordinais unificados e espaços colapsados."""
    t = "".join(c for c in unicodedata.normalize("NFKD", texto or "")
                if not unicodedata.combining(c))
    for de, para in (("–", "-"), ("—", "-"), ("º", "o"), ("°", "o"), ("ª", "a")):
        t = t.replace(de, para)
    return " ".join(t.split())


def _data(d: str, m: str, a: str) -> date | None:
    try:
        return date(int(a), int(m), int(d))
    except ValueError:
        return None


def _decimal(texto: str) -> Decimal | None:
    try:
        return Decimal(texto.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None


def _mais_anos(inicio: date, anos: int) -> date:
    try:
        return inicio.replace(year=inicio.year + anos)
    except ValueError:  # 29/02
        return inicio.replace(year=inicio.year + anos, day=28)


@dataclass
class Documento:
    tipo: str = ""  # "contrato" | "aditivo" | "" (não reconhecido)
    numero: str = ""
    numero_gms: str = ""
    termo_aditivo: str = ""
    cnpj: str = ""
    razao_social: str = ""
    numero_lote: int | None = None
    quantidade: int | None = None
    valor_unitario: Decimal | None = None
    valor_total: Decimal | None = None
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    vigencia_estimada: bool = False
    da_sesp: bool = False


def ler(texto: str) -> Documento:
    p = _plano(texto)
    doc = Documento(da_sesp=CNPJ_SESP in re.sub(r"\D", "", p))
    aditivo = re.search(r"TERMO ADITIVO No\s*" + _NUM, p, re.I)
    cabecalho = re.search(r"CONTRATO\s*-?\s*No\s*" + _NUM + r"\s*-\s*GMS\s*(?:No\s*)?" + _GMS,
                          p, re.I)
    citado = re.search(r"Contrato\s*n[o.]*\s*" + _NUM + r"\s*-\s*GMS\s*(?:No\s*)?" + _GMS, p, re.I)
    if aditivo:
        doc.tipo, doc.termo_aditivo = "aditivo", aditivo.group(1)
        if (m := citado or cabecalho):
            doc.numero, doc.numero_gms = m.group(1), m.group(2)
    elif cabecalho:
        doc.tipo = "contrato"
        doc.numero, doc.numero_gms = cabecalho.group(1), cabecalho.group(2)

    contratado = re.search(r"CONTRATAD[OA](?:\s*\(A\))?\s*:\s*(.+?)\s*,?\s*CNPJ\s*(?:n\s*o?)?"
                           r"\s*:?\s*(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})", p, re.I)
    if contratado:
        doc.razao_social = contratado.group(1).strip(" ,")
        doc.cnpj = re.sub(r"\D", "", contratado.group(2))
    if (lote := re.search(r"\bLOTE\s*-?\s*0*(\d{1,2})\b", p)):
        doc.numero_lote = int(lote.group(1))

    # A linha da tabela do objeto: "10.000 R$ 20,0000 R$ 200.000,00" — no aditivo de
    # repactuação o terceiro valor é o unitário novo; a última linha vale (apostilamento).
    linhas = re.findall(r"(\d{1,3}(?:\.\d{3})+|\d{2,7})\s+R\$\s*([\d.]+,\d{2,4})\s+R\$\s*"
                        r"([\d.]+,\d{2,4})", p)
    if linhas:
        qtd, unitario, terceiro = linhas[-1]
        doc.quantidade = int(qtd.replace(".", ""))
        if re.search(r"REPACTUAD", p, re.I):
            doc.valor_unitario = _decimal(terceiro)
        else:
            doc.valor_unitario, doc.valor_total = _decimal(unitario), _decimal(terceiro)
    if (total := re.search(r"valor total do contrato e de R\$\s*([\d.]+,\d{2})", p, re.I)):
        doc.valor_total = _decimal(total.group(1))
    if (novo := re.search(r"passando de R\$\s*[\d.]+,\d{2}.*?para R\$\s*([\d.]+,\d{2})", p,
                          re.I)):
        doc.valor_total = _decimal(novo.group(1))

    prorrogada = re.search(r"prorrogada a vigencia.{0,160}?a partir\s+de\s+" + _DATA
                           + r"\s+(?:ate|a)\s+" + _DATA, p, re.I)
    if prorrogada:
        g = prorrogada.groups()
        doc.vigencia_inicio, doc.vigencia_fim = _data(*g[:3]), _data(*g[3:])
    else:
        prazo = re.search(r"prazo de vigencia do contrato e de\s*(\d{1,2})\s*(?:\([^)]*\)\s*)?"
                          r"(anos?|mes(?:es)?)", p, re.I)
        inserido = re.search(r"Inserido ao Protocolo\s*[\d.\-]+\s*por\s*.+?em:?\s*" + _DATA, p,
                             re.I)
        if prazo and inserido and (inicio := _data(*inserido.groups())):
            n = int(prazo.group(1))
            fim = (_mais_anos(inicio, n) - timedelta(days=1)
                   if prazo.group(2).lower().startswith("ano")
                   else inicio + timedelta(days=30 * n - 1))
            doc.vigencia_inicio, doc.vigencia_fim, doc.vigencia_estimada = inicio, fim, True
    return doc
