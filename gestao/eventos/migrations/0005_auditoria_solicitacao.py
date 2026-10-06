from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("eventos", "0004_solicitacao")]

    operations = [auditar_tabela(t) for t in (
        "eventos_solicitacao", "eventos_solicitacaoservico", "eventos_solicitacaoequipe",
        "eventos_anexosolicitacao", "eventos_movimento")]
