"""Dados de demonstração da assistência (PREVIEW): chamar DEPOIS de `viagens.demonstracao
.semear()` — os exemplos saem dos registros fictícios que ela cria.

    from gestao.assistencia import demonstracao
    demonstracao.semear()

Deixa: o RT e o ofício no modo IA (porta SIMULADA: sem rede, sem custo), os demais na regra;
teto global de US$ 5,00 (estimado); uma sugestão pronta por uso que tem exemplo, uma
descartada (para o painel mostrar decisões) e o restante pronto para revisar. Nada é aceito
— aceitar mudaria os documentos de demonstração.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction

from gestao.plataforma import ambiente

from . import ganchos, orcamento, servicos
from .models import ConfiguracaoUso, OrcamentoIA, PedidoSugestao, Sugestao

EM_MODO_IA = ("viagens.rt_rascunho", "viagens.oficio_textos", "viagens.leitura_programacao")


def limpar() -> None:
    ambiente.exigir_ambiente_de_demonstracao("limpar a assistência de demonstração")
    with transaction.atomic():
        Sugestao.objects.all().delete()
        PedidoSugestao.objects.all().delete()
        OrcamentoIA.objects.all().delete()
        ConfiguracaoUso.objects.all().delete()


def semear() -> dict[str, int]:
    ambiente.exigir_ambiente_de_demonstracao("semear a assistência de demonstração")
    limpar()
    for uso in ganchos.usos():
        ConfiguracaoUso.objects.update_or_create(
            uso=uso.chave, defaults={"ligado": True,
                                     "modo": ConfiguracaoUso.Modo.IA if uso.chave in EM_MODO_IA
                                     else ConfiguracaoUso.Modo.REGRA,
                                     "motivo": "Demonstração (IA simulada, sem custo)."})
    linha = orcamento.garantir(orcamento.GLOBAL)
    OrcamentoIA.objects.filter(pk=linha.pk).update(teto_usd=Decimal("5.00"))
    pedidos = 0
    for uso in ganchos.usos():
        exemplo = uso.exemplo_demo() if uso.exemplo_demo else None
        if exemplo is None:
            continue
        usuario, recurso, opcoes = exemplo
        try:
            servicos.pedir(usuario, uso.chave, recurso, opcoes)
        except (servicos.PedidoRecusado, ganchos.RecursoInexistente, PermissionDenied):
            continue  # um exemplo que não serve não derruba a semeadura
        pedidos += 1
    servicos.processar_fila(limite=50)
    descartadas = 0
    plano = Sugestao.objects.filter(uso="viagens.plano_textos", estado=Sugestao.Estado.PRONTA
                                    ).select_related("pedido__usuario").first()
    if plano is not None:
        servicos.descartar(plano.pedido.usuario, plano.pk, Sugestao.MotivoDescarte.GENERICO)
        descartadas = 1
    return {"pedidos": pedidos, "sugestoes": Sugestao.objects.count(),
            "descartadas": descartadas}
