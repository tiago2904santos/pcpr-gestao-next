from django.db import migrations, models

from gestao.plataforma.auditoria import auditar_tabela


def copiar_oficio(apps, schema_editor):
    """O ofício de cada termo passa a ser o primeiro (e único) dos ofícios vinculados."""
    TermoAutorizacao = apps.get_model("viagens", "TermoAutorizacao")
    Vinculo = TermoAutorizacao.oficios.through
    Vinculo.objects.bulk_create([
        Vinculo(termoautorizacao_id=t.pk, oficio_id=t.oficio_id)
        for t in TermoAutorizacao.objects.exclude(oficio=None).only("pk", "oficio_id")
    ])


class Migration(migrations.Migration):

    dependencies = [
        ('viagens', '0044_edicao_termo_modelos'),
    ]

    operations = [
        migrations.AddField(
            model_name='termoautorizacao',
            name='oficios',
            field=models.ManyToManyField(blank=True, related_name='termos_vinculados', to='viagens.oficio', verbose_name='ofícios vinculados'),
        ),
        auditar_tabela("viagens_termoautorizacao_oficios"),
        migrations.RunPython(copiar_oficio, migrations.RunPython.noop),
    ]
