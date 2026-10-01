"""Popula LAB/DEV com o cenário fictício (apaga dados de negócio antes).

Bloqueado fora de LAB/DEV/TEST (gestao.plataforma.ambiente).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from gestao.plataforma import ambiente
from gestao.plataforma.auditoria import contexto


class Command(BaseCommand):
    help = "Recria dados fictícios de demonstração (somente LAB/DEV)."

    def add_arguments(self, parser):
        parser.add_argument("--senha", default="senha-local-123")

    def handle(self, *args, senha: str, **opts):
        ambiente.exigir_ambiente_destrutivo("semear_dev")
        from gestao.viagens.tests.cenarios import cenario_completo

        with transaction.atomic(), contexto(usuario_id=None, requisicao_id="semear_dev"):
            with connection.cursor() as cur:
                cur.execute(
                    "TRUNCATE viagens_historico, viagens_documento, viagens_trecho, "
                    "viagens_viajante, viagens_oficio, viagens_numeracaoanual, "
                    "cadastros_lotacao, cadastros_configuracaoinstitucional, cadastros_servidor, "
                    "cadastros_viatura, cadastros_cargo, cadastros_combustivel, "
                    "cadastros_tabeladiaria, cadastros_modelotexto, cadastros_unidade, "
                    "plataforma_outbox, identidade_tentativaacesso, "
                    "identidade_usuario_groups, identidade_usuario_user_permissions, "
                    "identidade_usuario CASCADE"
                )
            cenario = cenario_completo(senha=senha)
        self.stdout.write(self.style.SUCCESS(
            f"Cenário criado. Usuários: {', '.join(cenario.usuarios)} (senha: {senha})."))
