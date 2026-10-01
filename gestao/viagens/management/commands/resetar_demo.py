"""Zera o banco do PREVIEW (migrações + flush) e recria o dataset DEMO.

Recusa rodar fora de PREVIEW (e TEST). A trilha de auditoria (`auditoria_evento`) é
append-only e não é apagada: o reset fica registrado nela.
"""

from __future__ import annotations

import time

from django.core.management import call_command
from django.core.management.base import BaseCommand

from gestao.plataforma import ambiente


class Command(BaseCommand):
    help = "Recria o banco DEMO do zero (somente PREVIEW) e roda semear_demo."

    def add_arguments(self, parser):
        parser.add_argument("--escala", type=float, default=1.0)
        parser.add_argument("--sem-documentos", action="store_true")

    def handle(self, *args, escala: float, sem_documentos: bool, **opts):
        ambiente.exigir_ambiente_de_demonstracao("resetar_demo")
        inicio = time.perf_counter()
        call_command("migrate", interactive=False, verbosity=0)
        call_command("flush", interactive=False, verbosity=0)  # post_migrate recria os papéis
        call_command("semear_demo", escala=escala, sem_documentos=sem_documentos,
                     stdout=self.stdout)
        self.stdout.write(f"Reset completo em {time.perf_counter() - inicio:.1f}s.")
