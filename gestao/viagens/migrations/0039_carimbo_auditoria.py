"""Trilha de auditoria (trigger do banco) nos carimbos do número de solicitação."""

from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("viagens", "0038_carimbo_da_solicitacao")]

    operations = [auditar_tabela("viagens_carimbosolicitacao")]
