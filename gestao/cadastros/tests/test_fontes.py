"""Contrato local da futura origem: identidades, propriedade, conflitos e inativação."""

import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from gestao.cadastros import services
from gestao.cadastros.dominio_catalogo import ConflitoDeCadastro
from gestao.cadastros.fontes import atualizar_da_fonte, fonte_local, vincular_fonte
from gestao.cadastros.models import AtividadePlano, Cargo, Servidor, Unidade, Viatura

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(django_user_model):
    return django_user_model.objects.create_superuser(
        "admin-fonte", "fonte@teste.invalid", None, nome="Administrador sintético")


@pytest.mark.parametrize("entidade,modelo,dados,campo,valor", [
    ("servidor", Servidor, {"nome": "Servidor sintético"}, "nome", "Servidor atualizado"),
    ("viatura", Viatura, {"placa": "ABC1D23"}, "modelo", "Modelo atualizado"),
    ("unidade", Unidade, {"nome": "Unidade sintética"}, "sigla", "LAB"),
    ("cargo", Cargo, {"nome": "Cargo sintético"}, "nome", "Cargo atualizado"),
    ("atividade", AtividadePlano, {"nome": "Ação sintética", "meta": "Meta local"},
     "nome", "Ação atualizada"),
])
def test_identidade_local_e_inativacao_preservadas(admin, entidade, modelo, dados, campo, valor):
    registro = modelo.objects.create(**dados)
    vinculo = vincular_fonte(admin, entidade=entidade, registro_id=registro.pk,
                            fonte="origem-lab", identificador_externo="ID-47",
                            campos_externos=[campo, "ativo"])
    atualizado = atualizar_da_fonte(admin, vinculo_id=vinculo.pk, revisao="r1",
                                    valores={campo: valor, "ativo": False})
    assert atualizado.pk == registro.pk and getattr(atualizado, campo) == valor
    assert not fonte_local.consultar(entidade).filter(pk=registro.pk).exists()
    assert fonte_local.consultar(entidade, incluir=[registro.pk]).get(pk=registro.pk) == atualizado
    if entidade == "atividade":
        assert atualizado.meta == "Meta local" and atualizado.codigo == registro.codigo
    atualizar_da_fonte(admin, vinculo_id=vinculo.pk, revisao="r1",
                       valores={campo: valor, "ativo": False})
    assert modelo.objects.filter(pk=registro.pk).count() == 1
    with pytest.raises(services.CadastroInvalido, match="fonte dedicada"):
        services.excluir(admin, modelo, registro.pk)
    with pytest.raises(ValidationError):
        vincular_fonte(admin, entidade=entidade, registro_id=registro.pk,
                       fonte="outra-origem", identificador_externo="OUTRO",
                       campos_externos=[campo])


def test_conflito_aborta_toda_atualizacao(admin):
    cargo = Cargo.objects.create(nome="Cargo base")
    vinculo = vincular_fonte(admin, entidade="cargo", registro_id=cargo.pk,
                            fonte="lab", identificador_externo="C1",
                            campos_externos=["nome", "ativo"])
    # Simula edição válida concorrente anterior ao protocolo externo.
    Cargo.objects.filter(pk=cargo.pk).update(nome="Edição local válida")
    with pytest.raises(ConflitoDeCadastro, match="nome"):
        atualizar_da_fonte(admin, vinculo_id=vinculo.pk, revisao="r1",
                           valores={"nome": "Outra edição externa", "ativo": False})
    cargo.refresh_from_db()
    vinculo.refresh_from_db()
    assert cargo.nome == "Edição local válida" and cargo.ativo
    assert vinculo.revisao == ""


def test_crud_local_diz_como_resolver_campo_da_origem(admin):
    unidade = Unidade.objects.create(nome="Unidade externa", sigla="EXT")
    vincular_fonte(admin, entidade="unidade", registro_id=unidade.pk,
                   fonte="lab", identificador_externo="U1", campos_externos=["nome"])
    with pytest.raises(services.CadastroInvalido, match="Revise o conflito"):
        services.salvar_unidade(admin, pk=unidade.pk, nome="Alteração local")
    services.salvar_unidade(admin, pk=unidade.pk, nome=unidade.nome, sigla="LOCAL")
    unidade.refresh_from_db()
    assert unidade.sigla == "LOCAL"
    with pytest.raises(services.CadastroInvalido, match="fonte dedicada"):
        services.excluir(admin, Unidade, unidade.pk)


def test_sem_permissao_e_complementos_locais_nao_sao_importados(usuario, admin):
    cargo = Cargo.objects.create(nome="Cargo somente local")
    with pytest.raises(PermissionDenied):
        vincular_fonte(usuario, entidade="cargo", registro_id=cargo.pk,
                       fonte="lab", identificador_externo="C2", campos_externos=["nome"])
    with pytest.raises(ValidationError, match="campos"):
        vincular_fonte(admin, entidade="cargo", registro_id=cargo.pk,
                       fonte="lab", identificador_externo="C2", campos_externos=["padrao"])


def test_identificador_externo_nao_cria_segunda_identidade_local(admin):
    primeiro = Cargo.objects.create(nome="Cargo externo primeiro")
    segundo = Cargo.objects.create(nome="Cargo externo segundo")
    vinculo = vincular_fonte(admin, entidade="cargo", registro_id=primeiro.pk,
                            fonte="lab", identificador_externo="C-UNICO", campos_externos=["nome"])
    with pytest.raises(ValidationError):
        vincular_fonte(admin, entidade="cargo", registro_id=segundo.pk,
                       fonte="lab", identificador_externo="C-UNICO", campos_externos=["nome"])
    atualizar_da_fonte(admin, vinculo_id=vinculo.pk, revisao="r1", valores={"nome": "Cargo novo"})
    with pytest.raises(ValidationError, match="outros valores"):
        atualizar_da_fonte(admin, vinculo_id=vinculo.pk, revisao="r1",
                           valores={"nome": "Payload divergente"})


def test_ownership_persistido_e_revalidado_antes_de_escrever(admin):
    cargo = Cargo.objects.create(nome="Cargo com vínculo inconsistente")
    vinculo = vincular_fonte(admin, entidade="cargo", registro_id=cargo.pk,
                            fonte="lab", identificador_externo="C-INCONSISTENTE",
                            campos_externos=["nome"])
    type(vinculo).objects.filter(pk=vinculo.pk).update(campos_externos=["padrao"])
    with pytest.raises(ValidationError, match="campos locais"):
        atualizar_da_fonte(admin, vinculo_id=vinculo.pk, revisao="r1", valores={"padrao": True})
    cargo.refresh_from_db()
    assert not cargo.padrao
