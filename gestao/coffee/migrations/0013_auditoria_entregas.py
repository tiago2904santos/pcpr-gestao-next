from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("coffee", "0012_entregas")]

    operations = [auditar_tabela("coffee_entrega")]
