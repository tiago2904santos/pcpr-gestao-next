"""Leitura do texto dos PDFs da nota fiscal e da ordem bancária, em Python puro (CB5b;
paridade com `coffee_break/nota_fiscal.py` e `ordem_bancaria.py`): o que se acha vira
sugestão e aviso — nunca bloqueia (os formatos variam: DANFE, NFC-e, NFS-e de cada
prefeitura, SIAF). Mensagens da referência."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

_CHAVE = re.compile(r"(?<!\d)((?:\d[\s.]?){43}\d)(?!\d)")
_DANFE = re.compile(r"N[º°o]\.?\s*:?\s*(\d{3}\.\d{3}\.\d{3}|\d{9})(?!\d)")
_ROTULOS_NUMERO = (
    re.compile(r"N[úu]mero\s+da\s+(?:NFS-?e|Nota(?:\s+Fiscal)?)\s*[:\-]?\s*(\d{1,15})", re.I),
    re.compile(r"NFS-?e\s*(?:N[º°o.]*|n[úu]mero)\s*[:\-]?\s*(\d{1,15})", re.I),
    re.compile(r"Nota\s+Fiscal[^\n\d]{0,40}?N[º°o.]+\s*[:\-]?\s*(\d{1,15})", re.I),
)
_DINHEIRO = r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})"
_VALOR_NOTA = (
    re.compile(r"VALOR\s+TOTAL\s+DA\s+NOTA[^\d]{0,40}?" + _DINHEIRO, re.I),
    re.compile(r"VALOR\s+(?:TOTAL|L[ÍI]QUIDO)\s+D[AO]\s+(?:NFS-?e|NOTA(?:\s+FISCAL)?|"
               r"SERVI[ÇC]OS?)[^\d]{0,40}?" + _DINHEIRO, re.I),
)
_EMISSAO = re.compile(r"(?:DATA\s+D[AE]\s+EMISS[ÃA]O|DATA\s+E\s+HORA\s+D[AE]\s+EMISS[ÃA]O|"
                      r"EMITIDA\s+EM)[^\d]{0,40}?(\d{2}/\d{2}/\d{4})", re.I)
_PRESTADOR = re.compile(r"PRESTADOR[\s\S]{0,300}?CNPJ[^\d]{0,20}"
                        r"(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})", re.I)
_OB_NUMERO = (
    re.compile(r"(?<![\dA-Z])(\d{4}\s*OB\s*\d{3,})(?!\d)", re.I),
    re.compile(r"(?:ORDEM\s+BANC[ÁA]RIA|N[ÚU]MERO\s+DA\s+OB|\bOB\b)\s*(?:N[º°o.]*|n[úu]mero)?"
               r"\s*[:\-]?\s*(\d[\d./-]{2,})", re.I),
)
_OB_DATA = re.compile(r"(?:DATA\s+(?:DE\s+|DA\s+)?(?:EMISS[ÃA]O|PAGAMENTO|OB|ORDEM\s+BANC[ÁA]RIA)"
                      r"|EMITIDA\s+EM)[^\d]{0,40}?(\d{2}/\d{2}/\d{4})", re.I)
_DATA = re.compile(r"(?<!\d)(\d{2}/\d{2}/\d{4})(?!\d)")
_OB_VALOR = re.compile(r"VALOR(?:\s+(?:L[ÍI]QUIDO|TOTAL|DA\s+OB|DA\s+ORDEM\s+BANC[ÁA]RIA|PAGO|"
                       r"BRUTO))?[^\d]{0,40}?" + _DINHEIRO, re.I)


def _sem_zeros(numero: str) -> str:
    digitos = re.sub(r"\D", "", numero)
    return str(int(digitos)) if digitos else ""


def _data(texto: str) -> date | None:
    try:
        dia, mes, ano = (int(p) for p in texto.split("/"))
        return date(ano, mes, dia)
    except ValueError:
        return None


def _dinheiro(texto: str) -> Decimal:
    return Decimal(texto.replace(".", "").replace(",", "."))


def _chave(texto: str) -> str:
    """A chave de acesso da NF-e/NFC-e (44 dígitos, modelo 55 ou 65 nas posições 21-22)."""
    for achado in _CHAVE.finditer(texto or ""):
        chave = re.sub(r"\D", "", achado.group(1))
        if len(chave) == 44 and chave[20:22] in ("55", "65"):
            return chave
    return ""


@dataclass(frozen=True)
class Nota:
    numero: str = ""
    cnpj: str = ""
    valor: Decimal | None = None
    emissao: date | None = None


def ler_nota(texto: str) -> Nota:
    """Número (da chave, do "Nº 000.008.957" do DANFE ou dos rótulos da NFS-e), CNPJ do
    emitente (da chave; na NFS-e, o do prestador), valor total e data de emissão."""
    texto = texto or ""
    numero, cnpj = "", ""
    if (chave := _chave(texto)):
        cnpj = chave[6:20]
        numero = _sem_zeros(chave[25:34])
    if not numero or numero == "0":
        achado = _DANFE.search(texto)
        numero = _sem_zeros(achado.group(1)) if achado else ""
    if not numero or numero == "0":
        for padrao in _ROTULOS_NUMERO:
            if (achado := padrao.search(texto)) and (n := _sem_zeros(achado.group(1))) != "0":
                numero = n
                break
    if not cnpj and (achado := _PRESTADOR.search(texto)):
        cnpj = re.sub(r"\D", "", achado.group(1))
    valor = None
    for padrao in _VALOR_NOTA:
        if (achado := padrao.search(texto)):
            valor = _dinheiro(achado.group(1))
            break
    emissao = _data(achado.group(1)) if (achado := _EMISSAO.search(texto)) else None
    return Nota(numero if numero != "0" else "", cnpj, valor, emissao)


@dataclass(frozen=True)
class OrdemBancaria:
    numero: str = ""
    data: date | None = None
    valor: Decimal | None = None


def ler_ob(texto: str) -> OrdemBancaria:
    texto = texto or ""
    numero = ""
    for padrao in _OB_NUMERO:
        if (achado := padrao.search(texto)):
            numero = re.sub(r"\s+", "", achado.group(1)).upper().strip(".-/")
            break
    achado = _OB_DATA.search(texto) or _DATA.search(texto)
    data = _data(achado.group(1)) if achado else None
    valor = _dinheiro(achado.group(1)) if (achado := _OB_VALOR.search(texto)) else None
    return OrdemBancaria(numero, data, valor)


def _moeda(v: Decimal) -> str:
    inteiro, _, cent = f"{v:.2f}".partition(".")
    return f"R$ {int(inteiro):,}".replace(",", ".") + f",{cent}"


def avisos_da_nota(nota: Nota, *, cnpj_fornecedor: str, razao: str, cnpj_formatado: str,
                   quantidade: int, unitario: Decimal | None, data_evento: date | None,
                   repetida_em: str = "") -> list[str]:
    """A conferência só avisa (referência §4.1)."""
    avisos = []
    if nota.cnpj and cnpj_fornecedor and nota.cnpj != cnpj_fornecedor:
        c = nota.cnpj
        formatado = f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else c
        avisos.append(f"A nota foi emitida pelo CNPJ {formatado}, e não pelo do fornecedor do "
                      f"lote ({razao}, {cnpj_formatado}).")
    if nota.valor is not None and unitario is not None:
        esperado = (Decimal(quantidade) * unitario).quantize(Decimal("0.01"))
        if nota.valor != esperado:
            avisos.append(f"O valor da nota ({_moeda(nota.valor)}) não bate com {quantidade} "
                          f"pessoas × {_moeda(unitario)} = {_moeda(esperado)}. Se a nota "
                          "cobrou outra quantidade, informe as pessoas faturadas.")
    if nota.emissao and data_evento and nota.emissao < data_evento:
        avisos.append(f"A nota foi emitida em {nota.emissao:%d/%m/%Y}, antes do evento "
                      f"({data_evento:%d/%m/%Y}).")
    if repetida_em:
        avisos.append(f"A nota {nota.numero} do {razao} já está na {repetida_em}.")
    return avisos


def aviso_da_ob(valor_ob: Decimal | None, soma_notas: Decimal | None) -> str:
    if valor_ob is None or soma_notas is None or valor_ob == soma_notas:
        return ""
    return (f"O valor da ordem bancária ({_moeda(valor_ob)}) não bate com o valor das notas "
            f"fiscais ({_moeda(soma_notas)}). Confira o PDF anexado (retenções de imposto "
            "explicam diferença).")
