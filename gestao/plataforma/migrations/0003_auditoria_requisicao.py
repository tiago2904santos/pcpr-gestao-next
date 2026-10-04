from django.db import migrations


class Migration(migrations.Migration):
    """Índice por requisição: a linha do tempo de um documento junta, numa entrada só, o que
    um mesmo salvamento mudou na tabela principal e nas filhas (destinos, equipe…).

    CONCURRENTLY (fora de transação): toda escrita de negócio insere na trilha pelo trigger;
    construir o índice com trava pararia o sistema durante o deploy."""

    atomic = False
    dependencies = [("plataforma", "0002_extensoes")]
    operations = [
        migrations.RunSQL(
            sql=("CREATE INDEX CONCURRENTLY IF NOT EXISTS auditoria_evento_requisicao_idx "
                 "ON auditoria_evento (requisicao_id) WHERE requisicao_id IS NOT NULL;"),
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS auditoria_evento_requisicao_idx;",
        ),
    ]
