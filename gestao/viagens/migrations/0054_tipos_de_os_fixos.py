"""Os tipos de OS ficam fixos no código (sem cadastro na tela): nomes e ordem — OS padrão,
operação policial, micro-ônibus, caminhão, cerimonial — e a visita técnica do cerimonial."""

from django.db import migrations

from gestao.viagens.modelos_do_sistema import sincronizar


def sincronizar_tipos(apps, schema_editor):
    sincronizar(apps.get_model("viagens", "ModeloOS"), apps.get_model("viagens", "FuncaoOS"))


class Migration(migrations.Migration):

    dependencies = [("viagens", "0053_modelos_de_os")]

    operations = [migrations.RunPython(sincronizar_tipos, migrations.RunPython.noop)]
