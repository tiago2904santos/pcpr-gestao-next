"""Migra identidades sem alterar IDs de atividades nem documentos históricos.

O legado e seu mapa ficam preservados; rollback após novos usos exige reconciliação.
"""

import django.db.models.deletion
from django.db import migrations, models

from gestao.plataforma.auditoria import auditar_tabela

CIN = (
    "Confecção da Carteira de Identidade Nacional (CIN)",
    "Ampliar o acesso ao documento oficial de identificação civil, garantindo cidadania e "
    "inclusão social à população atendida.",
    "Kit de captura biométrica, estação de atendimento, conectividade e equipe técnica para "
    "triagem e emissão.",
)


def preservar_permissoes(apps, schema_editor):
    # migrate injeta RenameContentType após RenameModel. O modelo legado não deve
    # tomar a identidade/permissões de Servico: esse nome passa a ser o proxy comum.
    ContentType = apps.get_model("contenttypes", "ContentType")
    banco = schema_editor.connection.alias
    tipos = ContentType.objects.using(banco).filter(app_label="eventos")
    if not tipos.filter(model="servico").exists():
        tipos.filter(model="servicolegado").update(model="servico")


def migrar_catalogo(apps, schema_editor):
    Atividade = apps.get_model("cadastros", "AtividadePlano")
    Legado = apps.get_model("eventos", "ServicoLegado")
    Uso = apps.get_model("eventos", "SolicitacaoServico")
    Tipo = apps.get_model("eventos", "TipoEvento")
    banco = schema_editor.connection.alias
    codigos = set(Atividade.objects.using(banco).values_list("codigo", flat=True))
    for antigo in Legado.objects.using(banco).order_by("pk"):
        if antigo.canonico_id:
            continue
        # Equivalência explícita das cargas versionadas; não deduplicar só por nome.
        candidato = (Atividade.objects.using(banco).filter(
            codigo="CIN", nome=CIN[0], meta=CIN[1], recurso=CIN[2], ativo=True).first()
            if antigo.nome == "Emissão de CIN" and antigo.ativo else None)
        criterio = "equivalencia_carga_CIN"
        if candidato is None:
            criterio = ("preservado_homonimo" if Atividade.objects.using(banco).filter(
                nome__iexact=antigo.nome).exists() else "preservado_sem_equivalencia")
            codigo = f"EVENTO_{antigo.pk}"
            while codigo in codigos:
                codigo = "E_" + codigo
            codigos.add(codigo)
            candidato = Atividade.objects.using(banco).create(
                codigo=codigo, nome=antigo.nome, ativo=antigo.ativo, meta="", recurso="")
            Atividade.objects.using(banco).filter(pk=candidato.pk).update(
                criado_em=antigo.criado_em, atualizado_em=antigo.atualizado_em)
        usos = list(Uso.objects.using(banco).filter(servico_id=antigo.pk)
                    .values("id", "solicitacao_id", "observacao"))
        tipos = list(Tipo.objects.using(banco).filter(servicos_sugeridos=antigo)
                     .values_list("pk", flat=True))
        antigo.canonico_id, antigo.criterio = candidato.pk, criterio
        antigo.vinculos_originais = {"solicitacoes": usos, "tipos_evento": tipos}
        antigo.save(using=banco, update_fields=["canonico", "criterio", "vinculos_originais"])
        Uso.objects.using(banco).filter(servico_id=antigo.pk).update(
            catalogo_id=candidato.pk, nome_registrado=antigo.nome)
        for tipo in Tipo.objects.using(banco).filter(pk__in=tipos):
            tipo.servicos_catalogo.add(candidato)
    if Uso.objects.using(banco).filter(catalogo_id=None).exists():
        raise RuntimeError("Há uso de serviço sem identidade canônica; migração interrompida.")


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0018_catalogo_e_fonte_dedicada"),
        ("eventos", "0007_viagem_gerada"),
    ]

    operations = [
        migrations.RenameModel(old_name="Servico", new_name="ServicoLegado"),
        migrations.RunPython(preservar_permissoes),
        migrations.AlterModelOptions(name="servicolegado", options={
            "ordering": ["nome"], "default_permissions": ()}),
        migrations.AddField(model_name="servicolegado", name="canonico", field=models.ForeignKey(
            to="cadastros.atividadeplano", null=True,
            on_delete=django.db.models.deletion.PROTECT, related_name="origens_eventos")),
        migrations.AddField(model_name="servicolegado", name="criterio",
                            field=models.CharField(max_length=80, default="")),
        migrations.AddField(model_name="servicolegado", name="vinculos_originais",
                            field=models.JSONField(default=dict)),
        migrations.AddField(model_name="solicitacaoservico", name="catalogo",
                            field=models.ForeignKey(
                                to="cadastros.atividadeplano", null=True, related_name="+",
                                on_delete=django.db.models.deletion.PROTECT)),
        migrations.AddField(model_name="solicitacaoservico", name="nome_registrado",
                            field=models.CharField(
                                "serviço no registro", max_length=255, blank=True)),
        migrations.AddField(model_name="tipoevento", name="servicos_catalogo",
                            field=models.ManyToManyField(
                                to="cadastros.atividadeplano", blank=True, related_name="+",
                                verbose_name="serviços sugeridos")),
        # Auditoria cobre inclusive os INSERTs do mapa, antes da cópia.
        auditar_tabela("eventos_tipoevento_servicos_catalogo"),
        migrations.RunPython(migrar_catalogo),
        migrations.RunSQL("SET CONSTRAINTS ALL IMMEDIATE", migrations.RunSQL.noop),
        migrations.RemoveConstraint(model_name="solicitacaoservico",
                                    name="eventos_solic_servico_unico"),
        migrations.RemoveField(model_name="solicitacaoservico", name="servico"),
        migrations.RenameField(model_name="solicitacaoservico", old_name="catalogo",
                               new_name="servico"),
        migrations.AlterField(model_name="solicitacaoservico", name="servico",
                              field=models.ForeignKey(
                                  to="cadastros.atividadeplano", related_name="solicitacoes",
                                  on_delete=django.db.models.deletion.PROTECT)),
        migrations.AddConstraint(model_name="solicitacaoservico", constraint=models.UniqueConstraint(
            fields=["solicitacao", "servico"], name="eventos_solic_servico_unico")),
        migrations.RemoveField(model_name="tipoevento", name="servicos_sugeridos"),
        migrations.RenameField(model_name="tipoevento", old_name="servicos_catalogo",
                               new_name="servicos_sugeridos"),
        migrations.AlterField(model_name="servicolegado", name="canonico", field=models.ForeignKey(
            to="cadastros.atividadeplano", related_name="origens_eventos",
            on_delete=django.db.models.deletion.PROTECT)),
        migrations.AlterField(model_name="servicolegado", name="criterio",
                              field=models.CharField(max_length=80)),
        migrations.CreateModel(name="Servico", fields=[], options={
            "verbose_name": "serviço", "verbose_name_plural": "serviços",
            "proxy": True, "ordering": ["nome"], "indexes": [], "constraints": [],
        }, bases=("cadastros.atividadeplano",)),
    ]
