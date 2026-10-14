from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("viagens", "0050_regra_tempo_cache")]

    operations = [
        migrations.AddField(
            model_name="edicaodocumento",
            name="modelos",
            field=models.JSONField(blank=True, default=dict,
                                   verbose_name="HTML do modelo por região, na edição"),
        ),
    ]
