"""Executa o esquema anterior e a migração real num banco descartável próprio."""

from copy import deepcopy
from datetime import date
from uuid import uuid4

import pytest
from django.contrib.contenttypes.management import inject_rename_contenttypes_operations
from django.contrib.contenttypes.models import ContentType
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor

from gestao.identidade.models import Usuario


@pytest.fixture
def migracao_isolada(django_db_blocker):
    # A única escrita na conexão original cria/remove o banco próprio. Evita flush
    # do banco da suíte e preserva as cargas iniciais dos demais testes.
    with django_db_blocker.unblock():
        yield


def test_migracao_preserva_referencias_ambiguidades_e_observacoes(migracao_isolada):
    alias = "default"
    nome = "test_catalogo_migracao_" + uuid4().hex[:12]
    original = connections[alias]
    configuracao = deepcopy(connection.settings_dict)
    configuracao["NAME"] = nome
    configuracao["CONN_MAX_AGE"] = 0
    # Só este banco recém-criado é removido no finally; nenhuma base existente é usada.
    with original._nodb_cursor() as cursor:
        cursor.execute(f"CREATE DATABASE {connection.ops.quote_name(nome)}")
    banco = original.copy(alias=alias)
    banco.settings_dict.update(configuracao)
    # As migrações antigas usam o alias default; isolá-lo também cobre suas cargas.
    connections[alias] = banco
    try:
        antes = [("eventos", "0007_viagem_gerada"),
                 ("cadastros", "0018_catalogo_e_fonte_dedicada")]
        executor = MigrationExecutor(banco)
        executor.migrate(antes)
        apps = executor.loader.project_state(antes).apps
        atividade = apps.get_model("cadastros", "AtividadePlano")
        servico = apps.get_model("eventos", "Servico")
        tipo = apps.get_model("eventos", "TipoEvento").objects.using(alias).first()
        usuario = apps.get_model("identidade", "Usuario").objects.using(alias).create(
            login="teste-migracao", email="migracao@teste.invalid", nome="Usuário sintético")
        tipo_permissao = apps.get_model("contenttypes", "ContentType").objects.using(alias).create(
            app_label="eventos", model="servico")
        grupo = apps.get_model("auth", "Group").objects.using(alias).create(name="Grupo migrado")
        permissoes = []
        for acao in ("add", "change", "view", "delete"):
            permissao = apps.get_model("auth", "Permission").objects.using(alias).create(
                content_type_id=tipo_permissao.pk, codename=f"{acao}_servico", name=acao)
            grupo.permissions.add(permissao)
            permissoes.append(permissao.pk)
        usuario.groups.add(grupo)
        usuario.user_permissions.add(permissoes[0])
        ContentType.objects.clear_cache()
        assert Usuario.objects.get(pk=usuario.pk).has_perm("eventos.change_servico")
        solicitacao = apps.get_model("eventos", "Solicitacao").objects.using(alias).create(
            criado_por_id=usuario.pk, data_solicitacao=date(2026, 10, 17), status="atendida")
        homonimo = atividade.objects.using(alias).create(
            codigo="INDEPENDENTE", nome="Registro homônimo", meta="Meta própria")
        antigo = servico.objects.using(alias).create(nome="Registro homônimo")
        inativo = servico.objects.using(alias).create(nome="Serviço inativo sintético", ativo=False)
        cin = servico.objects.using(alias).get(nome="Emissão de CIN")
        uso = apps.get_model("eventos", "SolicitacaoServico")
        ids_usos = []
        for item in (antigo, inativo, cin):
            ids_usos.append(uso.objects.using(alias).create(
                solicitacao_id=solicitacao.pk, servico_id=item.pk,
                observacao=f"Original {item.pk}").pk)
        tipo.servicos_sugeridos.add(antigo, inativo, cin)
        total_atividades = atividade.objects.using(alias).count()
        total_servicos = servico.objects.using(alias).count()
        cin_id = atividade.objects.using(alias).get(codigo="CIN").pk

        executor = MigrationExecutor(banco)
        depois = [("eventos", "0008_catalogo_compartilhado")]
        # Reproduz o hook real de manage.py migrate: RenameModel injeta mudança de CT.
        inject_rename_contenttypes_operations(plan=executor.migration_plan(depois), using=alias)
        executor.migrate(depois)
        apps = executor.loader.project_state(depois).apps
        atividade = apps.get_model("cadastros", "AtividadePlano")
        legado = apps.get_model("eventos", "ServicoLegado")
        usos = apps.get_model("eventos", "SolicitacaoServico").objects.using(alias)
        assert atividade.objects.using(alias).count() == total_atividades + total_servicos - 1
        assert legado.objects.using(alias).count() == total_servicos
        assert usos.filter(pk__in=ids_usos).count() == 3
        assert legado.objects.using(alias).get(pk=cin.pk).canonico_id == cin_id
        assert apps.get_model("contenttypes", "ContentType").objects.using(alias).get(
            app_label="eventos", model="servico").pk == tipo_permissao.pk
        assert set(grupo.permissions.values_list("pk", flat=True)) == set(permissoes)
        for acao in ("add", "change", "view", "delete"):
            assert Usuario.objects.get(pk=usuario.pk).has_perm(f"eventos.{acao}_servico")
        mapa = legado.objects.using(alias).get(pk=antigo.pk)
        assert mapa.canonico_id != homonimo.pk and mapa.criterio == "preservado_homonimo"
        assert mapa.vinculos_originais["tipos_evento"] == [tipo.pk]
        for item, pk in zip((antigo, inativo, cin), ids_usos, strict=True):
            atual = usos.get(pk=pk)
            assert atual.observacao == f"Original {item.pk}"
            assert atual.nome_registrado == item.nome
            assert atual.servico_id == legado.objects.using(alias).get(pk=item.pk).canonico_id
            assert atual.solicitacao_id == solicitacao.pk
        tipo = apps.get_model("eventos", "TipoEvento").objects.using(alias).get(pk=tipo.pk)
        assert tipo.servicos_sugeridos.count() == 3
        assert not legado.objects.using(alias).get(pk=inativo.pk).canonico.ativo
        assert apps.get_model("eventos", "Solicitacao").objects.using(alias).get(
            pk=solicitacao.pk).status == "atendida"
    finally:
        banco.close()
        connections[alias] = original
        ContentType.objects.clear_cache()
        with original._nodb_cursor() as cursor:
            cursor.execute(f"DROP DATABASE {connection.ops.quote_name(nome)}")
