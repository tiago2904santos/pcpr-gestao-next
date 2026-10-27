from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('viagens', '0064_modelos_da_edicao_os_e_plano'),
    ]

    operations = [
        migrations.AddField(
            model_name='oficio',
            name='atualizado_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL,
                                    related_name='+', to=settings.AUTH_USER_MODEL),
        ),
    ]
