from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("plataforma", "0001_auditoria_outbox")]
    operations = [UnaccentExtension()]
