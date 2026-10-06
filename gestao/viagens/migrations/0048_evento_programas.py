from django.db import migrations, models

from gestao.plataforma.auditoria import auditar_tabela


def copiar_programa(apps, schema_editor):
    """O programa de cada evento passa a ser o primeiro (e único) dos programas."""
    EventoPlano = apps.get_model("viagens", "EventoPlano")
    Vinculo = EventoPlano.programas.through
    Vinculo.objects.bulk_create([
        Vinculo(eventoplano_id=e.pk, programasolicitante_id=e.programa_id)
        for e in EventoPlano.objects.exclude(programa=None).only("pk", "programa_id")
    ])


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0016_textos_do_rt"),
        ("viagens", "0047_evento_efetivo_e_diarias"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventoplano",
            name="programas",
            field=models.ManyToManyField(blank=True, related_name="+",
                                         to="cadastros.programasolicitante",
                                         verbose_name="programas"),
        ),
        auditar_tabela("viagens_eventoplano_programas"),
        migrations.RunPython(copiar_programa, migrations.RunPython.noop),
    ]
