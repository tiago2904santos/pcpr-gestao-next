"""Trilha de auditoria (trigger do banco) nos anexos da prestação."""

from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("viagens", "0034_anexos_da_prestacao")]

    operations = [auditar_tabela("viagens_anexoprestacao")]
