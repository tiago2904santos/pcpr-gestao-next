"""Trilha do banco nas tabelas de estado da automação.

Ficam de fora, de propósito, as de conteúdo com retenção (texto das mensagens, nome de
perfil, corpo bruto do webhook): a trilha é imutável e guardaria para sempre o que só deve
viver o prazo de retenção (ADR 0047)."""

from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela

# Fora: contatos e testadores (telefone, wa_id e BSUID ficariam na trilha imutável para
# sempre); o histórico deles é o `EventoContato`, auditado e sem o número.
TABELAS = [
    "automacao_chaveautomacao", "automacao_comunicacao",
    "automacao_tentativaentrega", "automacao_statusentrega", "automacao_recebimento",
    "automacao_excecaoautomacao",
]


class Migration(migrations.Migration):
    dependencies = [
        ("automacao", "0001_initial"),
        ("plataforma", "0001_auditoria_outbox"),
    ]

    operations = [auditar_tabela(t) for t in TABELAS]
