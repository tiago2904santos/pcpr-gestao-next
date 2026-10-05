"""Carga inicial dos catálogos de Eventos Sociais, a mesma da referência
(`cadastros/management/commands/seed_initial_data.py`). Idempotente; não apaga nada."""

from django.db import migrations

TIPOS = ("PCPR na Comunidade", "Justiça no Bairro", "Paraná em Ação", "Demafe",
         "Inauguração/Solenidade", "Evento", "Palestra", "Reunião", "Visita", "Capacitação",
         "Feira")
SERVICOS = ("Emissão de CIN", "Coleta de digitais", "Atendimento social", "Orientação jurídica",
            "Fotografia para documento")
ORGAOS = ("Instituto de Identificação do Paraná", "Delegacia-Geral", "Delegacia-Geral Adjunta")
EQUIPES = ("Alfa", "Bravo", "Charlie")


def carregar(apps, schema_editor):
    for modelo, nomes in (("TipoEvento", TIPOS), ("Servico", SERVICOS),
                          ("OrgaoResponsavel", ORGAOS), ("Equipe", EQUIPES)):
        Modelo = apps.get_model("eventos", modelo)
        for nome in nomes:
            if not Modelo.objects.filter(nome__iexact=nome).exists():
                Modelo.objects.create(nome=nome)


class Migration(migrations.Migration):
    dependencies = [("eventos", "0002_auditoria")]

    operations = [migrations.RunPython(carregar, migrations.RunPython.noop)]
