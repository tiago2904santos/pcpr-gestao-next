from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [
        ("identidade", "0001_initial"),
        ("plataforma", "0001_auditoria_outbox"),
    ]

    operations = [
        auditar_tabela("identidade_usuario"),
        auditar_tabela("auth_group"),
        auditar_tabela("identidade_usuario_groups"),
    ]
