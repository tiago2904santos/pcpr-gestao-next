from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("publicacoes", "0001_initial"), ("plataforma", "0005_rotina_do_dia")]

    operations = [auditar_tabela(t) for t in (
        "publicacoes_publicacao", "publicacoes_andamento", "publicacoes_integrante",
        "publicacoes_unidaderesponsavel")]
