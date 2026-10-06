from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("coffee", "0001_initial")]

    operations = [auditar_tabela(t) for t in (
        "coffee_fornecedor", "coffee_contrato", "coffee_termoaditivo", "coffee_lote",
        "coffee_lote_municipios", "coffee_configuracaooficio")]
