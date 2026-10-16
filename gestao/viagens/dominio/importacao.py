"""Identificação documental pura. Texto é evidência, nunca instrução executável."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

TIPOS = {
    "oficio": "Ofício",
    "justificativa": "Justificativa",
    "termo": "Termo de autorização",
    "ordem": "Ordem de serviço",
    "despacho": "Despacho",
    "db_assinado": "Diário de bordo",
    "rt_assinado": "Relatório técnico",
    "comprovante": "Comprovante",
}
TITULOS = (
    ("termo", r"TERMO\s+DE\s+AUTORIZACAO"),
    ("ordem", r"ORDEM\s+DE\s+SERVICO"),
    ("rt_assinado", r"RELATORIO\s+(?:TECNICO|DE VIAGEM)"),
    ("db_assinado", r"DIARIO\s+DE\s+BORDO"),
    ("justificativa", r"JUSTIFICATIVA(?:\s+DE\s+PRAZO)?"),
    ("despacho", r"DESPACHO"),
    ("comprovante", r"(?:COMPROVANTE|RECIBO)\s+(?:DE\s+)?(?:TRANSFERENCIA|SAQUE|PIX|PAGAMENTO)"),
    ("oficio", r"OFICIO\s*(?:N[Oº°.]*\s*)?\d"),
)


def normalizar(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    ).upper()


def tipo_do_texto(texto: str) -> str:
    # Cabeçalho/título: menção no corpo ("encaminhe o despacho") não muda o tipo.
    linhas = normalizar(texto).splitlines()[:24]
    for linha in linhas:
        linha = linha.strip()
        for tipo, padrao in TITULOS:
            if re.match(r"^(?:\d+[.\s-]+)?" + padrao, linha):
                return tipo
    return ""


@dataclass(frozen=True)
class Parte:
    inicio: int  # páginas 1-based, inclusive
    fim: int
    tipo: str
    texto: str


def separar(textos: list[str]) -> list[Parte]:
    partes: list[Parte] = []
    inicio, atual = 1, ""
    linhas: list[str] = []
    for numero, texto in enumerate(textos, 1):
        tipo = tipo_do_texto(texto)
        # Um título de outro documento não é uma continuação do ofício anterior.
        # Conserva a parte para revisão, em vez de anexar silenciosamente uma nota
        # fiscal/declaração desconhecida junto de uma via identificada.
        outro_titulo = not tipo and any(
            re.match(
                r"^(?:NOTA FISCAL|DANFE|FATURA|CERTIDAO|BOLETO|RECIBO|COMPROVANTE|"
                r"RELATORIO|REQUERIMENTO|DECLARACAO)\b",
                linha.strip(),
            )
            for linha in normalizar(texto).splitlines()[:16]
        )
        # Cabeçalho repetido em continuação explicitamente numerada não separa.
        continuacao = bool(re.search(r"P[ÁA]GINA\s+[2-9]\d*\s*(?:DE|/)", texto, re.I))
        if linhas and (tipo or outro_titulo) and not (tipo == atual and continuacao):
            partes.append(Parte(inicio, numero - 1, atual, "\n".join(linhas)))
            inicio, linhas = numero, []
        if not linhas:
            atual = tipo
        linhas.append(texto)
    if linhas:
        partes.append(Parte(inicio, len(textos), atual, "\n".join(linhas)))
    return partes


def referencias(texto: str, rotulo: str = "OFICIO") -> set[tuple[int, int | None]]:
    texto = normalizar(texto)
    padrao = (
        rf"\b{rotulo}\s*(?:N(?:UMERO|[Oº°.°]*)\s*)?[:#-]?\s*"
        r"(\d{1,6})(?:\s*[/\-]\s*(\d{2,6}))?\b"
    )
    return {
        (int(n), (2000 + int(a) if len(a) == 2 else int(a)) if a else None)
        for n, a in re.findall(padrao, texto)
    }


def protocolos(texto: str) -> set[str]:
    return set(
        re.findall(r"(?:E-?)?PROTOCOLO\s*(?:N[O.°]*\s*)?[:#-]?\s*(\d{9})\b", normalizar(texto))
    ) | {re.sub(r"\D", "", n) for n in re.findall(r"\b\d{2}\.\d{3}\.\d{3}-\d\b", texto)}


@dataclass(frozen=True)
class Destino:
    chave: str
    tipo: str
    rotulo: str
    numero: int = 0
    ano: int = 0
    protocolo: str = ""
    nome: str = ""
    cpf: str = ""
    inicio: str = ""  # DD/MM/AAAA (termo sem referência ao ofício)
    periodo: str = ""  # período completo por extenso, com ano


@dataclass(frozen=True)
class Decisao:
    chave: str = ""
    motivo: str = "Não encontrei um destino único. Confira o documento."
    candidatos: tuple[str, ...] = ()


def identificar(parte: Parte, destinos: list[Destino]) -> Decisao:
    if not parte.tipo:
        return Decisao(motivo="Não reconheci o tipo do documento. Escolha na revisão.")
    texto = normalizar(parte.texto)
    corrido = re.sub(r"\s+", " ", texto)
    if re.search(r"\b(?:MINUTA|RASCUNHO)\b", texto):
        return Decisao(
            motivo="O documento contém marca de minuta ou rascunho. Confira antes de anexar."
        )
    refs = referencias(texto, "ORDEM DE SERVICO" if parte.tipo == "ordem" else "OFICIO")
    prots = protocolos(texto)
    base = [d for d in destinos if d.tipo == parte.tipo]
    candidatos = base
    evidencias = []
    # Interseção de TODAS as referências: conflito não vira desempate por pontuação.
    if refs:
        candidatos = [
            d
            for d in candidatos
            if all(d.numero == n and (a is None or d.ano == a) for n, a in refs)
        ]
        evidencias.append("número do documento")
    if prots:
        candidatos = [d for d in candidatos if d.protocolo and d.protocolo in prots]
        if len(prots) > 1:
            return Decisao(motivo="Há protocolos diferentes nesta parte. Confira o destino.")
        evidencias.append("protocolo")
    pessoal = parte.tipo in {"termo", "rt_assinado", "comprovante"}
    if pessoal:
        cpfs = {
            re.sub(r"\D", "", c)
            for c in re.findall(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b", texto)
        }
        pelo_cpf = [d for d in candidatos if d.cpf and d.cpf in cpfs]
        pelo_nome = [
            d
            for d in candidatos
            if len(d.nome.split()) >= 2
            and re.search(r"(?<!\w)" + re.escape(normalizar(d.nome)) + r"(?!\w)", corrido)
        ]
        if pelo_cpf:
            candidatos = [d for d in pelo_cpf if not pelo_nome or d in pelo_nome]
            evidencias.append("CPF")
        elif not cpfs:
            candidatos = pelo_nome
            evidencias.append("nome completo")
        else:
            candidatos = []
        if not refs and not prots:
            # Pessoa sozinha não distingue viagens diferentes, nem mesmo um candidato atual.
            candidatos = [
                d
                for d in candidatos
                if (d.inicio and d.inicio in texto)
                or (d.periodo and normalizar(d.periodo) in corrido)
            ]
            evidencias.append("data do evento")
    elif not refs and not prots:
        candidatos = []
    unicos = {d.chave: d for d in candidatos}
    if len(unicos) == 1:
        return Decisao(next(iter(unicos)), "Identificado por " + ", ".join(evidencias) + ".")
    return Decisao(
        candidatos=tuple(unicos),
        motivo=(
            "Mais de um destino corresponde ao documento. Confira ano, pessoa e evento."
            if unicos
            else "As referências não identificam um destino. Confira tipo, número e pessoa."
        ),
    )


def identificar_conjunto(partes: list[Parte], destinos: list[Destino]) -> list[Decisao]:
    """Contexto do mesmo arquivo só quando todos os números concordam com um ofício.

    Nunca usar arquivos vizinhos do lote como prova. Um termo avulso não herda
    destino de outro documento apenas porque veio junto.
    """
    refs = set().union(*(referencias(p.texto) for p in partes))
    fortes = [p for p in partes if p.tipo == "oficio" and identificar(p, destinos).chave]
    contexto = next(iter(refs)) if len(refs) == 1 and fortes else None
    saida = []
    for p in partes:
        decisao = identificar(p, destinos)
        if (
            not decisao.chave
            and contexto
            and contexto[1]
            and p.tipo in {"despacho", "db_assinado", "rt_assinado", "comprovante"}
            and not referencias(p.texto)
            and not protocolos(p.texto)
        ):
            texto = p.texto + f"\nOfício {contexto[0]}/{contexto[1]}"
            contextual = identificar(Parte(p.inicio, p.fim, p.tipo, texto), destinos)
            if contextual.chave:
                decisao = Decisao(
                    contextual.chave, contextual.motivo + " Ofício identificado no mesmo arquivo."
                )
        saida.append(decisao)
    return saida
