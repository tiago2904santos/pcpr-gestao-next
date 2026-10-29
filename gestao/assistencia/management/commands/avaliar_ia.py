"""Gabarito do AUT-91 (casos fictícios): validador de fatos, leitura por regra e assistente.

    python manage.py avaliar_ia

Sem rede e sem custo. Sai com erro se algum caso falhar (serve de portão antes de ligar um
uso no modo IA).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from gestao.assistencia.avaliacao import rodar


class Command(BaseCommand):
    help = "Roda o conjunto de avaliação da assistência (casos fictícios com gabarito)."

    def handle(self, *args, **opcoes):
        resultados = rodar.tudo()
        for r in resultados:
            estilo = self.style.SUCCESS if r.passou else self.style.ERROR
            self.stdout.write(estilo(f"{'ok ' if r.passou else 'ERRO'} {r.grupo:<10} "
                                     f"{r.nome:<28} {r.detalhe}"))
        falhas = [r for r in resultados if not r.passou]
        self.stdout.write(f"{len(resultados) - len(falhas)}/{len(resultados)} casos certos.")
        if falhas:
            raise CommandError(f"{len(falhas)} caso(s) fora do gabarito.")
