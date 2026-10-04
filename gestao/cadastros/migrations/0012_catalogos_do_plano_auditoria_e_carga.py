"""Catálogos do plano de trabalho: trilha de auditoria e carga inicial.

A carga é a da referência (programas, horários e as 11 atividades com meta e recurso) e é
idempotente: cada item só entra se ainda não existir; renomear ou desativar depois não
volta sozinho.
"""

from django.db import migrations

from gestao.cadastros.carga import garantir_catalogos_do_plano
from gestao.plataforma.auditoria import auditar_tabela


def carregar(apps, schema_editor):
    garantir_catalogos_do_plano(apps)


class Migration(migrations.Migration):
    dependencies = [("cadastros", "0011_catalogos_do_plano")]

    operations = [
        auditar_tabela("cadastros_programasolicitante"),
        auditar_tabela("cadastros_horarioatendimento"),
        auditar_tabela("cadastros_atividadeplano"),
        auditar_tabela("cadastros_presetatividades"),
        auditar_tabela("cadastros_presetatividades_atividades"),
        migrations.RunPython(carregar, migrations.RunPython.noop),
    ]
