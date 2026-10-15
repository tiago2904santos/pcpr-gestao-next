import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

from gestao.plataforma.auditoria import auditar_tabela
from gestao.viagens.modelos_do_sistema import CHAVE_DO_TIPO, semear


def semear_e_ligar(apps, schema_editor):
    """Os quatro modelos do sistema e cada OS apontando para o do seu tipo antigo
    (`padrao` fica sem modelo)."""
    ModeloOS = apps.get_model("viagens", "ModeloOS")
    FuncaoOS = apps.get_model("viagens", "FuncaoOS")
    OrdemServico = apps.get_model("viagens", "OrdemServico")
    pks = semear(ModeloOS, FuncaoOS)
    for tipo, chave in CHAVE_DO_TIPO.items():
        OrdemServico.objects.filter(tipo=tipo).update(modelo_id=pks[chave])


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0016_textos_do_rt"),
        ("viagens", "0052_termo_viaturas"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ModeloOS",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "chave",
                    models.SlugField(blank=True, max_length=40, null=True, unique=True),
                ),
                (
                    "nome",
                    models.CharField(max_length=60, unique=True, verbose_name="nome"),
                ),
                (
                    "referencia",
                    models.CharField(max_length=120, verbose_name="referência (Ref.:)"),
                ),
                ("ida", models.TextField(blank=True, verbose_name="ida")),
                (
                    "ida_e_antes",
                    models.TextField(
                        blank=True, verbose_name="ida e véspera no mesmo dia"
                    ),
                ),
                (
                    "antes",
                    models.TextField(blank=True, verbose_name="dias antes do evento"),
                ),
                ("evento", models.TextField(blank=True, verbose_name="dias do evento")),
                (
                    "depois",
                    models.TextField(blank=True, verbose_name="dias depois do evento"),
                ),
                (
                    "depois_e_volta",
                    models.TextField(
                        blank=True, verbose_name="dia seguinte e volta no mesmo dia"
                    ),
                ),
                ("volta", models.TextField(blank=True, verbose_name="volta")),
                (
                    "justificativas",
                    models.TextField(blank=True, verbose_name="justificativas"),
                ),
                ("finalidade", models.TextField(blank=True, verbose_name="finalidade")),
                ("ativo", models.BooleanField(default=True, verbose_name="ativo")),
                (
                    "ordem",
                    models.PositiveSmallIntegerField(default=100, verbose_name="ordem"),
                ),
                (
                    "padrao_sistema",
                    models.BooleanField(
                        default=False, verbose_name="padrão do sistema"
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "modelo de OS",
                "verbose_name_plural": "modelos de OS",
                "ordering": ["ordem", "nome"],
            },
        ),
        migrations.AddField(
            model_name="ordemservico",
            name="data_evento_fim",
            field=models.DateField(blank=True, null=True, verbose_name="fim do evento"),
        ),
        migrations.AddField(
            model_name="ordemservico",
            name="data_evento_inicio",
            field=models.DateField(
                blank=True, null=True, verbose_name="início do evento"
            ),
        ),
        migrations.AddField(
            model_name="ordemservico",
            name="hora",
            field=models.TimeField(
                blank=True, null=True, verbose_name="horário do briefing"
            ),
        ),
        migrations.CreateModel(
            name="FuncaoOS",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("codigo", models.SlugField(max_length=30)),
                ("nome", models.CharField(max_length=40, verbose_name="nome")),
                (
                    "icone",
                    models.CharField(blank=True, max_length=40, verbose_name="ícone"),
                ),
                ("texto", models.TextField(verbose_name="atribuição")),
                ("ordem", models.PositiveSmallIntegerField(default=0)),
                (
                    "modelo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="funcoes",
                        to="viagens.modeloos",
                    ),
                ),
            ],
            options={
                "verbose_name": "função de OS",
                "verbose_name_plural": "funções de OS",
                "ordering": ["ordem", "id"],
            },
        ),
        migrations.AddField(
            model_name="ordemservico",
            name="modelo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ordens",
                to="viagens.modeloos",
                verbose_name="modelo",
            ),
        ),
        migrations.AddConstraint(
            model_name="ordemservico",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("data_evento_fim__isnull", True),
                    models.Q(
                        ("data_evento_fim__gte", models.F("data_evento_inicio")),
                        ("data_evento_inicio__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="os_evento_ordenado",
            ),
        ),
        migrations.AddConstraint(
            model_name="funcaoos",
            constraint=models.UniqueConstraint(
                fields=("modelo", "codigo"), name="funcaoos_codigo_unico"
            ),
        ),
        auditar_tabela("viagens_modeloos"),
        auditar_tabela("viagens_funcaoos"),
        migrations.RunPython(semear_e_ligar, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="ordemservico",
            name="tipo",
        ),
    ]
