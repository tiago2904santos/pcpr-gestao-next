"""Conferência da via assinada (paridade com o m112 da referência), em Python puro.

Recebe o que se leu do PDF — o texto das primeiras páginas e os campos de assinatura — e
diz, como aviso (nunca bloqueio):

- se há assinatura digital: campo de assinatura do PDF (ICP-Brasil, gov.br, Adobe) ou
  carimbo desenhado na página (eProtocolo "Assinatura Avançada realizada por…", ICP
  "Assinado de forma digital por…", gov.br "Documento assinado digitalmente…");
- quem assinou e quando;
- se o PDF é do documento certo: o número (ofício, OS), o protocolo e os nomes que o
  documento tem de trazer.

A leitura do arquivo fica em `viagens/documentos/leitura.py` (ADR 0022).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

PAGINAS_LIDAS = 4

_DATA = r"(\d{2}/\d{2}/\d{4})(?:\s*(?:às|as|-)?\s*(\d{2}:\d{2})(?::\d{2})?)?"
# eProtocolo: "Assinatura Avançada realizada por: NOME (XXX.123.456-XX) em 24/09/2026 11:13"
RX_EPROTOCOLO = re.compile(
    r"Assinatura\s+(?:Avan[çc]ada|Qualificada(?:\s+Externa)?|Simples)\s+realizada\s+por:?\s*"
    r"([^\n(]+?)\s*(?:\([\dXx*.\-\s]{11,18}\))?\s+em:?\s*" + _DATA, re.I)
# ICP (Adobe e afins): "Assinado de forma digital por NOME:12345678901 Dados: 2026.09.24 10:30"
RX_ICP = re.compile(
    r"Assinado\s+(?:de\s+forma\s+)?digital(?:mente)?\s+por:?\s*([A-ZÀ-Ý][A-ZÀ-Ý .'-]+?)"
    r"\s*(?::\s*\d{11})?\s*(?:Dados|Data)\s*:?\s*(\d{4})\.(\d{2})\.(\d{2})\s*(\d{2}:\d{2})?",
    re.I)
# gov.br: "Documento assinado digitalmente NOME Data: 24/09/2026 10:30:00-0300"
RX_GOVBR = re.compile(
    r"Documento\s+assinado\s+digitalmente\s+([A-ZÀ-Ý][A-ZÀ-Ý .'-]+?)\s+Data:\s*" + _DATA, re.I)
# "Ofício nº 12/2026", "Ordem de Serviço 007/2026", "OS 7/2026", "Justificativa 12/2026"
RX_NUMERO = re.compile(
    r"(?:Of[ií]cio|Ordem\s+de\s+Servi[çc]o|O\.?S\.?|Justificativa)\s*(?:n)?[ºo°.]*\s*"
    r"(\d{1,4})\s*/\s*(\d{4})", re.I)
# Protocolo do eProtocolo: 26.613.666-8 (pontos opcionais; o RG tem a mesma máscara).
RX_PROTOCOLO = re.compile(r"(?<![\d.])(\d{2})\.?(\d{3})\.?(\d{3})-(\d)(?![\d])")
RX_RG_ANTES = re.compile(r"RG\s*(?:n\.?\s*[ºo°]?)?\s*:?\s*$", re.I)


@dataclass
class Assinante:
    nome: str
    quando: datetime | None = None
    origem: str = ""  # "certificado" | "campo" | "eprotocolo" | "carimbo"

    def como_json(self) -> dict:
        return {"nome": self.nome, "quando": self.quando.isoformat() if self.quando else "",
                "origem": self.origem}


@dataclass
class Conferencia:
    assinado: bool = False
    assinantes: list[Assinante] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    sem_texto: bool = False

    @property
    def assinante(self) -> Assinante | None:
        """O do campo/certificado vale mais que o carimbo (que é só desenho)."""
        for origem in ("certificado", "campo", "eprotocolo", "carimbo"):
            for a in self.assinantes:
                if a.origem == origem and a.nome:
                    return a
        return self.assinantes[0] if self.assinantes else None

    def resumo(self) -> str:
        if not self.assinado:
            return "Este PDF não tem assinatura digital reconhecível."
        quem = self.assinante
        if quem is None or not quem.nome:
            return "PDF com assinatura digital."
        texto = f"Assinado digitalmente por {quem.nome}"
        if quem.quando:
            q = quem.quando
            texto += f" em {q:%d/%m/%Y %H:%M}" if (q.hour or q.minute) else f" em {q:%d/%m/%Y}"
        return texto + "."

    def como_json(self) -> dict:
        return {"assinado": self.assinado, "resumo": self.resumo(), "avisos": list(self.avisos),
                "sem_texto": self.sem_texto,
                "assinantes": [a.como_json() for a in self.assinantes]}


@dataclass
class Esperado:
    """O que o PDF deste documento tem de trazer."""

    numero: str = ""  # "12/2026"
    protocolo: str = ""  # com ou sem máscara
    nomes: list[str] = field(default_factory=list)
    rotulo: str = "documento"  # "ofício", "ordem de serviço", "termo do ofício"


def normalizar(texto: str) -> str:
    """Caixa alta, sem acento, espaços colapsados (NFKD desfaz ligaduras de PDF: "ﬁ")."""
    decomposto = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.upper().split())


def _quando(dia: str, hora: str | None) -> datetime | None:
    try:
        return datetime.strptime(f"{dia} {hora or '00:00'}", "%d/%m/%Y %H:%M")
    except ValueError:
        return None


def carimbos(texto: str) -> list[Assinante]:
    """Assinaturas escritas na página (o desenho do carimbo, não o certificado)."""
    corrido = " ".join((texto or "").split())
    saida = [Assinante(m.group(1).strip(), _quando(m.group(2), m.group(3)), "eprotocolo")
             for m in RX_EPROTOCOLO.finditer(corrido)]
    for m in RX_ICP.finditer(corrido):
        dia = f"{m.group(4)}/{m.group(3)}/{m.group(2)}"
        saida.append(Assinante(m.group(1).strip(), _quando(dia, m.group(5)), "carimbo"))
    saida += [Assinante(m.group(1).strip(), _quando(m.group(2), m.group(3)), "carimbo")
              for m in RX_GOVBR.finditer(corrido)]
    return saida


def numero_normalizado(numero: str) -> str:
    m = re.search(r"(\d{1,4})\s*/\s*(\d{4})", numero or "")
    return f"{int(m.group(1)):03d}/{m.group(2)}" if m else ""


def numeros_no_texto(texto: str) -> set[str]:
    return {f"{int(n):03d}/{ano}" for n, ano in RX_NUMERO.findall(texto or "")}


def protocolos_no_texto(texto: str) -> list[str]:
    saida = []
    for m in RX_PROTOCOLO.finditer(texto or ""):
        if RX_RG_ANTES.search(texto[max(0, m.start() - 16):m.start()]):
            continue
        digitos = "".join(m.groups())
        if digitos not in saida:
            saida.append(digitos)
    return saida


def _mascara(p: str) -> str:
    return f"{p[:2]}.{p[2:5]}.{p[5:8]}-{p[8:]}"


def conferir(texto: str, campos: list[Assinante], esperado: Esperado, *,
             paginas: int, legivel: bool = True) -> Conferencia:
    """`texto`: o das primeiras páginas; `campos`: os campos de assinatura preenchidos;
    `paginas`: quantas páginas se leram; `legivel`: se o PDF abriu."""
    conferencia = Conferencia(assinantes=list(campos))
    if not legivel:
        conferencia.avisos.append("Não foi possível ler o PDF para conferir se é o documento "
                                  "certo.")
    conferencia.assinantes += carimbos(texto)
    conferencia.assinado = bool(conferencia.assinantes)
    if paginas and not texto.strip():
        conferencia.sem_texto = True
        conferencia.avisos.append("O PDF é só imagem (digitalizado): não deu para conferir se "
                                  "é o documento certo.")
        return conferencia
    if not texto.strip():
        return conferencia
    alvo = numero_normalizado(esperado.numero)
    achados = numeros_no_texto(texto)
    if alvo and achados and alvo not in achados:
        conferencia.avisos.append(f"O número neste PDF é {', '.join(sorted(achados))}, mas "
                                  f"você está anexando no {esperado.rotulo} {alvo}.")
    digitos = re.sub(r"\D", "", esperado.protocolo or "")
    protocolos = protocolos_no_texto(texto)
    if len(digitos) == 9 and protocolos and digitos not in protocolos:
        conferencia.avisos.append(f"O protocolo neste PDF é {_mascara(protocolos[0])}, mas o "
                                  f"{esperado.rotulo} é do protocolo {_mascara(digitos)}.")
    corrido = normalizar(texto)
    for nome in esperado.nomes:
        nome = (nome or "").strip()
        if nome and normalizar(nome) not in corrido:
            conferencia.avisos.append(f"O nome {nome} não aparece neste PDF.")
    return conferencia
