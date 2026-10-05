from django.db import migrations

from gestao.plataforma.auditoria import auditar_tabela


class Migration(migrations.Migration):
    dependencies = [("eventos", "0001_initial"), ("plataforma", "0005_rotina_do_dia")]

    operations = [auditar_tabela(t) for t in (
        "eventos_tipoevento", "eventos_tipoevento_servicos_sugeridos", "eventos_tipoeventoequipe",
        "eventos_servico", "eventos_equipe", "eventos_orgaoresponsavel", "eventos_unidademovel",
        "eventos_textodespacho")]
