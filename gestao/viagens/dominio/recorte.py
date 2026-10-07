"""Recortes da lista de ofícios — Python puro, sem Django (decisões D1/D2 e D6).

A lista tem duas dimensões que antes se misturavam numa fileira só de abas:

* **tempo da viagem** (as abas, vocabulário canônico do módulo, igual a Roteiros, Termos e
  ao sistema de referência): Todos · Que vão acontecer · Em andamento e realizados ·
  Contas prestadas · Cancelados;
* **situação do documento** (o filtro "Documento", um clique, sempre à vista): Todos ·
  Rascunhos · Emitidos · Arquivados. Arquivado sai de "Todos" até ser pedido.

Aqui moram as regras (em que aba cai um ofício, que documento ele é), os rótulos e a
tradução dos endereços antigos (`?situacao=rascunho`…), que ainda chegam de favoritos,
do painel e de outras telas. A camada de consulta (`queries.py`) traduz as mesmas regras
para o banco; um teste confere que as duas dizem a mesma coisa.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

# ------------------------------------------------------------------ abas (tempo)
TODOS = ""
FUTUROS = "futuros"
ANDAMENTO = "andamento"
PRESTADAS = "prestadas"
CANCELADOS = "cancelados"

ABAS: tuple[tuple[str, str], ...] = (
    (TODOS, "Todos"),
    (FUTUROS, "Que vão acontecer"),
    (ANDAMENTO, "Em andamento e realizados"),
    (PRESTADAS, "Contas prestadas"),
    (CANCELADOS, "Cancelados"),
)
CHAVES_ABAS = frozenset(chave for chave, _ in ABAS)

# ------------------------------------------------------------------ documento
RASCUNHO = "rascunho"
EMITIDO = "emitido"
ARQUIVADO = "arquivado"

DOCUMENTOS: tuple[tuple[str, str], ...] = (
    (TODOS, "Todos"),
    (RASCUNHO, "Rascunhos"),
    (EMITIDO, "Emitidos"),
    (ARQUIVADO, "Arquivados"),
)
CHAVES_DOCUMENTOS = frozenset(chave for chave, _ in DOCUMENTOS)

# ------------------------------------------------------------------ ordem
ORDEM_PADRAO = "-numero"
# Rótulos honestos (P8): "Data de saída (próximas)" começava em 2024 — era "mais antiga
# primeiro". Cada rótulo diz o campo e o sentido, sem prometer o que a ordem não faz.
ORDENS: tuple[tuple[str, str], ...] = (
    ("-numero", "Número, mais recente primeiro"),
    ("numero", "Número, mais antigo primeiro"),
    ("saida", "Saída, mais antiga primeiro"),
    ("-saida", "Saída, mais recente primeiro"),
    ("-criacao", "Data do ofício, mais recente primeiro"),
    ("criacao", "Data do ofício, mais antiga primeiro"),
)
CHAVES_ORDENS = frozenset(chave for chave, _ in ORDENS)


def rotulo(opcoes: tuple[tuple[str, str], ...], chave: str) -> str:
    return next((r for c, r in opcoes if c == chave), "")


# ------------------------------------------------------------------ regras
@dataclass(frozen=True)
class SituacaoDoOficio:
    """O que as regras precisam saber de um ofício (o banco calcula o mesmo em lote)."""

    cancelado: bool
    contas_prestadas: bool          # prestação de todos da equipe finalizada (só emitido)
    primeira_saida: datetime | None
    rascunho: bool = False
    arquivado: bool = False


def aba_do_oficio(oficio: SituacaoDoOficio, fim_de_hoje: datetime) -> str:
    """Em que aba temporal o ofício cai (regra exata da referência, `abas.py:73-85`).

    Cancelado vence tudo; depois, contas prestadas; o resto é pelo dia da 1ª saída:
    depois do fim de hoje **ou sem data** → "Que vão acontecer" (o rascunho que ainda não
    tem roteiro não aconteceu); até o fim de hoje → "Em andamento e realizados"."""
    if oficio.cancelado:
        return CANCELADOS
    if oficio.contas_prestadas:
        return PRESTADAS
    if oficio.primeira_saida is None or oficio.primeira_saida > fim_de_hoje:
        return FUTUROS
    return ANDAMENTO


def documento_do_oficio(oficio: SituacaoDoOficio) -> str:
    """Rascunho, emitido ou arquivado (cancelado não é um documento à parte: mora na aba)."""
    if oficio.arquivado:
        return ARQUIVADO
    if oficio.cancelado:
        return ""
    return RASCUNHO if oficio.rascunho else EMITIDO


def no_recorte(oficio: SituacaoDoOficio, aba: str, documento: str,
               fim_de_hoje: datetime) -> bool:
    """O ofício aparece com esta aba e este documento? Arquivado só com Documento =
    Arquivados; "Todos" de cada dimensão não filtra aquela dimensão."""
    if documento == ARQUIVADO:
        if not oficio.arquivado:
            return False
    elif oficio.arquivado or (documento and documento_do_oficio(oficio) != documento):
        return False
    return not aba or aba_do_oficio(oficio, fim_de_hoje) == aba


# ------------------------------------------------------------------ endereços antigos
# Até o Lote 2 a lista tinha uma fileira só de abas por situação do documento
# (`?situacao=`). Favoritos, o painel, a busca global e outras telas ainda podem mandar
# esses endereços: cada um vira o recorte equivalente no vocabulário novo.
SITUACAO_ANTIGA: dict[str, dict[str, str]] = {
    "rascunho": {"documento": RASCUNHO},
    "emitido": {"documento": EMITIDO},
    "arquivado": {"documento": ARQUIVADO},
    "cancelado": {"aba": CANCELADOS},
    "proximos": {"aba": FUTUROS},       # "Próximas viagens" ≈ "Que vão acontecer"
    "prestadas": {"aba": PRESTADAS},
}


def traduzir_endereco_antigo(parametros: Mapping[str, str]) -> dict[str, str] | None:
    """Parâmetros novos para um endereço com `situacao=` (ou None se não houver).

    O resto do que a pessoa pediu (busca, filtros, ordem, página) segue igual; um
    `situacao` desconhecido simplesmente cai (vira a lista sem esse recorte). Se o
    endereço já trouxer `aba`/`documento`, eles valem sobre a tradução."""
    if "situacao" not in parametros:
        return None
    novos = {chave: valor for chave, valor in parametros.items() if chave != "situacao"}
    for chave, valor in SITUACAO_ANTIGA.get(parametros["situacao"], {}).items():
        novos.setdefault(chave, valor)
    return novos
