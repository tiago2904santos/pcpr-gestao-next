"""Central de ajuda (AUT-97): base de procedimentos aprovados, versionada com o código.

Cada artigo é um Markdown em `conhecimento/` com cabeçalho (`id`, `titulo`, `natureza`,
`publico`, `situacao`, `versao`, `aprovado_por`, `aprovado_em`, `revisar_em`, `palavras`).
Só `situacao: aprovado` aparece na Central e serve de fonte ao assistente. A natureza vira
selo na tela: `procedimento_aprovado`, `regra_do_sistema` (o que o código faz, não norma) ou
`a_confirmar`.

Busca local e determinística (sem IA, sem índice externo): pontua as palavras da pergunta
contra título, palavras-chave e corpo, sem acentos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

from .dominio.validacao import normalizar

PASTA = Path(__file__).resolve().parent / "conhecimento"
NATUREZAS = {"procedimento_aprovado": "Procedimento aprovado",
             "regra_do_sistema": "Regra do sistema", "a_confirmar": "A confirmar"}
CAMPOS = ("id", "titulo", "natureza", "publico", "situacao", "versao", "aprovado_por",
          "aprovado_em", "revisar_em", "palavras")
VAZIAS = frozenset([
    "a", "o", "e", "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", "um", "uma",
    "para", "por", "com", "que", "como", "qual", "quais", "meu", "minha", "meus", "minhas",
    "eu", "ja", "ainda", "ou", "se", "ao", "aos", "as", "os"])


class ArtigoInvalido(ValueError):
    pass


@dataclass(frozen=True)
class Bloco:
    tipo: str             # "p" | "lista"
    linhas: tuple[str, ...]


@dataclass(frozen=True)
class Artigo:
    id: str
    slug: str
    titulo: str
    natureza: str
    publico: tuple[str, ...]
    situacao: str
    versao: str
    aprovado_por: str
    aprovado_em: date | None
    revisar_em: date | None
    palavras: tuple[str, ...]
    blocos: tuple[Bloco, ...]

    @property
    def rotulo_natureza(self) -> str:
        return NATUREZAS.get(self.natureza, self.natureza)

    @property
    def resumo(self) -> str:
        return next((b.linhas[0] for b in self.blocos if b.tipo == "p"), "")

    @property
    def referencia(self) -> str:
        return f"{self.id} v{self.versao}"

    def revisao_vencida(self, hoje: date) -> bool:
        return self.revisar_em is not None and self.revisar_em < hoje

    @property
    def texto(self) -> str:
        return "\n".join(" ".join(b.linhas) for b in self.blocos)


def _data(valor: str) -> date | None:
    try:
        return date.fromisoformat(valor.strip())
    except ValueError:
        return None


def ler(caminho: Path) -> Artigo:
    texto = caminho.read_text(encoding="utf-8").replace("\r\n", "\n")
    m =re.match(r"^---\n(.*?)\n---\n(.*)$", texto, re.S)
    if not m:
        raise ArtigoInvalido(f"{caminho.name}: sem cabeçalho.")
    cab: dict[str, str] = {}
    for linha in m.group(1).splitlines():
        chave, _, valor = linha.partition(":")
        cab[chave.strip()] = valor.strip()
    faltam = [c for c in CAMPOS if not cab.get(c)]
    if faltam:
        raise ArtigoInvalido(f"{caminho.name}: faltam {', '.join(faltam)}.")
    if cab["natureza"] not in NATUREZAS:
        raise ArtigoInvalido(f"{caminho.name}: natureza desconhecida.")
    blocos: list[Bloco] = []
    for paragrafo in re.split(r"\n\s*\n", m.group(2).strip()):
        linhas = [x.strip() for x in paragrafo.splitlines() if x.strip()]
        if linhas and all(x.startswith("- ") for x in linhas):
            blocos.append(Bloco("lista", tuple(x[2:].strip() for x in linhas)))
        elif linhas:
            blocos.append(Bloco("p", (" ".join(linhas),)))
    return Artigo(
        id=cab["id"], slug=caminho.stem, titulo=cab["titulo"], natureza=cab["natureza"],
        publico=tuple(p.strip() for p in cab["publico"].split(",") if p.strip()),
        situacao=cab["situacao"], versao=cab["versao"], aprovado_por=cab["aprovado_por"],
        aprovado_em=_data(cab["aprovado_em"]), revisar_em=_data(cab["revisar_em"]),
        palavras=tuple(normalizar(p) for p in cab["palavras"].split(",") if p.strip()),
        blocos=tuple(blocos))


@cache
def todos() -> tuple[Artigo, ...]:
    return tuple(sorted((ler(p) for p in PASTA.glob("*.md")), key=lambda a: a.titulo))


def aprovados(publico: str | None = None) -> list[Artigo]:
    return [a for a in todos() if a.situacao == "aprovado"
            and (publico is None or publico in a.publico)]


def por_slug(slug: str) -> Artigo | None:
    return next((a for a in aprovados() if a.slug == slug), None)


def _termos(texto: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", normalizar(texto))
            if t not in VAZIAS and len(t) > 1]


def pontuar(pergunta: str, artigo: Artigo) -> float:
    termos = _termos(pergunta)
    if not termos:
        return 0.0
    q = " ".join(termos)
    pontos = 0.0
    chaves = 0
    for chave in artigo.palavras:
        if chave and re.search(rf"(?<![a-z0-9]){re.escape(chave)}(?![a-z0-9])", q):
            pontos += 3.0 if " " in chave else 2.0
            chaves += 1
    titulo = set(_termos(artigo.titulo))
    corpo = set(_termos(artigo.texto))
    no_titulo = 0
    for t in set(termos):
        if t in titulo:
            pontos += 1.5
            no_titulo += 1
        elif t in corpo:
            pontos += 0.5
    # Sem nenhuma palavra-chave, só vale com pelo menos dois termos do título: uma palavra
    # comum ("precisa", "quando") não basta para citar um procedimento.
    return pontos if chaves or no_titulo >= 2 else 0.0


def buscar(pergunta: str, publico: str | None = None, limite: int = 5,
           minimo: float = 2.0) -> list[tuple[Artigo, float]]:
    pares = [(a, pontuar(pergunta, a)) for a in aprovados(publico)]
    pares = [(a, p) for a, p in pares if p >= minimo]
    return sorted(pares, key=lambda par: (-par[1], par[0].titulo))[:limite]
