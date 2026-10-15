"""Operação policial no texto da OS real: Ref. "Diligências"; o dia da operação em dois
itens (o briefing, com o horário, e a permanência durante todo o dia); a volta sem os nomes."""

from django.db import migrations

from gestao.viagens.modelos_do_sistema import sincronizar


def sincronizar_tipos(apps, schema_editor):
    sincronizar(apps.get_model("viagens", "ModeloOS"), apps.get_model("viagens", "FuncaoOS"))


class Migration(migrations.Migration):

    dependencies = [("viagens", "0057_diario_tipo_unidade_movel")]

    operations = [migrations.RunPython(sincronizar_tipos, migrations.RunPython.noop)]
