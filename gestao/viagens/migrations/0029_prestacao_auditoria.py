"""Trilha de auditoria (trigger do banco) na prestação de contas."""

from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("viagens", "0028_prestacao_de_contas")]

    operations = [auditar_tabela("viagens_prestacaocontas"),
                  auditar_tabela("viagens_prestacaoservidor")]
