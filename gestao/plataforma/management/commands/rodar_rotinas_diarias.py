"""Rotinas diárias pelo cron (o middleware já as dispara no primeiro acesso do dia).
`--forcar` roda de novo mesmo que já tenham rodado hoje (os avisos não se repetem)."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from gestao.plataforma import rotinas


class Command(BaseCommand):
    help = "Roda as rotinas diárias (avisos de prazo da prestação de contas etc.)."

    def add_arguments(self, parser):
        parser.add_argument("--forcar", action="store_true")

    def handle(self, *args, forcar=False, **opts):
        if forcar:
            resultado = rotinas.rodar()
        elif not rotinas.rodar_se_for_hora():
            self.stdout.write("As rotinas de hoje já rodaram.")
            return
        else:
            from gestao.plataforma.models import RotinaDoDia
            resultado = RotinaDoDia.objects.latest("dia").resultado
        for nome, valor in resultado.items():
            self.stdout.write(f"{nome}: {valor}")
