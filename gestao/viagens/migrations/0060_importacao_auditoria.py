from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("viagens", "0059_arquivoimportado_parteimportada_and_more")]
    operations = [auditar_tabela("viagens_arquivoimportado"),
                  auditar_tabela("viagens_parteimportada")]
