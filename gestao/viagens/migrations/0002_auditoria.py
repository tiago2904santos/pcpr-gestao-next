from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [
        ("viagens", "0001_initial"),
        ("plataforma", "0001_auditoria_outbox"),
    ]

    operations = [
        auditar_tabela(t)
        for t in ["viagens_oficio", "viagens_viajante", "viagens_trecho", "viagens_documento",
                  "viagens_numeracaoanual"]
    ]
