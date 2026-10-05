from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("palestras", "0001_initial"), ("plataforma", "0005_rotina_do_dia")]

    operations = [auditar_tabela(t) for t in (
        "palestras_palestra", "palestras_palestra_temas", "palestras_palestra_palestrantes",
        "palestras_andamento", "palestras_respostaenviada", "palestras_tema",
        "palestras_palestrante", "palestras_respostapadrao")]
