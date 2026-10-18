"""Orçamento mensal de IA (custo ESTIMADO), seguro sob concorrência.

1. `reservar(uso, maximo)`: transação curta; trava as linhas do mês (global e do uso, sempre
   nessa ordem — sem impasse) com `select_for_update`; se `gasto + reservado + maximo` passar
   de algum teto, recusa (conta como bloqueada) — e quem chamou vai pelo caminho
   determinístico. Senão, soma `maximo` em `reservado`.
2. A chamada ao provedor acontece FORA de transação.
3. `liquidar(reserva, estimado, tokens)`: outra transação curta; tira a reserva e soma o
   estimado da resposta (nunca maior que o reservado, salvo retentativas já contadas).
4. Worker que morre entre 1 e 3 deixa a reserva anotada no pedido; `liberar_reservas_presas`
   (no laço do `processar_ia` e na rotina diária) a devolve depois do prazo da chamada + folga.

Mês civil em America/Sao_Paulo. Teto nulo = sem teto próprio (vale o global); zero = nada
com custo sai. Ao virar o mês, a linha nova herda o teto da anterior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from . import policies
from .models import OrcamentoIA

GLOBAL = "global"
TETO_GLOBAL_PADRAO = Decimal("5.00")   # US$/mês, estimado — o administrador ajusta na tela
#: Quanto esperar, além do prazo da chamada, antes de dar a reserva por presa.
FOLGA_RESERVA_PRESA = timedelta(minutes=10)


@dataclass(frozen=True)
class Reserva:
    mes: date
    escopos: tuple[str, ...]
    valor: Decimal
    pedido_pk: int | None = None


def mes_atual(hoje: date | None = None) -> date:
    return (hoje or timezone.localdate()).replace(day=1)


def _teto_herdado(escopo: str, mes: date) -> Decimal | None:
    anterior = (OrcamentoIA.objects.filter(escopo=escopo, mes__lt=mes).order_by("-mes")
                .values_list("teto_usd", flat=True).first())
    if anterior is not None:
        return anterior
    return TETO_GLOBAL_PADRAO if escopo == GLOBAL else None


def garantir(escopo: str, mes: date | None = None) -> OrcamentoIA:
    mes = mes or mes_atual()
    linha = OrcamentoIA.objects.filter(escopo=escopo, mes=mes).first()
    if linha:
        return linha
    try:
        with transaction.atomic():
            return OrcamentoIA.objects.create(escopo=escopo, mes=mes,
                                              teto_usd=_teto_herdado(escopo, mes))
    except IntegrityError:  # outro processo criou ao mesmo tempo
        return OrcamentoIA.objects.get(escopo=escopo, mes=mes)


def escopos_de(uso: str) -> tuple[str, ...]:
    return tuple(sorted({GLOBAL, uso}, key=lambda e: (e != GLOBAL, e)))


def reservar(uso: str, maximo: Decimal, hoje: date | None = None, *,
             pedido_pk: int | None = None, prazo: timedelta | None = None) -> Reserva | None:
    """Com `pedido_pk`, a reserva fica anotada no pedido (valor, mês e o prazo até o qual a
    chamada pode durar) na MESMA transação: um worker que morra depois disso deixa o rastro
    para `liberar_reservas_presas`."""
    from .models import PedidoSugestao

    mes = mes_atual(hoje)
    escopos = escopos_de(uso)
    for e in escopos:
        garantir(e, mes)
    with transaction.atomic():
        linhas = list(OrcamentoIA.objects.select_for_update()
                      .filter(escopo__in=escopos, mes=mes).order_by("id"))
        estourou = any(linha.teto_usd is not None
                       and linha.gasto_estimado_usd + linha.reservado_usd + maximo
                       > linha.teto_usd for linha in linhas)
        if estourou:
            OrcamentoIA.objects.filter(pk__in=[linha.pk for linha in linhas]).update(
                bloqueadas=F("bloqueadas") + 1)
            return None
        OrcamentoIA.objects.filter(pk__in=[linha.pk for linha in linhas]).update(
            reservado_usd=F("reservado_usd") + maximo, chamadas=F("chamadas") + 1)
        if pedido_pk is not None:
            campos = {"reserva_usd": maximo, "reserva_mes": mes}
            if prazo is not None:
                campos["reservado_ate"] = timezone.now() + prazo
            PedidoSugestao.objects.filter(pk=pedido_pk).update(**campos)
    return Reserva(mes, escopos, maximo, pedido_pk)


def _devolver(mes: date, escopos: tuple[str, ...], valor: Decimal) -> None:
    for linha in (OrcamentoIA.objects.select_for_update()
                  .filter(escopo__in=escopos, mes=mes).order_by("id")):
        linha.reservado_usd = max(Decimal(0), linha.reservado_usd - valor)
        linha.save(update_fields=["reservado_usd", "atualizado_em"])


def liquidar(reserva: Reserva, estimado: Decimal, tokens_entrada: int = 0,
             tokens_saida: int = 0) -> None:
    """Troca a reserva pelo estimado. Se a reserva do pedido já foi liberada por estar presa
    (o worker demorou além do prazo), não a desconta de novo: só soma o estimado."""
    from .models import PedidoSugestao

    with transaction.atomic():
        ainda_reservado = True
        if reserva.pedido_pk is not None:
            pedido = (PedidoSugestao.objects.select_for_update()
                      .filter(pk=reserva.pedido_pk).first())
            ainda_reservado = bool(pedido and pedido.reserva_usd > 0)
            if pedido and ainda_reservado:
                pedido.reserva_usd, pedido.reserva_mes = Decimal(0), None
                pedido.save(update_fields=["reserva_usd", "reserva_mes", "atualizado_em"])
        linhas = list(OrcamentoIA.objects.select_for_update()
                      .filter(escopo__in=reserva.escopos, mes=reserva.mes).order_by("id"))
        for linha in linhas:
            if ainda_reservado:
                linha.reservado_usd = max(Decimal(0), linha.reservado_usd - reserva.valor)
            linha.gasto_estimado_usd += estimado
            linha.tokens_entrada += max(0, tokens_entrada)
            linha.tokens_saida += max(0, tokens_saida)
            linha.save(update_fields=["reservado_usd", "gasto_estimado_usd", "tokens_entrada",
                                      "tokens_saida", "atualizado_em"])


def liberar_do_pedido(pedido) -> bool:
    """Devolve ao orçamento a reserva anotada no pedido (já travado por quem chama)."""
    if not pedido.reserva_usd or pedido.reserva_mes is None:
        return False
    _devolver(pedido.reserva_mes, escopos_de(pedido.uso), pedido.reserva_usd)
    pedido.reserva_usd, pedido.reserva_mes = Decimal(0), None
    pedido.save(update_fields=["reserva_usd", "reserva_mes", "atualizado_em"])
    return True


def liberar_reservas_presas(agora=None, folga: timedelta = FOLGA_RESERVA_PRESA) -> int:
    """Reservas de pedidos que passaram do prazo da chamada (mais a folga) sem liquidar: o
    worker morreu entre reservar e liquidar. O valor volta ao orçamento; o pedido volta à
    fila pelo lease vencido (e reserva de novo, se ainda couber)."""
    from .models import PedidoSugestao

    agora = agora or timezone.now()
    liberadas = 0
    while True:
        with transaction.atomic():
            pedido = (PedidoSugestao.objects.select_for_update(skip_locked=True)
                      .filter(reserva_usd__gt=0, reservado_ate__lt=agora - folga)
                      .order_by("id").first())
            if pedido is None:
                return liberadas
            liberar_do_pedido(pedido)
            liberadas += 1


@transaction.atomic
def definir_teto(usuario, escopo: str, teto: Decimal | None) -> OrcamentoIA:
    policies.exigir(policies.pode_administrar(usuario),
                    "Só quem administra a IA define o orçamento.")
    if teto is not None and teto < 0:
        raise ValueError("O teto não pode ser negativo.")
    if escopo == GLOBAL and teto is None:
        raise ValueError("O orçamento global precisa de um teto (zero bloqueia tudo).")
    linha = garantir(escopo)
    linha = OrcamentoIA.objects.select_for_update().get(pk=linha.pk)
    linha.teto_usd = teto
    linha.save(update_fields=["teto_usd", "atualizado_em"])
    return linha


def resumo(mes: date | None = None) -> dict[str, OrcamentoIA]:
    """Só leitura (as telas chamam em GET): sem a linha global do mês, devolve uma linha NÃO
    gravada com o teto herdado. Quem cria a linha é o caminho de escrita (reservar, definir
    teto) ou a rotina diária."""
    mes = mes or mes_atual()
    linhas = {o.escopo: o for o in OrcamentoIA.objects.filter(mes=mes)}
    if GLOBAL not in linhas:
        linhas[GLOBAL] = OrcamentoIA(escopo=GLOBAL, mes=mes,
                                     teto_usd=_teto_herdado(GLOBAL, mes))
    return linhas
