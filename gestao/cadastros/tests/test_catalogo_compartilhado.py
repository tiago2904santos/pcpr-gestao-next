"""Identidade comum, escopo e proteção dos usos (dados exclusivamente sintéticos)."""

from datetime import date

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from gestao.cadastros import services
from gestao.cadastros.fontes import atividades_e_servicos
from gestao.cadastros.models import AtividadePlano, PresetAtividades, Unidade
from gestao.eventos import catalogos
from gestao.eventos.forms import estrutura_do_post
from gestao.eventos.models import Servico, ServicoLegado, Solicitacao, SolicitacaoServico
from gestao.viagens import planos
from gestao.viagens.forms import FormularioPlano
from gestao.viagens.models import PlanoTrabalho

pytestmark = pytest.mark.django_db


def test_seed_migrado_tem_uma_so_identidade():
    cin = AtividadePlano.objects.get(codigo="CIN")
    legado = ServicoLegado.objects.get(nome="Emissão de CIN")
    assert legado.canonico_id == cin.pk
    assert legado.criterio == "equivalencia_carga_CIN"
    assert Servico._meta.concrete_model is AtividadePlano
    assert Servico.objects.get(pk=cin.pk) == cin
    assert Servico.objects.count() == AtividadePlano.objects.count()


def test_mesmo_cadastro_nos_dois_modulos_e_historico(usuario):
    usuario.is_superuser = True
    usuario.save()
    novo = catalogos.salvar(usuario, "servicos", {"nome": "Atendimento integrado sintético"})
    unidade = Unidade.objects.create(nome="Unidade sintética do catálogo")
    plano = PlanoTrabalho.objects.create(
        unidade=unidade, ano=2026, numero=9001, criado_por=usuario)
    plano.atividades.add(novo)
    assert "Atividades sem meta" in [aviso.rotulo for aviso in planos.avisos(plano)]
    solicitacao = Solicitacao.objects.create(criado_por=usuario, data_solicitacao=date.today())
    uso = SolicitacaoServico.objects.create(
        solicitacao=solicitacao, servico=novo, observacao="Observação histórica")
    total = AtividadePlano.objects.count()
    services.salvar_atividade(usuario, pk=novo.pk, nome="Atendimento integrado revisado",
                              meta="Atender os participantes.")
    uso.refresh_from_db()
    assert plano.atividades.get().pk == uso.servico_id == novo.pk
    assert uso.observacao == "Observação histórica"
    assert uso.servico.nome == "Atendimento integrado revisado"
    assert str(uso) == "Atendimento integrado sintético"
    assert AtividadePlano.objects.count() == total
    catalogos.alternar_ativo(usuario, "servicos", novo.pk)
    assert not atividades_e_servicos().filter(pk=novo.pk).exists()
    assert atividades_e_servicos(incluir=[novo.pk]).filter(pk=novo.pk).exists()
    assert FormularioPlano(plano=plano).fields["atividades"].queryset.filter(pk=novo.pk).exists()
    assert estrutura_do_post({f"servico_{novo.pk}": "1"})[0].servicos == {}
    assert novo.pk in estrutura_do_post({f"servico_{novo.pk}": "1"}, solicitacao)[0].servicos
    with pytest.raises(catalogos.CatalogoInvalido, match="Inativar"):
        catalogos.excluir(usuario, "servicos", novo.pk)
    with pytest.raises(services.CadastroInvalido, match="Desative"):
        services.excluir(usuario, AtividadePlano, novo.pk)


def test_exclusao_protege_conjunto_mesmo_sem_solicitacao(usuario):
    usuario.is_superuser = True
    usuario.save()
    item = catalogos.salvar(usuario, "servicos", {"nome": "Serviço só no conjunto"})
    conjunto = PresetAtividades.objects.create(nome="Conjunto sintético")
    conjunto.atividades.add(item)
    with pytest.raises(catalogos.CatalogoInvalido):
        catalogos.excluir(usuario, "servicos", item.pk)
    assert conjunto.atividades.get() == item


def test_proxy_nao_concede_permissao_de_manutencao(usuario):
    with pytest.raises(PermissionDenied):
        catalogos.salvar(usuario, "servicos", {"nome": "Sem autorização"})
    with pytest.raises(PermissionDenied):
        services.salvar_atividade(usuario, nome="Sem autorização", meta="Atender.")


def test_lista_conta_planos_e_solicitacoes_sem_multiplicar_joins_ou_n_mais_um(usuario):
    usuario.is_superuser = True
    usuario.save()
    item = AtividadePlano.objects.create(nome="Catálogo para contagem", meta="Atender.")
    unidade = Unidade.objects.create(nome="Unidade sintética de contagem")
    for numero in (991, 992):
        plano = PlanoTrabalho.objects.create(
            unidade=unidade, ano=2026, numero=numero, criado_por=usuario)
        plano.atividades.add(item)
        solicitacao = Solicitacao.objects.create(criado_por=usuario, data_solicitacao=date.today())
        SolicitacaoServico.objects.create(solicitacao=solicitacao, servico=item)
    for numero in (1, 2, 3):
        conjunto = PresetAtividades.objects.create(nome=f"Contagem {numero}")
        conjunto.atividades.add(item)
    cliente = Client()
    cliente.force_login(usuario)
    url = reverse("cadastros:atividades")
    with CaptureQueriesContext(connection) as antes:
        resposta = cliente.get(url)
    obj = next(obj for obj in resposta.context["page_obj"].object_list if obj.pk == item.pk)
    assert obj.usos == [(3, "conjunto,conjuntos"), (2, "plano,planos"),
                        (2, "solicitação,solicitações")]
    AtividadePlano.objects.bulk_create([
        AtividadePlano(codigo=f"CONTAGEM_{i}", nome=f"Contagem extra {i}") for i in range(5)])
    with CaptureQueriesContext(connection) as depois:
        resposta = cliente.get(url)
    assert resposta.status_code == 200 and len(depois) == len(antes)
