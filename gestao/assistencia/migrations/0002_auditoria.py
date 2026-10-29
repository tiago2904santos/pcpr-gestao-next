"""Trilha do banco nas tabelas de ESTADO da assistência por IA.

Ficam de fora, de propósito, as de conteúdo com retenção (orientação escrita no pedido,
texto sugerido, avisos do validador e texto aplicado): a trilha é imutável e guardaria para
sempre o que só deve viver o prazo de retenção (ADR 0048)."""

from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela

TABELAS = [
    "assistencia_configuracaouso", "assistencia_orcamentoia",
    "assistencia_pedidosugestao", "assistencia_sugestao",
]


class Migration(migrations.Migration):
    dependencies = [
        ("assistencia", "0001_initial"),
        ("plataforma", "0001_auditoria_outbox"),
    ]

    operations = [auditar_tabela(t) for t in TABELAS]
