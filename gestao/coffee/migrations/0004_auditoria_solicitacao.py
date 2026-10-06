from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("coffee", "0003_solicitacao")]

    operations = [auditar_tabela(t) for t in ("coffee_solicitacao", "coffee_movimento")]
