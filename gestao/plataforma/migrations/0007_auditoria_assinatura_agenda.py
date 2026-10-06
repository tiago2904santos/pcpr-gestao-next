from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("plataforma", "0006_assinatura_agenda")]

    operations = [auditar_tabela("plataforma_assinaturaagenda")]
