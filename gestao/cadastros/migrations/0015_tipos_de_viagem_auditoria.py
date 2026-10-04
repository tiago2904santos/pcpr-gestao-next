"""Trilha de auditoria (trigger do banco) nos tipos de viagem."""

from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("cadastros", "0014_tipos_de_viagem")]

    operations = [auditar_tabela("cadastros_tipoviagem")]
