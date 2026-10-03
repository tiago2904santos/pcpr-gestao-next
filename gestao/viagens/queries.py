"""Consultas de leitura do módulo Viagens (listas, contagens, tabelas vigentes)."""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib.postgres.aggregates import ArrayAgg
from django.db import models
from django.db.models import (
    Count,
    DateField,
    Exists,
    ExpressionWrapper,
    F,
    Max,
    Min,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Value,
    prefetch_related_objects,
)
from django.db.models.functions import Coalesce, Concat, TruncDate
from django.utils import timezone

from gestao.cadastros.models import TabelaDiaria

from .dominio import busca
from .dominio.diarias import Faixa, ValorVigente
from .models import Oficio, Roteiro, Trecho, TrechoRoteiro, Viajante


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


# Trechos e equipe de um ofício são lidos por várias regras na mesma requisição
# (diárias, prazo, assunto, prontidão, conflitos, documento): carregados uma vez só.
TRECHOS = Prefetch("trechos", queryset=Trecho.objects.select_related("origem", "destino"))
# As viaturas que cada um costuma dirigir entram junto: a equipe mostra e a viatura sugere.
VIAJANTES = Prefetch("viajantes", queryset=Viajante.objects.select_related(
    "servidor__cargo", "servidor__unidade").prefetch_related("servidor__viaturas_que_dirige"))


def trechos_de(oficio: Oficio) -> list[Trecho]:
    """Trechos em ordem, do cache da requisição (carrega na primeira chamada)."""
    prefetch_related_objects([oficio], TRECHOS)
    return list(oficio.trechos.all())


def viajantes_de(oficio: Oficio) -> list[Viajante]:
    """Equipe em ordem, do cache da requisição (carrega na primeira chamada)."""
    prefetch_related_objects([oficio], VIAJANTES)
    return list(oficio.viajantes.all())


def com_dados_de_lista(qs: QuerySet[Oficio]) -> QuerySet[Oficio]:
    """Tudo que a lista de ofícios exibe, em número fixo de consultas."""
    return (
        qs.select_related("unidade__configuracao", "viatura", "viatura__combustivel", "sede")
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
    # D1: arquivados saem de todas as outras abas e moram só aqui.
    "arquivado": ("Arquivados", Q(arquivado_em__isnull=False)),
}
NAO_ARQUIVADO = Q(arquivado_em__isnull=True)


def contagens(qs: QuerySet[Oficio]) -> dict[str, int]:
    agora = timezone.now()
    proximos = qs.filter(FILTROS_SITUACAO["proximos"][1], NAO_ARQUIVADO, trechos__ordem=1,
                         trechos__saida_em__gte=agora)
    resultado = qs.aggregate(
        todos=Count("pk", filter=NAO_ARQUIVADO),
        rascunho=Count("pk", filter=FILTROS_SITUACAO["rascunho"][1] & NAO_ARQUIVADO),
        emitido=Count("pk", filter=FILTROS_SITUACAO["emitido"][1] & NAO_ARQUIVADO),
        cancelado=Count("pk", filter=FILTROS_SITUACAO["cancelado"][1] & NAO_ARQUIVADO),
        arquivado=Count("pk", filter=FILTROS_SITUACAO["arquivado"][1]),
    )
    resultado["proximos"] = proximos.count()
    return resultado


def filtro_de_leitura(leitura: busca.Leitura) -> Q:
    """O Q de cada leitura do termo (dominio.busca diz quais existem)."""
    termo = leitura.termo
    if leitura.escopo == busca.NUMERO_ESCOPO:
        numero, ano = termo.split("/")
        return Q(numero=int(numero), ano=int(ano))
    if leitura.escopo == busca.PROTOCOLO:
        return Q(protocolo__contains=termo)
    if leitura.escopo == busca.PLACA_ESCOPO:
        placa = termo.replace("-", "").replace(" ", "").upper()
        return Q(viatura__placa__icontains=placa) | Q(transporte_placa__icontains=placa)
    if leitura.escopo == busca.DESTINO:
        return Q(trechos__destino__nome__unaccent__icontains=termo)
    return Q(viajantes__servidor__nome__unaccent__icontains=termo)


# Leituras que juntam tabelas: filtrar por elas repete o ofício uma vez por linha casada.
_COM_JUNCAO = {busca.DESTINO, busca.SERVIDOR}


def aplicar_leitura(qs: QuerySet[Oficio], leitura: busca.Leitura) -> QuerySet[Oficio]:
    filtrado = qs.filter(filtro_de_leitura(leitura))
    return filtrado.distinct() if leitura.escopo in _COM_JUNCAO else filtrado


def contar_leituras(qs: QuerySet[Oficio], leituras: list[busca.Leitura]) -> dict[str, int]:
    """Quantos ofícios cada leitura traria — numa consulta só, para a tela poder dizer
    "Ofício 26/2026 (1)" e "Protocolo com 26 (12)" antes de a pessoa escolher."""
    if not leituras:
        return {}
    return qs.aggregate(**{
        leitura.escopo: Count("pk", filter=filtro_de_leitura(leitura), distinct=True)
        for leitura in leituras
    })


# Categorias de veículo que a frota não guarda em campo próprio: o que as distingue hoje
# é o modelo da viatura ou a descrição do transporte ("Ônibus de linha", "Unidade Móvel").
PALAVRAS_DE_VEICULO = {
    "unidade_movel": ("unidade móvel", "unidade movel"),
    "onibus": ("ônibus", "onibus"),
    "caminhao": ("caminhão", "caminhao"),
    "van": ("van",),
}


def _filtro_de_veiculo(chave: str) -> Q:
    if chave in ("caracterizada", "descaracterizada"):
        return Q(viatura__tipo=chave)
    if chave == "sem":
        return Q(viatura__isnull=True, transporte_descricao="")
    filtro = Q()
    for palavra in PALAVRAS_DE_VEICULO.get(chave, ()):
        filtro |= (Q(viatura__modelo__unaccent__icontains=palavra)
                   | Q(transporte_descricao__unaccent__icontains=palavra))
    return filtro


def aplicar_filtros_avancados(qs: QuerySet[Oficio], filtros: dict) -> QuerySet[Oficio]:
    """Filtros da gaveta "Mais filtros" (forms.FiltrosOficio já validado). Chave ausente ou
    vazia não filtra nada."""
    de, ate = filtros.get("saida_de"), filtros.get("saida_ate")
    if de or ate:
        # Tudo na mesma chamada: é o mesmo trecho (a ida) que tem de cair no período.
        periodo = Q(trechos__ordem=1)
        if de:
            periodo &= Q(trechos__saida_em__date__gte=de)
        if ate:
            periodo &= Q(trechos__saida_em__date__lte=ate)
        qs = qs.filter(periodo)
    if filtros.get("criacao_de"):
        qs = qs.filter(data_oficio__gte=filtros["criacao_de"])
    if filtros.get("criacao_ate"):
        qs = qs.filter(data_oficio__lte=filtros["criacao_ate"])
    protocolo = "".join(c for c in (filtros.get("protocolo") or "") if c.isdigit())
    if protocolo:
        qs = qs.filter(protocolo__contains=protocolo)
    if filtros.get("veiculo"):
        qs = qs.filter(_filtro_de_veiculo(filtros["veiculo"]))
    if filtros.get("diarias_de") is not None:
        qs = qs.filter(diarias_total__gte=filtros["diarias_de"])
    if filtros.get("diarias_ate") is not None:
        qs = qs.filter(diarias_total__lte=filtros["diarias_ate"])
    # Juntar com trechos repete o ofício uma vez por linha casada.
    return qs.distinct() if (de or ate) else qs


def aplicar_filtro_situacao(qs: QuerySet[Oficio], chave: str | None) -> QuerySet[Oficio]:
    if chave == "arquivado":
        return qs.filter(FILTROS_SITUACAO["arquivado"][1])
    qs = qs.filter(NAO_ARQUIVADO)
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


# ---------------------------------------------------------------- roteiros
def trechos_do_roteiro(roteiro: Roteiro) -> list[TrechoRoteiro]:
    """Trechos do roteiro em ordem, com origem e destino (uma consulta)."""
    prefetch_related_objects([roteiro], Prefetch(
        "trechos", queryset=TrechoRoteiro.objects.select_related("origem", "destino")))
    return list(roteiro.trechos.all())


def roteiros_de_lista(qs: QuerySet[Roteiro]) -> QuerySet[Roteiro]:
    """Tudo que a lista de roteiros exibe, em número fixo de consultas."""
    return (
        qs.select_related("sede", "unidade")
        .prefetch_related(Prefetch(
            "trechos", queryset=TrechoRoteiro.objects.select_related("origem", "destino")))
        .annotate(primeira_saida=Min("trechos__saida_em"),
                  ultima_chegada=Max("trechos__chegada_em"),
                  total_trechos=Count("trechos", distinct=True),
                  total_oficios=Count("oficios", distinct=True))
    )


# Abas como no sistema de referência (finalizados: decisão pendente — ver paridade).
FILTROS_ROTEIRO = {
    "futuros": "Que vão acontecer",
    "andamento": "Em andamento e realizados",
    "cancelados": "Cancelados",
}


def filtrar_roteiros(qs: QuerySet[Roteiro], aba: str | None) -> QuerySet[Roteiro]:
    agora = timezone.now()
    ativos = qs.filter(situacao=Roteiro.Situacao.ATIVO)
    if aba == "futuros":
        return ativos.annotate(_ini=Min("trechos__saida_em")).filter(_ini__gt=agora)
    if aba == "andamento":
        return ativos.annotate(_ini=Min("trechos__saida_em")).filter(_ini__lte=agora)
    if aba == "cancelados":
        return qs.filter(situacao=Roteiro.Situacao.CANCELADO)
    return qs


def contagens_roteiros(qs: QuerySet[Roteiro]) -> dict[str, int]:
    resultado = {"todos": qs.count()}
    for chave in FILTROS_ROTEIRO:
        resultado[chave] = filtrar_roteiros(qs, chave).count()
    return resultado


def buscar_roteiros(qs: QuerySet[Roteiro], termo: str) -> QuerySet[Roteiro]:
    """Sede, destino, observações ou número (#12)."""
    termo = termo.strip()
    if not termo:
        return qs
    numero = termo.lstrip("#")
    filtro = (Q(sede__nome__unaccent__icontains=termo)
              | Q(trechos__destino__nome__unaccent__icontains=termo)
              | Q(observacoes__unaccent__icontains=termo))
    if numero.isdigit():
        filtro |= Q(pk=int(numero))
    return qs.filter(filtro).distinct()


def roteiros_para_oficio(qs: QuerySet[Roteiro], oficio: Oficio) -> list[Roteiro]:
    """Roteiros que podem servir de modelo ao ofício: ativos e com trechos (a sede do
    roteiro vem junto ao usá-lo)."""
    # Uma consulta só: período e destinos vêm agregados (sem buscar os trechos à parte).
    com_trechos = Exists(TrechoRoteiro.objects.filter(roteiro=OuterRef("pk")))
    return list(
        qs.filter(com_trechos, situacao=Roteiro.Situacao.ATIVO)
        .select_related("sede")
        .annotate(primeira_saida=Min("trechos__saida_em"),
                  ultima_chegada=Max("trechos__chegada_em"),
                  paradas=ArrayAgg(Concat("trechos__destino__nome", Value("/"),
                                          "trechos__destino__uf"),
                                   order_by="trechos__ordem"))
        .order_by(F("primeira_saida").desc(nulls_last=True))[:200]
    )


# ---------------------------------------------------------------- justificativas (D6)
ABAS_JUSTIFICATIVAS = {
    "pendentes": "Pendentes",
    "preenchidas": "Preenchidas",
}
PRAZO_PADRAO_DIAS = 10  # o mesmo padrão da configuração institucional


def com_regra_de_prazo(qs: QuerySet[Oficio]) -> QuerySet[Oficio]:
    """Anota, no banco, a regra de prazo do domínio (dominio/prazos.py): a justificativa é
    exigida quando a primeira saída (data local) cai até N dias depois da data do ofício —
    ou antes dela. N vem da configuração da unidade."""
    primeira = (Trecho.objects.filter(oficio=OuterRef("pk"), ordem=1)
                .annotate(dia=TruncDate("saida_em", tzinfo=timezone.get_current_timezone()))
                .values("dia")[:1])
    return qs.annotate(
        saida_dia=Subquery(primeira, output_field=DateField()),
        limite_prazo=ExpressionWrapper(
            F("data_oficio") + Coalesce(F("unidade__configuracao__prazo_justificativa_dias"),
                                        Value(PRAZO_PADRAO_DIAS)),
            output_field=DateField()),
    ).annotate(
        exige_justificativa=ExpressionWrapper(
            Q(saida_dia__isnull=False) & Q(saida_dia__lte=F("limite_prazo")),
            output_field=models.BooleanField()),
    )


def justificativas(qs: QuerySet[Oficio], aba: str = "") -> QuerySet[Oficio]:
    """A lista de justificativas é uma leitura dos ofícios (nada é copiado): os que exigem
    justificativa ou já têm uma escrita. Cancelados e arquivados ficam de fora."""
    qs = com_regra_de_prazo(qs.exclude(situacao=Oficio.Situacao.CANCELADO).filter(NAO_ARQUIVADO))
    preenchida = ~Q(justificativa="")
    qs = qs.filter(Q(exige_justificativa=True) | preenchida)
    if aba == "pendentes":
        return qs.filter(exige_justificativa=True, justificativa="")
    if aba == "preenchidas":
        return qs.filter(preenchida)
    return qs


def contagens_justificativas(qs: QuerySet[Oficio]) -> dict[str, int]:
    base = justificativas(qs)
    return base.aggregate(
        todas=Count("pk"),
        pendentes=Count("pk", filter=Q(exige_justificativa=True, justificativa="")),
        preenchidas=Count("pk", filter=~Q(justificativa="")),
    )
