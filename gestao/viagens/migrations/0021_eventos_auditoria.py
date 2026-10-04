"""Trilha de auditoria (trigger do banco) nas tabelas dos eventos do plano."""

from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela

TABELAS = ("viagens_eventoplano", "viagens_eventoplano_atividades", "viagens_eventodestino")


class Migration(migrations.Migration):
    dependencies = [("viagens", "0020_eventos_do_plano")]

    operations = [auditar_tabela(t) for t in TABELAS]
