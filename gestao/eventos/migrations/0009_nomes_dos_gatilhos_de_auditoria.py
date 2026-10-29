"""Os gatilhos da auditoria seguem o nome da tabela (`auditoria_<tabela>`).

A 0008 renomeou `eventos_servico` para `eventos_servicolegado` e trocou a tabela dos serviços
sugeridos do tipo pela que nasceu como `eventos_tipoevento_servicos_catalogo`; o gatilho
acompanha a tabela, mas manteve o nome antigo. Só o nome muda: a trilha já era gravada.
"""

from django.db import migrations

GATILHOS = (
    ("eventos_servicolegado", "auditoria_eventos_servico", "auditoria_eventos_servicolegado"),
    ("eventos_tipoevento_servicos_sugeridos", "auditoria_eventos_tipoevento_servicos_catalogo",
     "auditoria_eventos_tipoevento_servicos_sugeridos"),
)


class Migration(migrations.Migration):
    dependencies = [("eventos", "0008_catalogo_compartilhado")]

    operations = [
        migrations.RunSQL(
            sql=f'ALTER TRIGGER "{antigo}" ON "{tabela}" RENAME TO "{novo}";',
            reverse_sql=f'ALTER TRIGGER "{novo}" ON "{tabela}" RENAME TO "{antigo}";',
        )
        for tabela, antigo, novo in GATILHOS
    ]
