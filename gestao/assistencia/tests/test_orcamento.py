"""Orçamento de IA sob concorrência: a reserva trava as linhas do mês (`select_for_update`);
duas chamadas simultâneas que juntas passam do teto → só uma reserva. Banco real (threads com
conexões próprias), sem o cenário de Viagens."""

from __future__ import annotations

import threading
from decimal import Decimal

import pytest
from django.db import connection

from gestao.assistencia import orcamento
from gestao.assistencia.models import OrcamentoIA

USO = "viagens.rt_rascunho"


@pytest.mark.django_db(transaction=True)
def test_duas_reservas_simultaneas_nao_passam_do_teto():
    linha = orcamento.garantir(orcamento.GLOBAL)
    OrcamentoIA.objects.filter(pk=linha.pk).update(teto_usd=Decimal("0.0100"))
    orcamento.garantir(USO)
    largada = threading.Barrier(2)
    resultados: list[object] = []

    def reservar():
        try:
            largada.wait(timeout=10)
            resultados.append(orcamento.reservar(USO, Decimal("0.008")))
        finally:
            connection.close()

    threads = [threading.Thread(target=reservar) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert len(resultados) == 2
    assert sum(r is not None for r in resultados) == 1
    g = OrcamentoIA.objects.get(escopo=orcamento.GLOBAL)
    assert g.reservado_usd == Decimal("0.008") and g.chamadas == 1 and g.bloqueadas == 1


@pytest.mark.django_db
def test_liquidar_troca_a_reserva_pelo_estimado_e_herda_o_teto():
    from datetime import date

    reserva = orcamento.reservar(USO, Decimal("0.010"))
    orcamento.liquidar(reserva, Decimal("0.002"), 300, 100)
    g = OrcamentoIA.objects.get(escopo=orcamento.GLOBAL, mes=reserva.mes)
    assert g.reservado_usd == 0 and g.gasto_estimado_usd == Decimal("0.002")
    assert g.tokens_entrada == 300 and g.tokens_saida == 100
    assert g.teto_usd == orcamento.TETO_GLOBAL_PADRAO
    OrcamentoIA.objects.filter(pk=g.pk).update(teto_usd=Decimal("7.5"))
    seguinte = date(reserva.mes.year + (reserva.mes.month == 12),
                    reserva.mes.month % 12 + 1, 1)
    assert orcamento.garantir(orcamento.GLOBAL, seguinte).teto_usd == Decimal("7.5")


def _pedido(django_user_model, n: int = 1):
    from gestao.assistencia.models import PedidoSugestao

    u = django_user_model.objects.create_user(f"res-{n}", f"res{n}@pc.pr.gov.br",
                                              "senha-forte-1", nome="Teste de reserva")
    return PedidoSugestao.objects.create(uso=USO, recurso_id=str(n), usuario=u,
                                         estado="processando", versao_fonte="v",
                                         versao_prompt="p", chave=f"chave-{n}")


@pytest.mark.django_db
def test_reserva_presa_de_worker_morto_vira_gasto(django_user_model):
    """O worker morreu entre reservar e liquidar: a chamada pode ter sido feita (e cobrada),
    então a reserva vira gasto no pior caso — nunca volta ao orçamento."""
    from datetime import timedelta

    from django.utils import timezone

    from gestao.assistencia import manutencao
    from gestao.assistencia.models import PedidoSugestao

    preso, vivo = _pedido(django_user_model, 1), _pedido(django_user_model, 2)
    orcamento.reservar(USO, Decimal("0.300"), pedido_pk=preso.pk, prazo=timedelta(minutes=1))
    reserva_viva = orcamento.reservar(USO, Decimal("0.200"), pedido_pk=vivo.pk,
                                      prazo=timedelta(hours=2))
    g = OrcamentoIA.objects.get(escopo=orcamento.GLOBAL)
    assert g.reservado_usd == Decimal("0.5")
    # O worker do primeiro morreu; antes do prazo + folga, nada é liberado.
    assert orcamento.liberar_reservas_presas() == 0
    depois = timezone.now() + timedelta(minutes=12)
    assert orcamento.liberar_reservas_presas(agora=depois) == 1
    g.refresh_from_db()
    assert g.reservado_usd == Decimal("0.2") and g.gasto_estimado_usd == Decimal("0.3")
    assert PedidoSugestao.objects.get(pk=preso.pk).reserva_usd == 0
    assert OrcamentoIA.objects.get(escopo=USO).reservado_usd == Decimal("0.2")
    # O vivo liquida normalmente; a rotina diária também varre (e não acha mais nada).
    orcamento.liquidar(reserva_viva, Decimal("0.05"))
    g.refresh_from_db()
    assert g.reservado_usd == 0 and g.gasto_estimado_usd == Decimal("0.35")
    assert "0 reserva(s) presa(s)" in manutencao.diaria()


@pytest.mark.django_db
def test_liquidar_depois_de_liberada_nao_desconta_duas_vezes(django_user_model):
    from datetime import timedelta

    from django.utils import timezone

    lento, outro = _pedido(django_user_model, 3), _pedido(django_user_model, 4)
    reserva = orcamento.reservar(USO, Decimal("0.300"), pedido_pk=lento.pk,
                                 prazo=timedelta(minutes=1))
    orcamento.reservar(USO, Decimal("0.100"), pedido_pk=outro.pk, prazo=timedelta(hours=2))
    orcamento.liberar_reservas_presas(agora=timezone.now() + timedelta(minutes=12))
    orcamento.liquidar(reserva, Decimal("0.020"))  # o lento ainda terminou
    g = OrcamentoIA.objects.get(escopo=orcamento.GLOBAL)
    assert g.reservado_usd == Decimal("0.1")  # a reserva do outro continua intacta
    # Cobrado o pior caso (0,30) quando ficou presa, mais o que o lento ainda informou (0,02):
    # conservador — o teto nunca é furado; a reserva não é descontada duas vezes.
    assert g.gasto_estimado_usd == Decimal("0.32")


@pytest.mark.django_db
def test_lease_vencido_com_chamada_admitida_nao_refaz_as_cegas(django_user_model):
    from datetime import timedelta

    from django.utils import timezone

    from gestao.assistencia import servicos
    from gestao.assistencia.models import PedidoSugestao

    p = _pedido(django_user_model, 5)
    orcamento.reservar(USO, Decimal("0.300"), pedido_pk=p.pk, prazo=timedelta(minutes=1))
    PedidoSugestao.objects.filter(pk=p.pk).update(tentativas_admitidas=2)
    assert servicos.reservar_proximo(agora=timezone.now() + timedelta(minutes=2)) is None
    p.refresh_from_db()
    assert p.estado == "falhou" and p.reserva_usd == 0 and p.chamadas_sem_registro == 2
    g = OrcamentoIA.objects.get(escopo=orcamento.GLOBAL)
    assert g.reservado_usd == 0 and g.gasto_estimado_usd == Decimal("0.3")
    assert servicos.chamadas_hoje(USO) == 2  # as vagas do dia continuam tomadas


@pytest.mark.django_db
def test_erro_inesperado_devolve_a_reserva(django_user_model):
    """Erro inesperado entre reservar e liquidar: `_encerrar` devolve a reserva (antes ela
    ficava presa para sempre, com `reservado_ate` nulo fora da varredura)."""
    from datetime import timedelta

    from gestao.assistencia import servicos
    from gestao.assistencia.models import PedidoSugestao

    p = _pedido(django_user_model, 6)
    orcamento.reservar(USO, Decimal("0.300"), pedido_pk=p.pk, prazo=timedelta(minutes=1))
    servicos._encerrar(PedidoSugestao.objects.get(pk=p.pk),
                       PedidoSugestao.Estado.FALHOU, "erro_interno")
    p.refresh_from_db()
    assert p.estado == PedidoSugestao.Estado.FALHOU and p.reserva_usd == 0
    assert OrcamentoIA.objects.get(escopo=orcamento.GLOBAL).reservado_usd == 0
    assert OrcamentoIA.objects.get(escopo=USO).reservado_usd == 0


@pytest.mark.django_db
def test_reserva_de_pedido_encerrado_sem_lease_e_varrida(django_user_model):
    from datetime import timedelta

    from gestao.assistencia.models import PedidoSugestao

    p = _pedido(django_user_model, 7)
    orcamento.reservar(USO, Decimal("0.300"), pedido_pk=p.pk, prazo=timedelta(minutes=1))
    PedidoSugestao.objects.filter(pk=p.pk).update(estado=PedidoSugestao.Estado.FALHOU,
                                                   reservado_ate=None)
    assert orcamento.liberar_reservas_presas() == 1
    assert OrcamentoIA.objects.get(escopo=orcamento.GLOBAL).reservado_usd == 0


@pytest.mark.django_db
def test_vagas_do_dia_descontam_pedidos_em_voo(django_user_model):
    """Dois workers perto do teto diário: as tentativas já admitidas por um pedido em voo
    (lease vivo) saem das vagas do outro."""
    from datetime import timedelta
    from types import SimpleNamespace

    from django.utils import timezone

    from gestao.assistencia import servicos
    from gestao.assistencia.models import PedidoSugestao

    em_voo, novo = _pedido(django_user_model, 8), _pedido(django_user_model, 9)
    PedidoSugestao.objects.filter(pk=em_voo.pk).update(
        tentativas_admitidas=2, reservado_ate=timezone.now() + timedelta(minutes=5))
    config = SimpleNamespace(max_chamadas_dia=3, max_tentativas=3)
    assert servicos._admitir(novo, USO, config) == 1  # 3 do dia − 2 em voo
    PedidoSugestao.objects.filter(pk=em_voo.pk).update(reservado_ate=timezone.now())
    assert servicos._admitir(novo, USO, config) == 3  # lease vencido: as vagas voltam


def test_nomes_da_equipe_saem_antes_do_provedor():
    from gestao.assistencia import servicos

    texto = "Reunião com Ana Paula Ribeiro e o motorista Ribeiro na sede; ANA confirmou."
    limpo = servicos._sem_nomes(texto, ["Ana Paula Ribeiro"])
    assert "Ribeiro" not in limpo and "Paula" not in limpo
    assert limpo.count("[pessoa]") >= 2 and "sede" in limpo
