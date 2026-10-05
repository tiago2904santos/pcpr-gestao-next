"""Trilha de auditoria (trigger do banco) no diário de bordo."""

from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("viagens", "0030_diario_de_bordo")]

    operations = [auditar_tabela("viagens_diariobordo"),
                  auditar_tabela("viagens_diariobordotrecho")]
