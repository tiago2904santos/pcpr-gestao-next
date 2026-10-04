"""Trilha de auditoria (trigger do banco) na viagem, nos destinos e nos tipos dela."""

from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("viagens", "0026_viagem")]

    operations = [auditar_tabela("viagens_viagem"), auditar_tabela("viagens_viagemdestino"),
                  auditar_tabela("viagens_viagem_tipos")]
