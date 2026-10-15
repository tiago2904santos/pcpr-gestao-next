"""Trilha de "Documentos da viagem": os passos da preparação, na ordem, cada documento com o
que a folha da viagem mostra numa linha (título, o chip da situação e um subtexto do que ele
tem) e o que o visualizador (modal) precisa para abri-lo.

Passos: 1 Solicitação (o e-mail ou ofício que pediu o evento, anexado), 2 Roteiro,
3 Ofícios, 4 OS ou plano de trabalho (basta um dos dois) e 5 Termos.

No visualizador, um documento **pronto** (ofício emitido; OS e plano gerados e sem pendência;
termo com período e destino; anexo em PDF ou imagem) abre a folha (o documento como sai) ao
lado do resumo, com as ações. O que ainda não foi gerado, tem pendência ou não gera documento
(roteiro) abre só o resumo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from . import ordens, planos, policies, termos, viagem_solicitacao
from .dominio.escrita import lista_com_e
from .models import (
    AnexoViagem,
    Documento,
    Oficio,
    OrdemServico,
    PlanoTrabalho,
    TermoAutorizacao,
)
from .viagem import Documentos


@dataclass(frozen=True)
class Pagina:
    rotulo: str
    url: str  # a folha (o documento como sai), mostrada no visualizador
    pdf: str = ""  # baixar
    anexar: str = ""  # anexar a via assinada (só quem pode)


@dataclass(frozen=True)
class Chip:
    texto: str
    tom: str = "neutro"  # sucesso | aviso | perigo | neutro (as classes de .selo)


@dataclass
class Item:
    obj: Any
    grupo: str
    titulo: str
    chip: Chip
    subtexto: str
    abrir_url: str
    resumo_url: str = ""
    pronto: bool = False
    paginas: list[Pagina] = field(default_factory=list)
    remover_url: str = ""  # só nos anexos da solicitação
    visualizar: bool = True  # o e-mail (.eml/.msg) não abre no modal: baixa

    @property
    def paginas_json(self) -> str:
        """As folhas para o visualizador (vazio quando não está pronto: abre o resumo)."""
        if not self.pronto or not self.paginas:
            return ""
        return json.dumps([{"rotulo": p.rotulo, "url": p.url, "pdf": p.pdf,
                            "anexar": p.anexar} for p in self.paginas], ensure_ascii=False)


@dataclass(frozen=True)
class Novo:
    tipo: str  # o do formulário "novo-…" (roteiro, oficio, plano, ordem, termo)
    rotulo: str
    precisa_semente: bool = False


@dataclass
class Passo:
    numero: int
    chave: str
    titulo: str
    icone: str
    descricao: str
    vazio: str
    itens: list[Item] = field(default_factory=list)
    novos: list[Novo] = field(default_factory=list)
    anexar: bool = False  # a solicitação: anexa um arquivo em vez de criar documento
    dispensado: bool = False  # OS ou plano sem documento, com a solicitação anexada

    @property
    def feito(self) -> bool:
        return bool(self.itens) or self.dispensado


def _cancelado(obj) -> bool:
    return bool(getattr(obj, "cancelado", False) or getattr(obj, "cancelada", False)
                or getattr(obj, "situacao", "") in ("cancelado", "cancelada"))


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _situacao(obj, gerado: bool, rotulo_gerado: str) -> Chip:
    if _cancelado(obj):
        return Chip("Cancelada" if rotulo_gerado.endswith("a") else "Cancelado", "perigo")
    if gerado:
        return Chip(rotulo_gerado, "sucesso")
    return Chip("Rascunho", "aviso")


def _anexo(a: AnexoViagem) -> Item:
    abrir = reverse("viagens:abrir_solicitacao_viagem", args=[a.pk])
    visivel = viagem_solicitacao.extensao(a.arquivo.name or "") in viagem_solicitacao.VISIVEIS
    quando = timezone.localtime(a.enviado_em).strftime("%d/%m/%Y")
    quem = getattr(a.enviado_por, "nome", "") or str(a.enviado_por)
    return Item(a, "solicitacao", str(a),
                Chip({"email": "E-mail", "oficio": "Ofício"}.get(a.tipo, "Documento")),
                f"Anexado por {quem} em {quando}", abrir, pronto=visivel,
                paginas=[Pagina(str(a), abrir, pdf=f"{abrir}?baixar=1")] if visivel else [],
                remover_url=reverse("viagens:remover_solicitacao_viagem", args=[a.pk]),
                visualizar=visivel)


def _roteiro(r) -> Item:
    usado = [f"no Ofício {o.numero_formatado}" for o in r.oficios.all()]
    if _cancelado(r):
        chip = Chip("Cancelado", "perigo")
    elif r.diarias_total:
        chip = Chip("Diárias calculadas", "sucesso")
    else:
        chip = Chip("Sem diárias", "aviso")
    # O roteiro não gera documento: sempre o resumo.
    return Item(r, "roteiro", str(r), chip,
                f"Usado {lista_com_e(usado)}" if usado else "Ainda não usado em ofício",
                reverse("viagens:editar_roteiro", args=[r.pk]),
                reverse("viagens:resumo_roteiro", args=[r.pk]))


def _pdf_do_oficio(o: Oficio, tipo: str) -> str:
    """O PDF emitido mais recente (a via assinada prevalece no download)."""
    doc = (Documento.objects.filter(oficio=o, tipo=tipo, situacao=Documento.Situacao.PRONTO)
           .order_by("-versao").values_list("pk", flat=True).first())
    return f"{reverse('viagens:baixar_documento', args=[doc])}?baixar=1" if doc else ""


def _oficio(o: Oficio, usuario) -> Item:
    emitido = o.situacao == Oficio.Situacao.EMITIDO
    anexa = usuario is not None and policies.pode_anexar_assinado(usuario, o)
    tipos = [("Ofício", "oficio")]
    if (o.justificativa or "").strip():
        tipos.append(("Justificativa", "justificativa"))
    final = "?final=1" if emitido else ""  # emitido: a folha sem a marca de minuta
    paginas = [Pagina(rotulo, reverse("viagens:folha", args=[o.pk, tipo]) + final,
                      pdf=_pdf_do_oficio(o, tipo) if emitido else "",
                      anexar=reverse("viagens:anexar_assinado", args=[tipo, o.pk])
                      if anexa and emitido else "") for rotulo, tipo in tipos]
    protocolo = o.protocolo_formatado if o.protocolo else ""
    return Item(o, "oficio", str(o), _situacao(o, emitido, "Emitido"),
                f"Protocolo {protocolo}" if protocolo else "Sem protocolo",
                reverse("viagens:editar", args=[o.pk]), reverse("viagens:resumo", args=[o.pk]),
                pronto=emitido, paginas=paginas)


def _plano(p: PlanoTrabalho) -> Item:
    gerado = p.documento_gerado_em is not None or p.situacao == PlanoTrabalho.Situacao.GERADO
    pronto = gerado and not _cancelado(p) and not planos.pendencias(p)
    atividades = p.atividades.count()
    efetivo = p.efetivo.aggregate(total=Sum("quantidade"))["total"] or 0
    return Item(p, "os-plano", str(p), _situacao(p, gerado, "Gerado"),
                f"{_plural(atividades, 'atividade', 'atividades')} · "
                f"{_plural(efetivo, 'pessoa no efetivo', 'pessoas no efetivo')}",
                reverse("viagens:editar_plano", args=[p.pk]),
                reverse("viagens:resumo_plano", args=[p.pk]), pronto=pronto,
                paginas=[Pagina("Plano de trabalho", reverse("viagens:folha_plano", args=[p.pk]),
                                pdf=reverse("viagens:documento_plano", args=[p.pk, "pdf"]))])


def _ordem(o: OrdemServico, usuario) -> Item:
    gerada = o.documento_gerado_em is not None
    pronto = gerada and not _cancelado(o) and not ordens.faltando(o)
    tipo = o.modelo.nome if o.modelo is not None else "OS padrão"
    servidores = o.servidores.count()
    return Item(o, "os-plano", str(o), _situacao(o, gerada, "Gerada"),
                f"{tipo} · {_plural(servidores, 'servidor', 'servidores')}",
                reverse("viagens:editar_ordem", args=[o.pk]),
                reverse("viagens:resumo_ordem", args=[o.pk]), pronto=pronto,
                paginas=[Pagina(
                    "Ordem de serviço", reverse("viagens:folha_ordem", args=[o.pk]),
                    pdf=reverse("viagens:documento_ordem", args=[o.pk, "pdf"]),
                    anexar=reverse("viagens:anexar_assinado", args=["ordem", o.pk])
                    if usuario is not None and policies.pode_editar_ordem(usuario, o) and gerada
                    else "")])


def _termo(t: TermoAutorizacao, usuario) -> Item:
    ef = termos.efetivo(t)
    pronto = bool(ef.inicio and ef.destinos) and not _cancelado(t)
    anexa = usuario is not None and policies.pode_editar_termo(usuario, t)
    paginas = [Pagina(d["titulo"], reverse("viagens:folha_termo", args=[t.pk, d["chave"]]),
                      pdf=reverse("viagens:documento_termo", args=[t.pk, d["chave"], "pdf"]),
                      anexar=reverse("viagens:anexar_assinado_de", args=["termo", t.pk, d["chave"]])
                      if anexa else "")
               for d in termos.documentos_do_termo(t, ef)] if pronto else []
    if _cancelado(t):
        chip = Chip("Cancelado", "perigo")
    else:
        chip = Chip("Pronto", "sucesso") if pronto else Chip("Falta período ou destino", "aviso")
    sub = _plural(len(ef.servidores), "servidor", "servidores")
    if t.oficio is not None:
        sub += f" · pelo Ofício {t.oficio.numero_formatado}"
    return Item(t, "termo", str(t), chip, sub, reverse("viagens:editar_termo", args=[t.pk]),
                reverse("viagens:resumo_termo", args=[t.pk]), pronto=pronto, paginas=paginas)


def trilha(docs: Documentos, anexos=(), usuario=None) -> list[Passo]:
    """`usuario`: quem vê — decide o "Anexar assinado" de cada documento."""
    documentos_da_os = ([_ordem(o, usuario) for o in docs.ordens]
                        + [_plano(p) for p in docs.planos])
    solicitacao = [_anexo(a) for a in anexos]
    return [
        Passo(1, "solicitacao", "Solicitação", "mail",
              "O e-mail do solicitante ou o ofício que pede o evento.",
              "Nenhuma solicitação anexada", solicitacao, anexar=True),
        Passo(2, "roteiro", "Roteiro", "route", "O percurso, os trechos e as diárias.",
              "Nenhum roteiro ainda", [_roteiro(r) for r in docs.roteiros],
              [Novo("roteiro", "Novo roteiro")]),
        Passo(3, "oficio", "Ofícios", "file-text", "A equipe e o pedido de diárias.",
              "Nenhum ofício ainda", [_oficio(o, usuario) for o in docs.oficios],
              [Novo("oficio", "Novo ofício")]),
        Passo(4, "os-plano", "OS ou plano de trabalho", "clipboard-list",
              "Basta um dos dois — e nenhum é preciso quando a solicitação está anexada.",
              "Dispensado: a solicitação está anexada." if solicitacao
              else "Nenhuma OS nem plano ainda", documentos_da_os,
              [Novo("ordem", "Nova OS", True), Novo("plano", "Novo plano", True)],
              dispensado=bool(solicitacao) and not documentos_da_os),
        Passo(5, "termo", "Termos", "file-signature", "As autorizações dos servidores.",
              "Nenhum termo ainda", [_termo(t, usuario) for t in docs.termos],
              [Novo("termo", "Novo termo", True)]),
    ]
