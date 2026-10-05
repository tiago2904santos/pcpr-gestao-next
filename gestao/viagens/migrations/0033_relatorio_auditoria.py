"""Trilha de auditoria (trigger do banco) no relatório técnico."""

from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("viagens", "0032_relatorio_tecnico")]

    operations = [auditar_tabela("viagens_relatoriotecnico")]
