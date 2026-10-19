"""Diagnóstico da porta de IA.

    python manage.py ia_check          # configuração, sem tocar a rede
    python manage.py ia_check --ensaio # um pedido ao adaptador SIMULADO (sem rede, sem custo)

Nunca chama o provedor real e nunca mostra segredo (a chave aparece só como "configurada").
Uma chamada real custa dinheiro: só acontece pelo worker `processar_ia`, com orçamento.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from gestao.integracoes.ia import servico
from gestao.integracoes.ia.adaptadores import AdaptadorSimulado
from gestao.integracoes.ia.porta import BlocoDeDados, PedidoIA

ESQUEMA = {"type": "object", "additionalProperties": False, "required": ["ok"],
           "properties": {"ok": {"type": "boolean"}}}


class Command(BaseCommand):
    help = "Mostra a configuração da IA; com --ensaio, exercita o adaptador simulado."

    def add_arguments(self, parser):
        parser.add_argument("--ensaio", action="store_true",
                            help="Pedido de ensaio ao adaptador simulado (sem rede).")

    def handle(self, *args, ensaio: bool = False, **opcoes):
        for chave, valor in servico.diagnostico().items():
            self.stdout.write(f"{chave:>28}: {valor}")
        if not ensaio:
            return
        pedido = PedidoIA(uso="diagnostico", instrucoes="Responda no esquema.",
                          versao_prompt="diagnostico-v1",
                          dados=(BlocoDeDados("fatos", "ensaio"),), esquema=ESQUEMA,
                          resposta_simulada={"ok": True})
        r = servico.executar(pedido, AdaptadorSimulado())
        estilo = self.style.SUCCESS if r.ok else self.style.WARNING
        self.stdout.write(estilo(f"ensaio simulado: {'ok' if r.ok else r.erro_codigo} · "
                                 f"{r.tokens_entrada}+{r.tokens_saida} tokens estimados · "
                                 f"custo estimado US$ {r.custo_estimado}"))
