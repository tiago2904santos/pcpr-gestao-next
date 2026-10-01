"""Worker da outbox. `--uma-vez` processa o que houver e sai (útil em cron/testes)."""

from __future__ import annotations

import select

from django.core.management.base import BaseCommand
from django.db import connection

from gestao.plataforma.outbox import processar_lote


class Command(BaseCommand):
    help = "Entrega as mensagens pendentes da outbox aos assinantes."

    def add_arguments(self, parser):
        parser.add_argument("--uma-vez", action="store_true")
        parser.add_argument("--intervalo", type=float, default=30.0)

    def handle(self, *args, uma_vez=False, intervalo=30.0, **opts):
        if uma_vez:
            total = 0
            while (n := processar_lote()) > 0:
                total += n
            self.stdout.write(f"{total} mensagem(ns) tratada(s).")
            return
        connection.ensure_connection()
        with connection.cursor() as cur:
            cur.execute("LISTEN outbox")
        pg = connection.connection
        self.stdout.write("Worker da outbox aguardando mensagens…")
        while True:
            while processar_lote() > 0:
                pass
            # Acorda por NOTIFY (commit de nova mensagem) ou pelo intervalo (backoff).
            select.select([pg.fileno()], [], [], intervalo)
            for _ in pg.notifies(timeout=0):
                pass
