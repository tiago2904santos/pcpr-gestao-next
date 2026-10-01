"""Consultas de leitura do módulo Viagens (listas, contagens, tabelas vigentes)."""

from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Count, Min, Prefetch, Q, QuerySet
from django.utils import timezone

from gestao.cadastros.models import TabelaDiaria

from .dominio.diarias import Faixa, ValorVigente
from .models import Oficio, Trecho, Viajante


def buscar_tabelas_vigentes(data_referencia: date) -> dict[Faixa, ValorVigente]:
    """Vigência mais recente de cada faixa com início ≤ data de referência."""
    vigentes: dict[Faixa, ValorVigente] = {}
    linhas = (TabelaDiaria.objects.filter(vigente_desde__lte=data_referencia)
              .order_by("faixa", "-vigente_desde"))
    for linha in linhas:
        faixa = Faixa(linha.faixa)
        if faixa not in vigentes:
            vigentes[faixa] = ValorVigente(faixa, linha.valor_24h, linha.vigente_desde,
                                           f"tabeladiaria:{linha.pk}")
    return vigentes


def com_dados_de_lista(qs: QuerySet[Oficio]) -> QuerySet[Oficio]:
    """Tudo que a lista de ofícios exibe, em número fixo de consultas."""
    return (
        qs.select_related("unidade", "viatura", "viatura__combustivel", "sede")
        .prefetch_related(
            Prefetch("viajantes", queryset=Viajante.objects.select_related("servidor")),
            Prefetch("trechos", queryset=Trecho.objects.select_related("origem", "destino")
                     .order_by("ordem")),
        )
        .annotate(primeira_saida=Min("trechos__saida_em"))
    )


FILTROS_SITUACAO = {
    "rascunho": ("Rascunhos", Q(situacao=Oficio.Situacao.RASCUNHO)),
    "emitido": ("Emitidos", Q(situacao=Oficio.Situacao.EMITIDO)),
    "proximos": ("Próximas viagens", Q(situacao__in=["rascunho", "emitido"])),
    "cancelado": ("Cancelados", Q(situacao=Oficio.Situacao.CANCELADO)),
}


def contagens(qs: QuerySet[Oficio]) -> dict[str, int]:
    agora = timezone.now()
    proximos = qs.filter(FILTROS_SITUACAO["proximos"][1], trechos__ordem=1,
                         trechos__saida_em__gte=agora)
    resultado = qs.aggregate(
        todos=Count("pk"),
        rascunho=Count("pk", filter=FILTROS_SITUACAO["rascunho"][1]),
        emitido=Count("pk", filter=FILTROS_SITUACAO["emitido"][1]),
        cancelado=Count("pk", filter=FILTROS_SITUACAO["cancelado"][1]),
    )
    resultado["proximos"] = proximos.count()
    return resultado


def aplicar_filtro_situacao(qs: QuerySet[Oficio], chave: str | None) -> QuerySet[Oficio]:
    if not chave or chave not in FILTROS_SITUACAO:
        return qs
    qs = qs.filter(FILTROS_SITUACAO[chave][1])
    if chave == "proximos":
        qs = qs.filter(trechos__ordem=1, trechos__saida_em__gte=timezone.now())
    return qs


def indicadores_do_painel(qs: QuerySet[Oficio]) -> dict[str, object]:
    hoje = timezone.localdate()
    inicio_mes = hoje.replace(day=1)
    em_30 = timezone.now() + timedelta(days=30)
    return {
        "oficios_mes": qs.filter(data_oficio__gte=inicio_mes).exclude(
            situacao=Oficio.Situacao.CANCELADO).count(),
        "rascunhos": qs.filter(situacao=Oficio.Situacao.RASCUNHO).count(),
        "viagens_30_dias": qs.exclude(situacao=Oficio.Situacao.CANCELADO).filter(
            trechos__ordem=1, trechos__saida_em__gte=timezone.now(),
            trechos__saida_em__lte=em_30).count(),
        "diarias_mes": sum(
            (o.diarias_total for o in qs.filter(situacao=Oficio.Situacao.EMITIDO,
                                                 emitido_em__date__gte=inicio_mes)
             .only("diarias_total")),
            start=0,
        ),
    }
