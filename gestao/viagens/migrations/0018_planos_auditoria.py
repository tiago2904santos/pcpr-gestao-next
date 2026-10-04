"""Trilha de auditoria (trigger do banco) nas tabelas do plano de trabalho."""

from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela

TABELAS = (
    "viagens_planotrabalho", "viagens_planotrabalho_oficios",
    "viagens_planotrabalho_atividades", "viagens_planodestino", "viagens_efetivoplano",
    "viagens_numeracaoplano", "viagens_lacunaplano",
)


class Migration(migrations.Migration):
    dependencies = [("viagens", "0017_planos_de_trabalho")]

    operations = [auditar_tabela(t) for t in TABELAS]
