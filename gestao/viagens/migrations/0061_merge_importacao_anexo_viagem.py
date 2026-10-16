"""Une as migrações independentes de importação e anexos da solicitação."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("viagens", "0059_anexo_da_viagem"),
        ("viagens", "0060_importacao_auditoria"),
    ]

    operations = []
