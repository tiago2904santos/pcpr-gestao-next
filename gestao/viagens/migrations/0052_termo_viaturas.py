import django.db.models.deletion
from django.db import migrations, models

from gestao.plataforma.auditoria import auditar_tabela


def copiar_viatura(apps, schema_editor):
    """A viatura única de cada termo passa a ser a primeira (e única) da lista — sem equipe
    marcada: com uma viatura só, todos vão nela (termos.Efetivo.viatura_de)."""
    TermoAutorizacao = apps.get_model("viagens", "TermoAutorizacao")
    TermoViatura = apps.get_model("viagens", "TermoViatura")
    TermoViatura.objects.bulk_create([
        TermoViatura(termo_id=t.pk, viatura_id=t.viatura_id, ordem=0)
        for t in TermoAutorizacao.objects.exclude(viatura=None).only("pk", "viatura_id")
    ])


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0016_textos_do_rt'),
        ('viagens', '0051_edicao_documento_modelos'),
    ]

    operations = [
        migrations.CreateModel(
            name='TermoViatura',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordem', models.PositiveSmallIntegerField(default=0)),
                ('servidores', models.ManyToManyField(blank=True, related_name='+', to='cadastros.servidor', verbose_name='quem vai nesta viatura')),
                ('termo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='viaturas', to='viagens.termoautorizacao')),
                ('viatura', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='cadastros.viatura')),
            ],
            options={
                'verbose_name': 'viatura do termo',
                'verbose_name_plural': 'viaturas do termo',
                'ordering': ['ordem', 'id'],
                'constraints': [models.UniqueConstraint(fields=('termo', 'viatura'), name='termo_viatura_unica')],
            },
        ),
        auditar_tabela("viagens_termoviatura"),
        auditar_tabela("viagens_termoviatura_servidores"),
        migrations.RunPython(copiar_viatura, migrations.RunPython.noop),
    ]
