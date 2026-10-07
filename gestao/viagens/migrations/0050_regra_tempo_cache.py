from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("viagens", "0049_data_manual_oficio")]

    operations = [
        migrations.AddField(
            model_name="distanciamunicipios",
            name="regra_tempo",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
