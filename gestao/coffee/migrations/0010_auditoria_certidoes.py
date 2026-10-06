from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("coffee", "0009_certidoes")]

    operations = [auditar_tabela("coffee_certidao")]
