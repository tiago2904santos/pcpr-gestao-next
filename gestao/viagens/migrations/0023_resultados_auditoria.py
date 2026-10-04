"""Trilha de auditoria (trigger do banco) nos resultados do plano."""

from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("viagens", "0022_resultados_do_plano")]

    operations = [auditar_tabela("viagens_resultadoatividade")]
