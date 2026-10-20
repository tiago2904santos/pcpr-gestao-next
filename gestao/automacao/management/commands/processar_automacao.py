"""Worker da automação: envia comunicações, processa webhooks, baixa/associa arquivos e
entrega os eventos ao n8n (quando configurado).

    python manage.py processar_automacao            # fica no ar (LISTEN automacao)
    python manage.py processar_automacao --uma-vez  # trata o que houver e sai

Cada item tem a própria transação curta; a chamada ao canal acontece fora delas. O contexto
de auditoria é limpo a cada item (a conexão persiste entre itens).
"""

from __future__ import annotations

import logging
import select
import time

from django.core.management.base import BaseCommand
from django.db import connection

from gestao.automacao import entrada, entrega, eventos, manutencao, recebimentos
from gestao.plataforma import recursos

log = logging.getLogger("gestao.automacao")
MANUTENCAO_A_CADA = 300  # s


def rodada(limite: int = 50) -> int:
    """Uma passada pelas três filas. Devolve quantos itens tratou."""
    tratados = 0
    for _ in range(limite):
        feito = False
        for etapa in (entrada.processar_uma_entrada, recebimentos.processar_um,
                      entrega.processar_uma, eventos.processar_um):
            try:
                if etapa():
                    feito = True
                    tratados += 1
            except Exception:
                log.exception("Etapa %s da automação falhou", etapa.__name__)
        if not feito:
            break
    return tratados


class Command(BaseCommand):
    help = "Envia as comunicações agendadas e processa o que chegou pelo WhatsApp."

    def add_arguments(self, parser):
        parser.add_argument("--uma-vez", action="store_true")
        parser.add_argument("--intervalo", type=float, default=15.0)

    def handle(self, *args, uma_vez=False, intervalo=15.0, **opts):
        if not recursos.ligado(recursos.AUTOMACAO):
            # Automações desligadas (ADR 0050): nada sai nem entra. Em serviço, fica parado
            # (sem reinícios em laço do contêiner); a retenção segue pela rotina diária.
            self.stdout.write("Automações desligadas (AUTOMACAO_HABILITADA=false): nada a fazer.")
            if not uma_vez:
                while True:
                    time.sleep(3600)
            return
        if uma_vez:
            total = 0
            while (n := rodada()) > 0:
                total += n
            manutencao.expirar_vencidas()
            self.stdout.write(f"{total} item(ns) tratado(s).")
            return
        connection.ensure_connection()
        with connection.cursor() as cur:
            cur.execute("LISTEN automacao")
        pg = connection.connection
        self.stdout.write("Worker da automação aguardando…")
        ultima = 0.0
        while True:
            while rodada() > 0:
                pass
            if time.monotonic() - ultima > MANUTENCAO_A_CADA:
                try:
                    manutencao.expirar_vencidas()
                    manutencao.reconciliar()
                    manutencao.purgar()
                except Exception:
                    log.exception("Manutenção da automação falhou")
                ultima = time.monotonic()
            select.select([pg.fileno()], [], [], intervalo)
            for _ in pg.notifies(timeout=0):
                pass
