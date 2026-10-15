"""Trilha de "Documentos da viagem": os cinco tipos na ordem da preparação, cada documento
com o que a folha da viagem precisa para mostrá-lo no visualizador (modal).

No visualizador, um documento **pronto** (ofício emitido; OS e plano gerados e sem pendência;
termo com período e destino) abre a folha dele — o documento como sai — ao lado do resumo,
com as ações. O que ainda não foi gerado, tem pendência ou não gera documento (roteiro) abre
só o resumo. As páginas são as folhas de um documento (ofício e justificativa; os termos de
cada servidor, o genérico e o da viatura).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from django.urls import reverse

from . import ordens, planos, termos
from .models import Oficio, OrdemServico, PlanoTrabalho, TermoAutorizacao
from .viagem import Documentos


@dataclass(frozen=True)
class Pagina:
    rotulo: str
    url: str


@dataclass
class Item:
    obj: Any
    titulo: str
    abrir_url: str
    resumo_url: str
    estado: str  # ok | rascunho | cancelado | neutro (a cor da folhinha)
    pronto: bool = False
    paginas: list[Pagina] = field(default_factory=list)

    @property
    def paginas_json(self) -> str:
        """As folhas para o visualizador (vazio quando não está pronto: abre o resumo)."""
        if not self.pronto or not self.paginas:
            return ""
        return json.dumps([{"rotulo": p.rotulo, "url": p.url} for p in self.paginas],
                          ensure_ascii=False)


@dataclass
class Passo:
    numero: int
    tipo: str  # o do formulário "novo-…" (roteiro, oficio, plano, ordem, termo)
    titulo: str
    icone: str
    rotulo_novo: str
    vazio: str
    precisa_semente: bool
    itens: list[Item] = field(default_factory=list)


def _cancelado(obj) -> bool:
    return bool(getattr(obj, "cancelado", False) or getattr(obj, "cancelada", False)
                or getattr(obj, "situacao", "") in ("cancelado", "cancelada"))


def _estado(obj, gerado: bool) -> str:
    if _cancelado(obj):
        return "cancelado"
    if gerado:
        return "ok"
    return "rascunho" if getattr(obj, "situacao", "") == "rascunho" else "neutro"


def _oficio(o: Oficio) -> Item:
    emitido = o.situacao == Oficio.Situacao.EMITIDO
    paginas = [Pagina("Ofício", reverse("viagens:folha", args=[o.pk, "oficio"]))]
    if (o.justificativa or "").strip():
        paginas.append(Pagina("Justificativa",
                              reverse("viagens:folha", args=[o.pk, "justificativa"])))
    return Item(o, str(o), reverse("viagens:editar", args=[o.pk]),
                reverse("viagens:resumo", args=[o.pk]), _estado(o, emitido),
                pronto=emitido, paginas=paginas)


def _ordem(o: OrdemServico) -> Item:
    gerada = o.documento_gerado_em is not None
    pronto = gerada and not _cancelado(o) and not ordens.faltando(o)
    return Item(o, str(o), reverse("viagens:editar_ordem", args=[o.pk]),
                reverse("viagens:resumo_ordem", args=[o.pk]), _estado(o, gerada),
                pronto=pronto,
                paginas=[Pagina("Ordem de serviço", reverse("viagens:folha_ordem", args=[o.pk]))])


def _plano(p: PlanoTrabalho) -> Item:
    gerado = p.documento_gerado_em is not None or p.situacao == PlanoTrabalho.Situacao.GERADO
    pronto = gerado and not _cancelado(p) and not planos.pendencias(p)
    return Item(p, str(p), reverse("viagens:editar_plano", args=[p.pk]),
                reverse("viagens:resumo_plano", args=[p.pk]), _estado(p, gerado),
                pronto=pronto,
                paginas=[Pagina("Plano de trabalho", reverse("viagens:folha_plano", args=[p.pk]))])


def _termo(t: TermoAutorizacao) -> Item:
    ef = termos.efetivo(t)
    pronto = bool(ef.inicio and ef.destinos) and not _cancelado(t)
    paginas = [Pagina(d["titulo"], reverse("viagens:folha_termo", args=[t.pk, d["chave"]]))
               for d in termos.documentos_do_termo(t, ef)] if pronto else []
    return Item(t, str(t), reverse("viagens:editar_termo", args=[t.pk]),
                reverse("viagens:resumo_termo", args=[t.pk]), _estado(t, pronto),
                pronto=pronto, paginas=paginas)


def _roteiro(r) -> Item:
    # O roteiro não gera documento: sempre o resumo.
    return Item(r, str(r), reverse("viagens:editar_roteiro", args=[r.pk]),
                reverse("viagens:resumo_roteiro", args=[r.pk]), _estado(r, False))


def trilha(docs: Documentos) -> list[Passo]:
    return [
        Passo(1, "roteiro", "Roteiro", "route", "Novo roteiro", "Nenhum roteiro ainda", False,
              [_roteiro(r) for r in docs.roteiros]),
        Passo(2, "oficio", "Ofícios", "file-text", "Novo ofício", "Nenhum ofício ainda", False,
              [_oficio(o) for o in docs.oficios]),
        Passo(3, "plano", "Plano", "list-checks", "Novo plano", "Nenhum plano ainda", True,
              [_plano(p) for p in docs.planos]),
        Passo(4, "ordem", "OS", "clipboard-list", "Nova OS", "Nenhuma OS ainda", True,
              [_ordem(o) for o in docs.ordens]),
        Passo(5, "termo", "Termos", "file-signature", "Novo termo", "Nenhum termo ainda", True,
              [_termo(t) for t in docs.termos]),
    ]
