"""Leitura do e-mail de pedido de coffee break em Python puro (CB7c; comportamento da
referência, `coffee_break/preenchimento.py` §11 — implementação própria): sugere a data, o
horário, o município, o evento, a quantidade ("2 turmas de 25", "quarenta pessoas"), o
local, o endereço, o CEP e quem recebe. Só sugere: a pessoa confere antes de registrar.
Nunca sugere o nº da OS.

Tudo trabalha no texto "dobrado" (minúsculo e sem acento, com o mesmo comprimento do
original), para as posições valerem nos dois."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, time

MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
         "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
UNIDADES = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
            "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12,
            "treze": 13, "quatorze": 14, "catorze": 14, "quinze": 15, "dezesseis": 16,
            "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20, "trinta": 30,
            "quarenta": 40, "cinquenta": 50, "sessenta": 60, "setenta": 70, "oitenta": 80,
            "noventa": 90, "cem": 100, "cento": 100, "duzentos": 200, "duzentas": 200,
            "trezentos": 300, "trezentas": 300, "quatrocentos": 400, "quatrocentas": 400,
            "quinhentos": 500, "quinhentas": 500}
GENTE = (r"(?:pessoas?|participantes|alunos?|alunas?|convidados?|servidores?|policiais|"
         r"kits?|lanches?|unidades|inscritos?|integrantes|estudantes|agentes|pax)")
SAUDACOES = ("bom dia", "boa tarde", "boa noite", "ola", "prezad", "caro", "cara ", "senhor",
             "sr.", "sra.", "att", "atenciosamente", "obrigad", "de:", "para:", "enviado",
             "cc:", "data:", "date:", "from:", "to:")


def dobrar(texto: str) -> str:
    """Minúsculo e sem acento, caractere a caractere (o comprimento não muda)."""
    return "".join(unicodedata.normalize("NFD", c)[0].lower() for c in texto)


def impressao(texto: str) -> str:
    """A "digital" do e-mail (para achar as OS já criadas a partir dele)."""
    return hashlib.sha256(" ".join(dobrar(texto).split()).encode()).hexdigest()


# ---------------------------------------------------------------- quantidade
_R_PALAVRAS = re.compile(r"\b(?:" + "|".join(sorted(UNIDADES, key=len, reverse=True))
                         + r")(?:\s+e\s+(?:" + "|".join(sorted(UNIDADES, key=len,
                                                                reverse=True)) + r"))*\b")


def _por_extenso(dobrado: str) -> str:
    """"quarenta e cinco" → "45" com o mesmo comprimento (preenchido com espaços); "um"
    sozinho fica (não é quantidade)."""
    def trocar(m: re.Match) -> str:
        partes = re.split(r"\s+e\s+", m.group(0))
        if partes in (["um"], ["uma"]):
            return m.group(0)
        n = str(sum(UNIDADES[p] for p in partes))
        return n + " " * (len(m.group(0)) - len(n))
    return _R_PALAVRAS.sub(trocar, dobrado)


_R_TURMAS = re.compile(r"\b(\d{1,2})\s+turmas?\s+de\s+(\d{1,4})\b")
_R_SOMA = re.compile(r"\b(\d{1,4})\s+[a-z]+\s*\+\s*(\d{1,4})\s+[a-z]+")
_R_ROTULO = re.compile(r"\b(?:quantidade|qtd\.?|pessoas|participantes|publico(?:\s+estimado)?|"
                       r"efetivo)\s*(?:de\s+)?[:=-]?\s*(\d{1,4})\b(?!\s*(?:h\b|:|/))")
_R_COM_GENTE = re.compile(r"\b(\d{1,4})\s*(?:\([^)]{1,30}\)\s*)?" + GENTE + r"\b")
_R_PARA = re.compile(r"\b(?:coffee(?:[\s-]?break)?|cafe|lanches?|kits?)\b[^.\n]{0,40}?"
                     r"\b(?:para|pra|p/)\s+(?:cerca\s+de\s+|aproximadamente\s+|uns\s+|umas\s+)?"
                     r"(\d{1,4})\b(?!\s*(?:h\b|hs\b|horas?|:|/))")
_R_CORRECAO = re.compile(r"\b(?:corrig\w*|retific\w*|na\s+verdade|desconsider\w*)\b")


@dataclass(frozen=True)
class Quantidade:
    valor: int
    trecho: str


def quantidade(texto: str) -> Quantidade | None:
    """Quantas pessoas: produto ("2 turmas de 25"), soma ("30 alunos + 10 instrutores"),
    rótulo ("Quantidade: 25"), número com gente ("40 pessoas") ou "coffee para 30". Com
    correção no texto ("corrigindo, serão 36 pessoas"), vale a última; senão a primeira."""
    if not texto:
        return None
    original = dobrar(texto)
    d = _por_extenso(original)
    achados: list[tuple[int, int, str]] = []
    tomados: list[tuple[int, int]] = []
    for regex, conta in ((_R_TURMAS, lambda a, b: a * b), (_R_SOMA, lambda a, b: a + b)):
        for m in regex.finditer(d):
            achados.append((m.start(), conta(int(m.group(1)), int(m.group(2))),
                            texto[m.start():m.end()]))
            tomados.append((m.start(), m.end()))
    for regex in (_R_ROTULO, _R_COM_GENTE, _R_PARA):
        for m in regex.finditer(d):
            if all(m.end(1) <= a or m.start(1) >= b for a, b in tomados):
                achados.append((m.start(1), int(m.group(1)), texto[m.start():m.end()]))
                tomados.append((m.start(1), m.end(1)))
    achados = sorted(a for a in achados if 0 < a[1] <= 5000)
    if not achados:
        return None
    if (corr := list(_R_CORRECAO.finditer(d))):
        depois = [a for a in achados if a[0] > corr[-1].start()]
        if depois:
            return Quantidade(depois[-1][1], " ".join(depois[-1][2].split()))
    return Quantidade(achados[0][1], " ".join(achados[0][2].split()))


# ---------------------------------------------------------------- datas e horário
_R_DATA = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
_R_DATA_EXT = re.compile(r"\b(\d{1,2})(?:º|o)?\s+de\s+(" + "|".join(MESES)
                         + r")(?:\s+de\s+(\d{4}))?\b")
_R_FAIXA = re.compile(r"\b(\d{1,2})\s+(?:a|ate|e)\s+(\d{1,2})(?:\s+de\s+(" + "|".join(MESES)
                      + r")|/(\d{1,2}))(?:(?:\s+de\s+|/)(\d{2,4}))?\b")


def _ano(texto_ano: str | None, mes: int, dia: int, hoje: date) -> int:
    if texto_ano:
        ano = int(texto_ano)
        return ano + 2000 if ano < 100 else ano
    # Sem ano: o deste ano, ou o do próximo se a data já passou há mais de 2 meses.
    try:
        candidata = date(hoje.year, mes, dia)
    except ValueError:
        return hoje.year
    return hoje.year + 1 if (hoje - candidata).days > 60 else hoje.year


def _data(dia: int, mes: int, ano: int) -> date | None:
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def datas(texto: str, hoje: date) -> list[date]:
    """As datas do evento citadas (sem repetir, em ordem): "14/10", "14/10/2026", "14 de
    outubro", e as faixas "14 a 16/10" / "14 e 15 de outubro" (todos os dias)."""
    d = dobrar(texto or "")
    saida: list[date] = []
    tomados: list[tuple[int, int]] = []
    for m in _R_FAIXA.finditer(d):
        mes = MESES[m.group(3)] if m.group(3) else int(m.group(4))
        a, b = int(m.group(1)), int(m.group(2))
        if not 1 <= mes <= 12 or not a < b <= 31 or b - a > 10:
            continue
        ano = _ano(m.group(5), mes, a, hoje)
        saida.extend(x for x in (_data(dia, mes, ano) for dia in range(a, b + 1)) if x)
        tomados.append((m.start(), m.end()))
    for m in list(_R_DATA.finditer(d)) + list(_R_DATA_EXT.finditer(d)):
        if any(a <= m.start() < b for a, b in tomados):
            continue
        dia = int(m.group(1))
        mes = int(m.group(2)) if m.group(2).isdecimal() else MESES[m.group(2)]
        if not (1 <= mes <= 12 and 1 <= dia <= 31):
            continue
        if (x := _data(dia, mes, _ano(m.group(3), mes, dia, hoje))):
            saida.append(x)
    vistas: list[date] = []
    for x in sorted(saida):
        if x not in vistas:
            vistas.append(x)
    return vistas


_R_HORA = re.compile(r"\b(?:as\s+)?(\d{1,2})\s*(?:h|hs|:|horas?)\s*(\d{2})?\b(?!\s*/)")
_R_PERTO = re.compile(r"\b(?:coffee|cafe|lanche|intervalo|entrega|servir|servido)\b")


def horario(texto: str) -> time | None:
    """O horário do coffee: o mais perto de "coffee/lanche/intervalo/entrega"; senão o
    primeiro citado."""
    d = dobrar(texto or "")
    horas = []
    for m in _R_HORA.finditer(d):
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if h <= 23 and mi <= 59:
            horas.append((m.start(), time(h, mi)))
    if not horas:
        return None
    perto = [m.start() for m in _R_PERTO.finditer(d)]
    if perto:
        return min(horas, key=lambda par: min(abs(par[0] - p) for p in perto))[1]
    return horas[0][1]


# ---------------------------------------------------------------- campos com rótulo
def _rotulado(texto: str, rotulos: tuple[str, ...]) -> str:
    """O valor de "Rótulo: valor" numa linha do e-mail (o primeiro rótulo achado)."""
    for linha in texto.splitlines():
        d = dobrar(linha)  # mesmo comprimento: as posições valem para a linha original
        for r in rotulos:
            m = re.match(r"\s*[*>-]*\s*" + r + r"\s*[:=-]\s*(.+)$", d)
            if m:
                return " ".join(linha[m.start(1):].split()).strip(" .;")
    return ""


_R_ENDERECO = re.compile(r"\b(?:rua|r\.|avenida|av\.?|alameda|al\.|travessa|rodovia|praca|"
                         r"estrada)\s+[^\n,;]{3,80}(?:,\s*(?:n[o°º.]*\s*)?\d{1,6}[a-z]?)?")
_R_CEP = re.compile(r"\b(\d{5})-?(\d{3})\b")
_R_LOCAL = re.compile(r"\b(?:no|na|em)\s+((?:auditorio|salao|sala|ginasio|teatro|anfiteatro|"
                      r"sede|plenario|espaco|centro|clube|igreja|escola|colegio|"
                      r"delegacia|quartel|academia|biblioteca|capela)\b[^\n,.;:()]{0,60})")


def _municipio(texto: str, nomes: dict[str, str]) -> str:
    """O município do PR citado (o nome mais comprido que aparece como palavra inteira;
    prefere o que vem depois de "em", "município de", "cidade de")."""
    d = dobrar(texto)
    achados = []
    for dobrado, nome in nomes.items():
        for m in re.finditer(r"\b" + re.escape(dobrado) + r"\b", d):
            antes = d[max(0, m.start() - 15):m.start()]
            forte = bool(re.search(r"(?:\bem|municipio de|cidade de|\bde)\s*$", antes))
            achados.append((not forte, -len(dobrado), m.start(), nome))
    return min(achados)[3] if achados else ""


def _evento(texto: str) -> str:
    if (v := _rotulado(texto, ("evento", "assunto", "objeto", "motivo"))):
        return re.sub(r"^(?:re|fw|fwd|enc)\s*:\s*", "", v, flags=re.I)[:300]
    for linha in texto.splitlines():
        limpa = " ".join(linha.split())
        if len(limpa) >= 12 and not dobrar(limpa).startswith(SAUDACOES):
            return limpa[:300]
    return ""


@dataclass
class Leitura:
    data: date | None = None
    dias: list[date] = field(default_factory=list)
    horario: time | None = None
    municipio: str = ""
    descricao: str = ""
    quantidade: Quantidade | None = None
    local: str = ""
    endereco: str = ""
    bairro: str = ""
    cep: str = ""
    responsavel: str = ""

    @property
    def vazia(self) -> bool:
        return not any((self.data, self.horario, self.municipio, self.descricao,
                        self.quantidade, self.local, self.endereco, self.responsavel))


def ler(texto: str, hoje: date, nomes_de_municipios: dict[str, str]) -> Leitura:
    """`nomes_de_municipios`: nome dobrado → "Cidade/PR"."""
    texto = (texto or "")[:20000]
    dias = [d for d in datas(texto, hoje) if (d - hoje).days >= -30]
    cep = _R_CEP.search(texto)
    endereco = _rotulado(texto, ("endereco", r"end\."))
    if not endereco and (m := _R_ENDERECO.search(dobrar(texto))):
        endereco = texto[m.start():m.end()]
    local = _rotulado(texto, ("local de entrega", "local do evento", "local", "entrega")) or (
        texto[m.start(1):m.end(1)] if (m := _R_LOCAL.search(dobrar(texto))) else "")
    return Leitura(
        data=dias[0] if dias else None, dias=dias, horario=horario(texto),
        municipio=_municipio(texto, nomes_de_municipios), descricao=_evento(texto),
        quantidade=quantidade(texto), local=" ".join(local.split())[:255],
        endereco=" ".join(endereco.split())[:255],
        bairro=_rotulado(texto, ("bairro",))[:120],
        cep=f"{cep.group(1)}-{cep.group(2)}" if cep else "",
        responsavel=_rotulado(texto, ("quem recebe", "recebe", "recebimento", "responsavel",
                                      "contato", "receber"))[:200])
