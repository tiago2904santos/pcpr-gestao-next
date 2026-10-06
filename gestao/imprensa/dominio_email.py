"""Leitura do e-mail (ou mensagem) do jornalista em Python puro (I2; comportamento da
referência, `atendimento_imprensa/preenchimento.py` — implementação própria): data e hora
do envio, quem pede (o nome do remetente ou a apresentação "Sou X, da Y"), o veículo (o
nome de um cadastrado citado no texto, ou o domínio do remetente), o contato (e-mail e
telefone), o pedido (assunto + corpo, sem cabeçalhos e sem a despedida) e o prazo ("até as
17h de hoje", "até amanhã", "até 14/10") — a hora do prazo, que não tem campo, vai no texto
do pedido. Só sugere; nada grava.

Trabalha no texto "dobrado" (minúsculo, sem acento, mesmo comprimento) para as posições
valerem no original."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

LIMITE_PEDIDO = 6000
DOMINIOS_GENERICOS = frozenset({
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.com.br", "outlook.com",
    "outlook.com.br", "live.com", "msn.com", "yahoo.com", "yahoo.com.br", "icloud.com",
    "me.com", "uol.com.br", "bol.com.br", "terra.com.br", "ig.com.br", "protonmail.com",
    "proton.me"})
DIAS_DA_SEMANA = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4,
                  "sabado": 5, "domingo": 6}
CABECALHOS = ("de", "from", "para", "to", "cc", "cco", "bcc", "enviado em", "enviada em",
              "sent", "date", "data", "assunto", "subject")
DESPEDIDAS = ("att", "atenciosamente", "abs", "abraco", "abracos", "obrigad", "grat",
              "cordialmente", "sds", "saudacoes", "--")


def dobrar(texto: str) -> str:
    return "".join(unicodedata.normalize("NFD", c)[0].lower() for c in texto)


@dataclass(frozen=True)
class Prazo:
    data: date
    hora: time | None
    trecho: str


@dataclass
class Leitura:
    data: date | None = None
    horario: time | None = None
    jornalista: str = ""
    veiculo_id: int | None = None
    veiculo_texto: str = ""  # nome lido que não está no cadastro (sugestão)
    contato: str = ""
    pedido: str = ""
    prazo: Prazo | None = None

    @property
    def vazia(self) -> bool:
        # Um "ok"/"obrigado" solto não é pedido: sem quem pede, contato nem prazo, o texto
        # precisa ter um mínimo para virar sugestão.
        return not any((self.jornalista, self.contato, self.prazo)) and len(self.pedido) < 20


# ---------------------------------------------------------------- cabeçalhos
_R_CABECALHO = re.compile(r"^\s*(" + "|".join(re.escape(c) for c in CABECALHOS)
                          + r")\s*:\s*(.*)$")
_R_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_R_TELEFONE = re.compile(r"(?:\+?55\s?)?\(?\b\d{2}\)?\s?9?\d{4}[-.\s]?\d{4}\b")
_R_DATA_HORA = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})(?:\D{1,8}(\d{1,2})[:h](\d{2}))?")
_R_DATA_EXT = re.compile(r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})"
                         r"(?:\D{1,8}(\d{1,2})[:h](\d{2}))?")
MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
         "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11,
         "dezembro": 12}


def cabecalhos(texto: str) -> dict[str, str]:
    """Os cabeçalhos do primeiro bloco de e-mail colado (De, Enviado em, Assunto…)."""
    saida: dict[str, str] = {}
    for linha in texto.splitlines()[:30]:
        m = _R_CABECALHO.match(dobrar(linha))
        if m:
            chave = m.group(1)
            if chave not in saida:
                saida[chave] = linha[m.start(2):].strip()
    return saida


def _quando(valor: str) -> datetime | None:
    d = dobrar(valor)
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


def _corpo(texto: str) -> str:
    """O texto sem as linhas de cabeçalho e sem a despedida/assinatura."""
    linhas = [linha for linha in texto.splitlines() if not _R_CABECALHO.match(dobrar(linha))]
    for i, linha in enumerate(linhas):
        d = dobrar(linha).strip()
        if i > 0 and any(d.startswith(x) for x in DESPEDIDAS):
            linhas = linhas[:i]
            break
    return "\n".join(linhas).strip()


# ---------------------------------------------------------------- quem pede e veículo
_R_APRESENTACAO = re.compile(
    r"\b(?:sou|meu nome e|aqui e|quem fala e)\s+(?:o\s+|a\s+)?([a-z][a-z]+(?:\s+[a-z][a-z]+){0,3})"
    r"(?:\s*,\s*|\s+)(?:reporter|produtor[a]?|jornalista|editor[a]?|da|do|de)\b")


def _nome_do_remetente(de: str) -> str:
    nome = _R_EMAIL.sub("", de).replace("<", "").replace(">", "").replace('"', "").strip(" ,;")
    return " ".join(nome.split())[:150]


def _limpar_nome(nome: str) -> str:
    return " ".join(p.capitalize() if p.islower() else p for p in nome.split())


def quem_pede(texto: str, cab: dict[str, str]) -> str:
    """A apresentação no corpo ("Sou Ana Lima, repórter da Y") ganha do nome do remetente."""
    d = dobrar(texto)
    m = _R_APRESENTACAO.search(d)
    if m:
        return _limpar_nome(texto[m.start(1):m.end(1)])[:150]
    if (de := cab.get("de") or cab.get("from")):
        nome = _nome_do_remetente(de)
        if nome and dobrar(nome) not in ("redacao", "producao"):
            return nome
    return ""


def veiculo(texto: str, cab: dict[str, str],
            veiculos: list[tuple[int, str]]) -> tuple[int | None, str]:
    """(id, "") do veículo cadastrado citado no texto (o nome mais comprido); senão
    (None, nome do domínio do remetente) como sugestão."""
    d = dobrar(texto)
    achados = [(len(nome), pk) for pk, nome in veiculos
               if len(nome) >= 3 and re.search(r"\b" + re.escape(dobrar(nome)) + r"\b", d)]
    if achados:
        return max(achados)[1], ""
    de = cab.get("de") or cab.get("from") or ""
    if (m := _R_EMAIL.search(de)):
        dominio = m.group(0).split("@", 1)[1].lower()
        if dominio not in DOMINIOS_GENERICOS:
            raiz = dominio.split(".")[0]
            for pk, nome in veiculos:  # domínio "bandab" casa com "Banda B"
                if re.sub(r"[^a-z0-9]", "", dobrar(nome)) == raiz:
                    return pk, ""
            return None, raiz.upper() if len(raiz) <= 4 else raiz.capitalize()
    return None, ""


def contato(texto: str, cab: dict[str, str]) -> str:
    de = cab.get("de") or cab.get("from") or ""
    emails = [m.group(0) for m in _R_EMAIL.finditer(de)] or [m.group(0) for m in
                                                               _R_EMAIL.finditer(texto)]
    fones = [m.group(0).strip() for m in _R_TELEFONE.finditer(texto)]
    partes = list(dict.fromkeys([*fones[:1], *emails[:1]]))
    return " · ".join(partes)[:150]


# ---------------------------------------------------------------- prazo
_R_PRAZO = re.compile(r"\b(?:ate|prazo|deadline|fechamento|vai ao ar|veicula\w*|publica\w*)\b"
                      r"[^.\n]{0,60}")
_R_HORA = re.compile(r"\b(\d{1,2})\s*(?:h|:|horas?)\s*(\d{2})?\b")
_R_DIA = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")


def prazo(texto: str, referencia: date) -> Prazo | None:
    """O primeiro prazo dito: "até as 17h de hoje", "até amanhã às 10h", "até sexta",
    "vai ao ar dia 14/10"; sem dia, é o da referência (o envio)."""
    d = dobrar(texto)
    for m in _R_PRAZO.finditer(d):
        trecho = d[m.start():m.end()]
        dia = None
        if "depois de amanha" in trecho:
            dia = referencia + timedelta(days=2)
        elif "amanha" in trecho:
            dia = referencia + timedelta(days=1)
        elif "hoje" in trecho:
            dia = referencia
        elif (md := _R_DIA.search(trecho)):
            ano = int(md.group(3)) if md.group(3) else referencia.year
            ano = ano + 2000 if ano < 100 else ano
            try:
                dia = date(ano, int(md.group(2)), int(md.group(1)))
            except ValueError:
                dia = None
        else:
            for nome, wd in DIAS_DA_SEMANA.items():
                if re.search(r"\b" + nome, trecho):
                    dia = referencia + timedelta(days=(wd - referencia.weekday()) % 7 or 7)
                    break
        mh = _R_HORA.search(trecho)
        hora = None
        if mh and int(mh.group(1)) < 24 and int(mh.group(2) or 0) < 60:
            hora = time(int(mh.group(1)), int(mh.group(2) or 0))
        if dia is None and hora is None:
            continue
        return Prazo(dia or referencia, hora, " ".join(texto[m.start():m.end()].split()))
    return None


# ---------------------------------------------------------------- tudo
def ler(texto: str, agora: datetime, veiculos: list[tuple[int, str]]) -> Leitura:
    texto = (texto or "")[:20000]
    cab = cabecalhos(texto)
    enviado = _quando(cab.get("enviado em") or cab.get("enviada em") or cab.get("sent")
                      or cab.get("date") or cab.get("data") or "")
    referencia = enviado.date() if enviado else agora.date()
    corpo = _corpo(texto)
    assunto = re.sub(r"^(?:re|res|fw|fwd|enc)\s*:\s*", "",
                     cab.get("assunto") or cab.get("subject") or "", flags=re.I).strip()
    p = prazo(f"{assunto}\n{corpo}", referencia)
    partes = [f"Assunto: {assunto}"] if assunto else []
    if corpo:
        partes.append(corpo)
    if p is not None and p.hora is not None:
        partes.append(f"Prazo pedido: até {p.hora:%H:%M} de {p.data:%d/%m/%Y}.")
    pedido = "\n\n".join(partes)
    if len(pedido) > LIMITE_PEDIDO:
        pedido = pedido[:LIMITE_PEDIDO].rstrip() + "…"
    vid, vtexto = veiculo(f"{assunto}\n{corpo}", cab, veiculos)
    return Leitura(
        data=referencia if (enviado or pedido) else None,
        horario=(enviado.time() if enviado and (enviado.hour or enviado.minute) else None),
        jornalista=quem_pede(corpo, cab), veiculo_id=vid, veiculo_texto=vtexto,
        contato=contato(texto, cab), pedido=pedido, prazo=p)
