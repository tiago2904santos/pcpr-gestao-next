"""Simula ou aplica a recuperação conservadora do motorista dos rascunhos."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from gestao.plataforma.ambiente import OperacaoBloqueadaPorAmbiente
from gestao.viagens.recuperacao_motorista import (
    exigir_ambiente_de_recuperacao,
    rascunhos_afetados,
    recuperar_rascunho,
)


class Command(BaseCommand):
    help = "Simula a recuperação de motoristas; use --aplicar apenas em banco descartável."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true",
                            help="Grava a recuperação. Sem esta opção, apenas simula.")
        parser.add_argument("--oficio", type=int, action="append",
                            help="Restringe aos IDs informados; pode ser repetido.")

    def handle(self, *args, aplicar=False, oficio=None, **options):
        if aplicar:
            try:
                exigir_ambiente_de_recuperacao()
            except OperacaoBloqueadaPorAmbiente as exc:
                raise CommandError(str(exc)) from exc
        candidatos = rascunhos_afetados()
        if oficio:
            candidatos = candidatos.filter(pk__in=oficio)
        ids = list(candidatos.values_list("pk", flat=True))
        total = pendentes = 0
        self.stdout.write("APLICAÇÃO" if aplicar else "SIMULAÇÃO — nenhuma alteração será gravada")
        for pk in ids:
            resultado = recuperar_rascunho(pk, aplicar=aplicar)
            if not resultado.aplicavel:
                self.stdout.write(f"Ofício #{pk}: estado mudou; ignorado.")
                continue
            total += 1
            if resultado.selecao_manual:
                pendentes += 1
                mensagem = "limpar externo fantasma; selecione manualmente quem vai dirigir"
            elif resultado.evidencia_id:
                mensagem = (f"restaurar viajante #{resultado.motorista_id}; "
                            f"evidência de auditoria #{resultado.evidencia_id}")
            else:
                mensagem = "limpar externo fantasma; preservar seleção atual"
            self.stdout.write(f"Ofício #{pk}: {mensagem}.")
        self.stdout.write(f"Rascunhos tratados: {total}. Seleção manual pendente: {pendentes}.")
