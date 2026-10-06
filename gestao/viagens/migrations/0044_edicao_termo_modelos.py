from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('viagens', '0043_edicao_plano'),
    ]

    operations = [
        migrations.AddField(
            model_name='edicaotermo',
            name='modelos',
            field=models.JSONField(blank=True, default=dict, verbose_name='HTML do modelo por região, na edição'),
        ),
    ]
