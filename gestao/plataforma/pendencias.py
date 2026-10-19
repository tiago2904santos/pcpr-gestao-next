"""Pendências do operador (aba "Pendências" da Agenda): o que está esperando uma pessoa —
envios aos servidores, documentos em rascunho, prestação de contas vencendo, solicitações
a despachar. A plataforma não conhece os módulos: cada contexto registra a sua seção
(`registrar_secao`, no `ready` do app) com a permissão dele, e devolve grupos já ordenados
por urgência, cada item com o endereço da tela que resolve. Mesmo desenho da agenda, da
busca e do menu.

Cada seção lê só o que a pessoa vê nas telas de origem (as `policies` do contexto) e em
poucas consultas: a contagem é do recorte inteiro; os itens, os primeiros `LIMITE`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from django.db.models import Case, F, IntegerField, QuerySet, When

logger = logging.getLogger(__name__)

LIMITE = 20  # itens carregados por grupo; o resto fica no "Ver todos" da tela de origem
VISIVEIS = 5  # itens à vista por grupo na visão geral; os demais em "Mostrar mais"


@dataclass(frozen=True)
class Item:
    """Uma pendência: o que é (placa + título), os fatos e o botão do que se faz ao chegar."""

    chave: str
    titulo: str
    url: str
    acao: str
    rotulo: str = ""  # a placa ("Ofício", "OS", "Servidor"…)
    numero: str = ""
    fatos: tuple[tuple[str, str], ...] = ()  # (ícone, texto)
    selo: str = ""
    tom: str = "neutro"  # neutro | info | sucesso | aviso | perigo


@dataclass(frozen=True)
class Acao:
    """Ação da seção inteira (ex.: "Atualizar pendências"). `post`: formulário com CSRF."""

    rotulo: str
    url: str
    icone: str = ""
    post: bool = False
    contagem: int | None = None  # atalho para um recorte da lista ("Sem comprovante · 4")


@dataclass
class Grupo:
    chave: str
    titulo: str
    total: int
    itens: list[Item] = field(default_factory=list)
    ajuda: str = ""
    ver_todos: str = ""  # a lista de origem com o mesmo recorte

    @property
    def primeiros(self) -> list[Item]:
        return self.itens[:VISIVEIS]

    @property
    def demais(self) -> list[Item]:
        return self.itens[VISIVEIS:]

    @property
    def faltam(self) -> int:
        """Quantos não couberam no limite (estão só na tela de origem)."""
        return max(self.total - len(self.itens), 0)


@dataclass(frozen=True)
class Secao:
    slug: str
    titulo: str
    icone: str
    descricao: str
    pode: Callable[[object], bool]
    grupos: Callable[[object, date], list[Grupo]]
    acoes: Callable[[object], list[Acao]] = lambda usuario: []
    vazio: str = "Nada pendente."
    ordem: int = 100


@dataclass
class Montada:
    secao: Secao
    grupos: list[Grupo]
    acoes: list[Acao]
    erro: bool = False

    @property
    def total(self) -> int:
        return sum(g.total for g in self.grupos)


_SECOES: list[Secao] = []


def registrar_secao(secao: Secao) -> None:
    if all(s.slug != secao.slug for s in _SECOES):
        _SECOES.append(secao)
        _SECOES.sort(key=lambda s: (s.ordem, s.titulo))


def secoes_de(usuario) -> list[Secao]:
    """As seções que esta pessoa pode ver — as abas da tela."""
    return [s for s in _SECOES if s.pode(usuario)]


def montar(usuario, hoje: date) -> list[Montada]:
    """Todas as seções visíveis, com os grupos que têm algo. A falha de uma seção vira
    aviso nela (e log), sem derrubar as outras."""
    saida = []
    for secao in secoes_de(usuario):
        try:
            grupos = [g for g in secao.grupos(usuario, hoje) if g.total]
            saida.append(Montada(secao, grupos, secao.acoes(usuario)))
        except Exception:
            logger.exception("Pendências: a seção %s falhou.", secao.slug)
            saida.append(Montada(secao, [], [], erro=True))
    return saida


# ---------------------------------------------------------------- ajudas para as seções
def carregar(qs: QuerySet) -> tuple[list, int]:
    """Os primeiros `LIMITE` e o total — a contagem só vai ao banco quando o limite enche."""
    linhas = list(qs[:LIMITE])
    return linhas, (len(linhas) if len(linhas) < LIMITE else qs.order_by().count())


def por_urgencia(qs: QuerySet, campo: str, desde) -> QuerySet:
    """O que começa de `desde` em diante, o mais perto primeiro; depois os sem data; por
    último os que já passaram, os mais recentes primeiro."""
    faixa = Case(When(**{f"{campo}__gte": desde}, then=0),
                 When(**{f"{campo}__isnull": True}, then=1), default=2,
                 output_field=IntegerField())
    futuro = Case(When(**{f"{campo}__gte": desde}, then=F(campo)), default=None)
    return qs.annotate(_faixa=faixa).order_by("_faixa", futuro.asc(nulls_last=True),
                                              F(campo).desc(nulls_last=True), "-pk")
