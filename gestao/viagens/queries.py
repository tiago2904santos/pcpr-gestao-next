"""Consultas de leitura do módulo Viagens (listas, contagens, tabelas vigentes)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

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

from . import prestacao
from .dominio import busca, recorte
from .dominio.diarias import Faixa, ValorVigente
from .models import (
    Documento,
    Oficio,
    Roteiro,
    Trecho,
    TrechoRoteiro,
    ViaAssinada,
    Viajante,
)


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


_pdf_do_oficio = (Documento.objects.filter(oficio=OuterRef("pk"), tipo=Documento.Tipo.OFICIO,
                                          situacao=Documento.Situacao.PRONTO)
                  .order_by("-versao"))


def com_dados_de_lista(qs: QuerySet[Oficio]) -> QuerySet[Oficio]:
    """Tudo que a lista de ofícios exibe, em número fixo de consultas."""
    return (
        qs.select_related("unidade__configuracao", "viatura", "viatura__combustivel", "sede",
                          "motorista_externo_servidor")
        .prefetch_related(
            Prefetch("viajantes", queryset=Viajante.objects.select_related("servidor")),
            Prefetch("trechos", queryset=Trecho.objects.select_related("origem", "destino")
                     .order_by("ordem")),
        )
        .annotate(primeira_saida=Min("trechos__saida_em"),
                  tem_documentos=Exists(Documento.objects.filter(oficio=OuterRef("pk"))),
                  # Menu ⋮ (D7): o PDF que vale ("Ver PDF vN", "Anexar assinado") e se já há
                  # via assinada — subconsultas na mesma consulta, nenhuma por linha.
                  pdf_oficio_id=Subquery(_pdf_do_oficio.values("pk")[:1]),
                  pdf_oficio_versao=Subquery(_pdf_do_oficio.values("versao")[:1]),
                  via_oficio=Exists(ViaAssinada.objects.filter(
                      oficio=OuterRef("pk"), tipo=ViaAssinada.Tipo.OFICIO,
                      revogada_em__isnull=True)))
    )


NAO_ARQUIVADO = Q(arquivado_em__isnull=True)


# ---------------------------------------------------------------- recortes (D1/D2)
# As regras estão em dominio/recorte.py; aqui, a mesma conta em SQL. `_saida` é a 1ª saída
# (a mesma que a linha mostra), por subconsulta: entra em filtro e em contagem condicional
# sem juntar trechos (nem repetir o ofício).
def com_primeira_saida(qs: QuerySet[Oficio]) -> QuerySet[Oficio]:
    primeira = (Trecho.objects.filter(oficio=OuterRef("pk")).order_by()
                .values("oficio").annotate(m=Min("saida_em")).values("m"))
    return qs.annotate(_saida=Subquery(primeira, output_field=models.DateTimeField()))


def fim_de_hoje() -> datetime:
    hoje = timezone.localdate()
    return timezone.make_aware(datetime.combine(hoje, time.max))


def _contas_prestadas() -> Q:
    # Prestação de contas de todos da equipe finalizada (referência: "Contas prestadas").
    return Q(situacao=Oficio.Situacao.EMITIDO) & prestacao.prestadas("oficio")


def q_da_aba(aba: str, limite: datetime) -> Q:
    """Aba temporal (dominio.recorte.aba_do_oficio) — exige `com_primeira_saida`."""
    cancelado = Q(situacao=Oficio.Situacao.CANCELADO)
    if aba == recorte.CANCELADOS:
        return cancelado
    if aba == recorte.PRESTADAS:
        return ~cancelado & _contas_prestadas()
    pendente = ~cancelado & ~_contas_prestadas()
    if aba == recorte.FUTUROS:
        return pendente & (Q(_saida__gt=limite) | Q(_saida__isnull=True))
    if aba == recorte.ANDAMENTO:
        return pendente & Q(_saida__lte=limite)
    return Q()


def q_do_documento(documento: str) -> Q:
    """Documento (dominio.recorte.documento_do_oficio): arquivado só quando pedido."""
    if documento == recorte.ARQUIVADO:
        return Q(arquivado_em__isnull=False)
    if documento == recorte.RASCUNHO:
        return NAO_ARQUIVADO & Q(situacao=Oficio.Situacao.RASCUNHO)
    if documento == recorte.EMITIDO:
        return NAO_ARQUIVADO & Q(situacao=Oficio.Situacao.EMITIDO)
    return NAO_ARQUIVADO


def aplicar_recorte(qs: QuerySet[Oficio], aba: str, documento: str) -> QuerySet[Oficio]:
    return com_primeira_saida(qs).filter(q_da_aba(aba, fim_de_hoje()),
                                         q_do_documento(documento))


def contagens_do_recorte(base: QuerySet[Oficio], filtrado: QuerySet[Oficio] | None,
                         aba: str, documento: str) -> dict[str, int]:
    """Contadores das abas e do filtro Documento numa agregação condicional só.

    Cada dimensão conta com a busca e os filtros (`filtrado`) e com a escolha da OUTRA
    dimensão, ignorando a própria — é o que a referência fazia com as abas. `universo` é a
    aba atual sem busca nem filtros (o "de M" da barra): sem nada filtrado (`filtrado` é
    None) sai na mesma consulta; com filtro, numa segunda (contar sobre `pk IN (busca)`
    repetia a busca em cada contador — 0,6 s com "curitiba" no PREVIEW)."""
    limite = fim_de_hoje()
    contas = {f"aba-{chave or 'todos'}": Count(
        "pk", filter=q_do_documento(documento) & q_da_aba(chave, limite))
        for chave, _ in recorte.ABAS}
    contas.update({f"doc-{chave or 'todos'}": Count(
        "pk", filter=q_da_aba(aba, limite) & q_do_documento(chave))
        for chave, _ in recorte.DOCUMENTOS})
    universo = Count("pk", filter=q_da_aba(aba, limite) & (
        Q() if documento == recorte.ARQUIVADO else NAO_ARQUIVADO))
    if filtrado is None:
        return com_primeira_saida(base.order_by()).aggregate(**contas, universo=universo)
    resultado = com_primeira_saida(filtrado.order_by()).aggregate(**contas)
    resultado.update(com_primeira_saida(base.order_by()).aggregate(universo=universo))
    return resultado


def anos_dos_numeros(qs: QuerySet[Oficio]) -> list[int]:
    """Anos que existem na numeração (opções do filtro "Ano do número"), do mais novo."""
    return list(qs.order_by("-ano").values_list("ano", flat=True).distinct())


def q_destino(termo: str) -> Q:
    """Algum trecho vai a uma cidade com esse nome — sem contar a volta à sede (F2: com a
    sede em Curitiba, "curitiba" trazia quase todos os ofícios só porque voltam para lá).
    Subconsulta não correlacionada (o banco a resolve uma vez, não por ofício)."""
    trechos = Trecho.objects.filter(destino__nome__unaccent__icontains=termo).filter(
        Q(oficio__sede__isnull=True) | ~Q(destino_id=F("oficio__sede_id")))
    return Q(pk__in=trechos.values("oficio_id"))


def q_servidor(termo: str) -> Q:
    return Q(pk__in=Viajante.objects.filter(
        servidor__nome__unaccent__icontains=termo).values("oficio_id"))


def q_placa(termo: str) -> Q:
    placa = busca.placa_normalizada(termo)
    return Q(viatura__placa__icontains=placa) | Q(transporte_placa__icontains=placa)


def filtro_de_leitura(leitura: busca.Leitura) -> Q:
    """O Q de cada leitura do termo (dominio.busca diz quais existem). Destino e servidor
    vão por subconsulta (IN): nada de juntar tabelas, então nada de ofício repetido nem
    DISTINCT."""
    termo = leitura.termo
    if leitura.escopo == busca.NUMERO_ESCOPO:
        numero, ano = termo.split("/")
        return Q(numero=int(numero), ano=int(ano))
    if leitura.escopo == busca.PROTOCOLO:
        return Q(protocolo__contains=termo)
    if leitura.escopo == busca.PLACA_ESCOPO:
        return q_placa(termo)
    if leitura.escopo == busca.DESTINO:
        return q_destino(termo)
    return q_servidor(termo)


def aplicar_leitura(qs: QuerySet[Oficio], leitura: busca.Leitura) -> QuerySet[Oficio]:
    return qs.filter(filtro_de_leitura(leitura))


def contar_leituras(qs: QuerySet[Oficio], leituras: list[busca.Leitura]) -> dict[str, int]:
    """Quantos ofícios cada leitura traria — numa consulta só, para a tela poder dizer
    "Ofício 26/2026 (1)" e "Protocolo com 26 (12)" antes de a pessoa escolher."""
    if not leituras:
        return {}
    return qs.order_by().aggregate(**{
        leitura.escopo: Count("pk", filter=filtro_de_leitura(leitura))
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
    """Filtros da gaveta (forms.FiltrosOficio.validos). Chave ausente ou vazia não filtra
    nada."""
    de, ate = filtros.get("saida_de"), filtros.get("saida_ate")
    if de or ate:
        # É o mesmo trecho (a ida) que tem de cair no período; EXISTS não repete o ofício.
        ida = Trecho.objects.filter(oficio=OuterRef("pk"), ordem=1)
        if de:
            ida = ida.filter(saida_em__date__gte=de)
        if ate:
            ida = ida.filter(saida_em__date__lte=ate)
        qs = qs.filter(Exists(ida))
    if filtros.get("criacao_de"):
        qs = qs.filter(data_oficio__gte=filtros["criacao_de"])
    if filtros.get("criacao_ate"):
        qs = qs.filter(data_oficio__lte=filtros["criacao_ate"])
    if filtros.get("ano"):
        qs = qs.filter(ano=filtros["ano"])
    protocolo = "".join(c for c in (filtros.get("protocolo") or "") if c.isdigit())
    if protocolo:
        qs = qs.filter(protocolo__contains=protocolo)
    if filtros.get("veiculo"):
        qs = qs.filter(_filtro_de_veiculo(filtros["veiculo"]))
    if filtros.get("diarias_de") is not None:
        qs = qs.filter(diarias_total__gte=filtros["diarias_de"])
    if filtros.get("diarias_ate") is not None:
        qs = qs.filter(diarias_total__lte=filtros["diarias_ate"])
    return qs


def indicadores_do_painel(qs: QuerySet[Oficio]) -> dict[str, object]:
    hoje = timezone.localdate()
    inicio_mes = hoje.replace(day=1)
    em_30 = timezone.now() + timedelta(days=30)
    return {
        "oficios_mes": qs.filter(data_oficio__gte=inicio_mes).exclude(
            situacao=Oficio.Situacao.CANCELADO).count(),
        "rascunhos": qs.filter(NAO_ARQUIVADO, situacao=Oficio.Situacao.RASCUNHO).count(),
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
    "finalizados": "Finalizados",
    "cancelados": "Cancelados",
}


def filtrar_roteiros(qs: QuerySet[Roteiro], aba: str | None) -> QuerySet[Roteiro]:
    agora = timezone.now()
    ativos = qs.filter(situacao=Roteiro.Situacao.ATIVO)
    prestadas = prestacao.prestadas("roteiro")
    if aba == "finalizados":
        return ativos.filter(prestadas)
    if aba == "futuros":
        return ativos.annotate(_ini=Min("trechos__saida_em")).filter(~prestadas, _ini__gt=agora)
    if aba == "andamento":
        return ativos.annotate(_ini=Min("trechos__saida_em")).filter(~prestadas,
                                                                     _ini__lte=agora)
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
        return qs.filter(Q(exige_justificativa=True) & Q(justificativa=""))
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
