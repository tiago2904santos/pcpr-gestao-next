"""Micro-ônibus e caminhão viram um tipo de OS só, "Unidade móvel": as OS dos dois passam para
ele (as funções têm os mesmos códigos) e os tipos antigos são apagados."""

from django.db import migrations

from gestao.viagens.modelos_do_sistema import juntar, sincronizar


def juntar_tipos(apps, schema_editor):
    ModeloOS = apps.get_model("viagens", "ModeloOS")
    juntar(ModeloOS, apps.get_model("viagens", "OrdemServico"))
    sincronizar(ModeloOS, apps.get_model("viagens", "FuncaoOS"))


class Migration(migrations.Migration):

    dependencies = [("viagens", "0055_os_concordancia_e_funcoes_primeiro")]

    operations = [migrations.RunPython(juntar_tipos, migrations.RunPython.noop)]
