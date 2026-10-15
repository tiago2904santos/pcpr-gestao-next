"""Textos dos tipos de OS: concordância com o número de servidores e, no caminhão e no
micro-ônibus, o deslocamento de cada um com a sua função antes dos itens dos dias."""

from django.db import migrations

from gestao.viagens.modelos_do_sistema import sincronizar


def sincronizar_tipos(apps, schema_editor):
    sincronizar(apps.get_model("viagens", "ModeloOS"), apps.get_model("viagens", "FuncaoOS"))


class Migration(migrations.Migration):

    dependencies = [("viagens", "0054_tipos_de_os_fixos")]

    operations = [migrations.RunPython(sincronizar_tipos, migrations.RunPython.noop)]
