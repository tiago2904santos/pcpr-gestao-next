from django.db import migrations, models

from gestao.plataforma.auditoria import auditar_tabela


def copiar_programa(apps, schema_editor):
    """O programa de cada plano passa a ser o primeiro (e único) dos programas."""
    PlanoTrabalho = apps.get_model("viagens", "PlanoTrabalho")
    Vinculo = PlanoTrabalho.programas.through
    Vinculo.objects.bulk_create([
        Vinculo(planotrabalho_id=p.pk, programasolicitante_id=p.programa_id)
        for p in PlanoTrabalho.objects.exclude(programa=None).only("pk", "programa_id")
    ])


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0016_textos_do_rt"),
        ("viagens", "0045_termo_oficios"),
    ]

    operations = [
        migrations.AddField(
            model_name="planotrabalho",
            name="programas",
            field=models.ManyToManyField(blank=True, related_name="+", to="cadastros.programasolicitante", verbose_name="programas"),
        ),
        auditar_tabela("viagens_planotrabalho_programas"),
        migrations.RunPython(copiar_programa, migrations.RunPython.noop),
    ]
