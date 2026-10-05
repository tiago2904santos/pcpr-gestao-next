from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("imprensa", "0001_initial"), ("plataforma", "0005_rotina_do_dia")]

    operations = [auditar_tabela(t) for t in ("imprensa_atendimento", "imprensa_andamento",
                                              "imprensa_integrante", "imprensa_veiculo")]
