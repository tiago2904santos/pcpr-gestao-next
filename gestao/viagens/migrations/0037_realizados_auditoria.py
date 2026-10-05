"""Trilha de auditoria (trigger do banco) nos trechos realizados da prestação."""

from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("viagens", "0036_trechos_realizados")]

    operations = [auditar_tabela("viagens_trechorealizado")]
