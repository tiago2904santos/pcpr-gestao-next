"""Preserva a edição da prestação e a importação desenvolvidas em paralelo."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("viagens", "0061_merge_importacao_anexo_viagem"),
        ("viagens", "0060_edicao_prestacao"),
    ]
    operations = []
