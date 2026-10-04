"""Trilha de auditoria (trigger do banco) nas vias assinadas."""

from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("viagens", "0024_vias_assinadas")]

    operations = [auditar_tabela("viagens_viaassinada")]
