"""Auditoria das tabelas de cadastro e carga da lista oficial de municípios (IBGE)."""

from django.db import migrations

from gestao.cadastros.carga import garantir_municipios
from gestao.plataforma.auditoria import auditar_tabela

TABELAS = [
    "cadastros_unidade", "cadastros_cargo", "cadastros_combustivel", "cadastros_servidor",
    "cadastros_viatura", "cadastros_tabeladiaria", "cadastros_configuracaoinstitucional",
    "cadastros_lotacao", "cadastros_modelotexto",
]


def carregar_municipios(apps, schema_editor):
    garantir_municipios(apps.get_model("cadastros", "Municipio"))


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0001_initial"),
        ("plataforma", "0001_auditoria_outbox"),
    ]

    operations = [
        migrations.RunPython(carregar_municipios, migrations.RunPython.noop),
        *[auditar_tabela(t) for t in TABELAS],
    ]
