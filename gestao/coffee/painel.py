"""Números e alertas do painel do Coffee Break (CB6a; paridade com `coffee_break/views.py`
§8.2): capacidade, consumo e saldo dos lotes ativos, gasto do ano, pendências financeiras,
alerta de saldo (projeção pelo ritmo), vigência dos contratos, certidões e "O que fazer
hoje". Os lotes ativos e os saldos são lidos uma vez para o painel inteiro."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import Max, Q, Sum
from django.db.models.functions import Coalesce, ExtractMonth, ExtractYear
from django.urls import reverse

from . import certidoes, dominio_pedido, queries
from . import dominio_painel as regras
from .models import Lote, Solicitacao


@dataclass
class Indicadores:
    capacidade: int
    consumido: int
    lotes_ativos: int
    ano: int
    gasto: Decimal
    pago: Decimal
    pendencias: int

    @property
    def restante(self) -> int:
        return self.capacidade - self.consumido

    @property
    def percentual(self) -> int:
        return dominio_pedido.percentual_consumido(self.consumido, self.capacidade)


def _gasto_do_ano(ano: int) -> tuple[Decimal, Decimal]:
    """Σ valor das OS não canceladas com evento no ano (ou pedido, sem data de evento) e a
    parte com ordem bancária. O valor é arredondado por OS, como na tela da OS."""
    gasto = pago = Decimal("0")
    linhas = (Solicitacao.objects.filter(cancelada=False)
              .filter(Q(data_evento__year=ano) | Q(data_evento__isnull=True,
                                                   data_solicitacao__year=ano))
              .values_list("quantidade", "quantidade_faturada", "valor_unitario",
                           "ordem_bancaria_em"))
    for pedida, faturada, unitario, ob in linhas:
        v = dominio_pedido.valor(dominio_pedido.quantidade_efetiva(pedida, faturada), unitario)
        if v is None:
            continue
        gasto += v
        if ob:
            pago += v
    return gasto, pago


def consumo_mensal(lotes: list[int]) -> dict[int, dict[tuple[int, int], int]]:
    """Por lote, a quantidade efetiva por mês do evento (ou do pedido, sem data de evento)."""
    mes = Coalesce("data_evento", "data_solicitacao")
    linhas = (Solicitacao.objects.filter(lote__in=lotes, cancelada=False)
              .annotate(a=ExtractYear(mes), m=ExtractMonth(mes))
              .values_list("lote", "a", "m")
              .annotate(n=Sum(Coalesce("quantidade_faturada", "quantidade"))).order_by())
    saida: dict[int, dict[tuple[int, int], int]] = defaultdict(dict)
    for lote, a, m, n in linhas:
        saida[lote][(a, m)] = n or 0
    return saida


MOSTRAR_POR_GRUPO = 5


@dataclass
class LoteAtivo:
    lote: Lote
    saldo: queries.Saldo
    fim: date | None
    alerta: str = ""


@dataclass
class Grupo:
    chave: str
    titulo: str
    ajuda: str
    botao: str
    ancora: str
    itens: list = field(default_factory=list)

    @property
    def primeiros(self) -> list:
        return self.itens[:MOSTRAR_POR_GRUPO]

    @property
    def demais(self) -> list:
        return self.itens[MOSTRAR_POR_GRUPO:]


@dataclass
class Painel:
    indicadores: Indicadores
    lotes: list[LoteAtivo]
    vigencia: list[tuple[str, str, str, str]]  # (contrato, texto, tom, url)
    certidoes: list[tuple[object, list]]
    grupos: list[Grupo]

    @property
    def pedem_acao(self) -> int:
        return sum(len(g.itens) for g in self.grupos)

    @property
    def alertas_de_saldo(self) -> list[LoteAtivo]:
        return [la for la in self.lotes if la.alerta]


def _lotes_ativos(hoje: date) -> list[LoteAtivo]:
    lotes = queries.lotes_ativos()
    sal = queries.saldos(lotes)
    consumo = consumo_mensal([lote.pk for lote in lotes])
    saida = []
    for lote in lotes:
        s = sal[lote.pk]
        fim = lote.contrato.fim_efetivo()
        alerta = regras.alerta_de_saldo(s.restante, s.total,
                                        regras.ritmo(consumo.get(lote.pk, {}), hoje), fim, hoje)
        saida.append(LoteAtivo(lote, s, fim, alerta.texto if alerta else ""))
    return saida


def _vigencia(lotes: list[LoteAtivo], hoje: date) -> list[tuple[str, str, str, str]]:
    """Contratos com lote ativo que vencem em até 90 dias ou já venceram."""
    vistos: set[int] = set()
    saida = []
    for la in lotes:
        c = la.lote.contrato
        if c.pk in vistos:
            continue
        vistos.add(c.pk)
        if la.fim and (texto := regras.alerta_de_vigencia(la.fim, hoje)):
            tom = "perigo" if (la.fim - hoje).days <= regras.FAIXAS_VIGENCIA[0] else "aviso"
            saida.append((f"Contrato {c.numero} · {c.fornecedor}", texto, tom,
                          reverse("coffee:cadastros", args=["aditivos"])))
    return saida


def _certidoes(hoje: date) -> list[tuple[object, list]]:
    """Por fornecedor com lote ativo, as certidões que não estão vigentes."""
    saida = []
    for f in certidoes.fornecedores_com_lote_ativo():
        ruins = [linha for linha in certidoes.quadro(f, hoje) if linha.situacao != "vigente"]
        if ruins:
            saida.append((f, ruins))
    return saida


def _botao(g: Grupo, s: Solicitacao, hoje: date) -> tuple[str, str]:
    """(rótulo, seção da folha): o que a pessoa vai fazer ao chegar."""
    if g.chave == "entregas" and s.data_evento == hoje:
        return "Registrar a entrega", "entregas"
    if g.chave == "sem_ob" and s.atesto_em:
        return "Anexar a OB", "pdfs"
    return g.botao, g.ancora


def o_que_fazer(hoje: date) -> list[Grupo]:
    """As OS que dependem da equipe, em grupos na ordem do fluxo."""
    grupos = {c: Grupo(c, t, a, b, n) for c, t, a, b, n in regras.GRUPOS}
    abertas = (Solicitacao.objects.filter(cancelada=False, envio_empresa_em__isnull=True)
               .select_related("municipio", "lote__contrato__fornecedor")
               .annotate(ultimo=Max("movimentos__em")))
    for s in abertas:
        chave = regras.grupo_de(cancelada=False, concluida=False, data_evento=s.data_evento,
                                nota=bool(s.nota_fiscal), oficio=bool(s.numero_oficio),
                                protocolo=bool(s.protocolo_pagamento),
                                ob=bool(s.ordem_bancaria_em), hoje=hoje)
        if chave is None:
            continue
        ultimo = (s.ultimo or s.criado_em).date()
        dias = regras.dias_parada(ultimo, s.data_evento if chave != "entregas" else None, hoje)
        grupos[chave].itens.append((s, dias, *_botao(grupos[chave], s, hoje)))
    for g in grupos.values():
        if g.chave == "entregas":
            g.itens.sort(key=lambda t: (t[0].data_evento, t[0].horario is None,
                                        t[0].horario or t[0].criado_em.time()))
        else:
            g.itens.sort(key=lambda t: (-t[1], t[0].pk))
    return [g for g in grupos.values() if g.itens]


def montar(hoje: date) -> Painel:
    lotes = _lotes_ativos(hoje)
    gasto, pago = _gasto_do_ano(hoje.year)
    ind = Indicadores(sum(la.saldo.total for la in lotes),
                      sum(la.saldo.consumido for la in lotes), len(lotes), hoje.year, gasto,
                      pago, Solicitacao.objects.filter(queries.PENDENTES).count())
    return Painel(ind, lotes, _vigencia(lotes, hoje), _certidoes(hoje), o_que_fazer(hoje))
