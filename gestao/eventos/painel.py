"""Números do painel de Eventos Sociais (paridade com `dashboard/views.py` da referência),
sempre sobre as solicitações que a pessoa vê: no mês (vs. mês anterior), aguardando
despacho, deferidas no ano (atendidas e % das decididas), eventos nos próximos 30 dias
(com unidade móvel), a série mensal e o despacho da DG (tempo médio do envio à decisão e
as decisões do ano)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.db.models import Count, F, Min, Q, QuerySet
from django.db.models.functions import ExtractMonth, ExtractYear

from . import dominio, policies
from .models import Movimento, Solicitacao

NOMES_DOS_MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                   "agosto", "setembro", "outubro", "novembro", "dezembro")
ABREVIADOS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov",
              "dez")
PERIODOS = (6, 12, 24)
DEFERIDOS = (dominio.DEFERIDA, dominio.ATENDIDA)
FORA_DA_AGENDA = (dominio.CANCELADA, dominio.NAO_ATENDIDA)


@dataclass
class Resumo:
    no_mes: int
    no_mes_anterior: int
    aguardando: int
    deferidas_ano: int
    atendidas_ano: int
    decididas_ano: int
    proximos: int
    proximos_unidade_movel: int

    @property
    def diferenca(self) -> int:
        return self.no_mes - self.no_mes_anterior

    @property
    def percentual(self) -> int:
        return round(self.deferidas_ano * 100 / self.decididas_ano) if self.decididas_ano else 0


def proximos(qs: QuerySet[Solicitacao], hoje: date) -> QuerySet[Solicitacao]:
    return qs.filter(data_inicio_evento__gte=hoje,
                     data_inicio_evento__lte=hoje + timedelta(days=30)).exclude(
        status__in=FORA_DA_AGENDA)


def resumo(usuario, hoje: date) -> Resumo:
    """Os quatro indicadores numa consulta só."""
    inicio = hoje.replace(day=1)
    anterior = (inicio - timedelta(days=1)).replace(day=1)
    fim_30 = hoje + timedelta(days=30)
    ano = Q(data_solicitacao__year=hoje.year)
    prox = (Q(data_inicio_evento__gte=hoje, data_inicio_evento__lte=fim_30)
            & ~Q(status__in=FORA_DA_AGENDA))
    n = policies.solicitacoes_visiveis(usuario).aggregate(
        no_mes=Count("pk", filter=Q(data_solicitacao__gte=inicio)),
        no_mes_anterior=Count("pk", filter=Q(data_solicitacao__gte=anterior,
                                              data_solicitacao__lt=inicio)),
        aguardando=Count("pk", filter=Q(status=dominio.AGUARDANDO)),
        deferidas_ano=Count("pk", filter=ano & Q(status__in=DEFERIDOS)),
        atendidas_ano=Count("pk", filter=ano & Q(status=dominio.ATENDIDA)),
        decididas_ano=Count("pk", filter=ano & Q(status__in=(*DEFERIDOS,
                                                             dominio.NAO_ATENDIDA))),
        proximos=Count("pk", filter=prox),
        proximos_unidade_movel=Count("pk", filter=prox & Q(unidade_movel=True)))
    return Resumo(**n)


def meses_recentes(hoje: date, quantos: int) -> list[date]:
    marcos: list[date] = []
    primeiro = hoje.replace(day=1)
    for _ in range(quantos):
        marcos.append(primeiro)
        primeiro = (primeiro - timedelta(days=1)).replace(day=1)
    marcos.reverse()
    return marcos


def serie_mensal(usuario, hoje: date, meses: int = 12) -> list[dict[str, Any]]:
    """Solicitações por mês (data da solicitação), com as alturas para o gráfico."""
    marcos = meses_recentes(hoje, meses)
    contagens = {(a, m): n for a, m, n in
                 policies.solicitacoes_visiveis(usuario)
                 .filter(data_solicitacao__gte=marcos[0])
                 .annotate(a=ExtractYear("data_solicitacao"),
                           m=ExtractMonth("data_solicitacao"))
                 .values_list("a", "m").annotate(n=Count("pk")).order_by()}
    barras = [{"rotulo": f"{ABREVIADOS[d.month - 1]}/{d:%y}",
               "titulo": f"{NOMES_DOS_MESES[d.month - 1]} de {d.year}",
               "valor": contagens.get((d.year, d.month), 0)} for d in marcos]
    maximo = max((b["valor"] for b in barras), default=0) or 1
    for b in barras:
        b["altura"] = round(b["valor"] * 100 / maximo)
        b["topo"] = 100 - b["altura"]  # y da barra no SVG (viewBox de 100 de altura)
    return barras


@dataclass
class Despacho:
    media_dias: float | None
    decididas: int
    pendentes: int
    atender: int
    nao_atender: int
    cancelados: int
    ano: int


def despacho(usuario, hoje: date, pendentes: int) -> Despacho:
    """Tempo médio entre o primeiro envio e a primeira decisão (como a referência) e as
    decisões do ano."""
    visiveis = policies.solicitacoes_visiveis(usuario)
    marcos = (Movimento.objects.filter(solicitacao__in=visiveis.values("pk"))
              .values("solicitacao_id")
              .annotate(enviado=Min("em", filter=Q(acao=Movimento.Acao.ENVIO)),
                        decidido=Min("em", filter=Q(acao=Movimento.Acao.DECISAO)))
              .filter(enviado__isnull=False, decidido__isnull=False,
                      decidido__gte=F("enviado")).order_by())
    dias = [(m["decidido"] - m["enviado"]).total_seconds() / 86400 for m in marcos]
    por_decisao = dict(visiveis.filter(data_solicitacao__year=hoje.year)
                       .values_list("decisao_dg").annotate(n=Count("pk")).order_by())
    return Despacho(media_dias=round(sum(dias) / len(dias), 1) if dias else None,
                    decididas=len(dias), pendentes=pendentes,
                    atender=por_decisao.get("atender", 0),
                    nao_atender=por_decisao.get("nao_atender", 0),
                    cancelados=por_decisao.get("cancelado", 0), ano=hoje.year)
