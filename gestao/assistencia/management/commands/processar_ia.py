"""Worker da assistência por IA: o ÚNICO lugar onde a porta de IA é chamada.

    python manage.py processar_ia            # fica no ar (LISTEN assistencia)
    python manage.py processar_ia --uma-vez  # trata a fila e sai

Fora da requisição web e fora de transação: cada pedido tem a reserva (transação curta), a
chamada (sem transação) e o registro (transação curta). Sem configuração explícita, a porta é
a simulada (sem rede, sem custo). A retenção roda junto, de tempos em tempos.
"""

from __future__ import annotations

import logging
import select
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from gestao.assistencia import manutencao, orcamento, servicos

log = logging.getLogger("gestao.assistencia")
MANUTENCAO_A_CADA = 3600  # s
RESERVAS_A_CADA = 300  # s


class Command(BaseCommand):
    help = "Processa os pedidos de sugestão (IA ou regra) fora da requisição web."

    def add_arguments(self, parser):
        parser.add_argument("--uma-vez", action="store_true")
        parser.add_argument("--intervalo", type=float, default=30.0)

    def handle(self, *args, uma_vez=False, intervalo=30.0, **opts):
        if connection.in_atomic_block:
            raise CommandError("O worker não roda dentro de transação.")
        if uma_vez:
            orcamento.liberar_reservas_presas()
            total = 0
            while (n := servicos.processar_fila()) > 0:
                total += n
            self.stdout.write(f"{total} pedido(s) tratado(s).")
            return
        connection.ensure_connection()
        with connection.cursor() as cur:
            cur.execute("LISTEN assistencia")
        pg = connection.connection
        self.stdout.write("Worker da assistência aguardando…")
        ultima = ultima_reserva = 0.0
        while True:
            if time.monotonic() - ultima_reserva > RESERVAS_A_CADA:
                try:
                    orcamento.liberar_reservas_presas()
                except Exception:
                    log.exception("Liberação de reservas presas falhou")
                ultima_reserva = time.monotonic()
            try:
                while servicos.processar_fila() > 0:
                    pass
            except Exception:
                log.exception("Rodada da assistência falhou")
            if time.monotonic() - ultima > MANUTENCAO_A_CADA:
                try:
                    manutencao.purgar()
                except Exception:
                    log.exception("Retenção da assistência falhou")
                ultima = time.monotonic()
            select.select([pg.fileno()], [], [], intervalo)
            for _ in pg.notifies(timeout=0):
                pass
