import pytest

from gestao.cadastros.dominio_catalogo import (
    ConflitoDeCadastro,
    codigo_da_atividade,
    normalizar_da_origem,
    reconciliar,
)


def test_codigo_estavel_e_sufixos():
    assert codigo_da_atividade("Ação pública", {"ACAO_PUBLICA"}) == "ACAO_PUBLICA_2"
    assert codigo_da_atividade("", set()) == "ATIVIDADE"


def test_origem_sem_alteracao_preserva_edicao_local():
    assert reconciliar({"nome": "Base"}, {"nome": "Local"}, {"nome": "Base"}) == {}


def test_alteracao_concorrente_nao_sobrescreve():
    with pytest.raises(ConflitoDeCadastro, match="nome"):
        reconciliar({"nome": "Base"}, {"nome": "Local"}, {"nome": "Origem"})


def test_mesma_alteracao_e_idempotente():
    assert reconciliar({"nome": "Base"}, {"nome": "Novo"}, {"nome": "Novo"}) == {}
    assert reconciliar({"ativo": True}, {"ativo": True}, {"ativo": False}) == {"ativo": False}


def test_plano_avisa_meta_vazia_sem_inventar_complemento():
    from gestao.viagens.dominio.plano_trabalho import DadosPlano, avisos

    dados = DadosPlano(tem_atividades=True, atividades_sem_meta=["Serviço de Eventos"])
    aviso = next(aviso for aviso in avisos(dados) if aviso.rotulo == "Atividades sem meta")
    assert "Serviço de Eventos" in aviso.mensagem
    assert "Atividades e serviços" in aviso.mensagem and aviso.secao == "atividades"


def test_origem_reutiliza_regras_de_documentos_e_placa():
    assert normalizar_da_origem("servidor", {
        "cpf": "529.982.247-25", "telefone": "(41) 99999-3333", "rg": "12.345-6"}) == {
            "cpf": "52998224725", "telefone": "41999993333", "rg": "123456"}
    assert normalizar_da_origem("viatura", {"placa": "abc-1234"}) == {"placa": "ABC1234"}
    with pytest.raises(ValueError, match="CPF inválido"):
        normalizar_da_origem("servidor", {"cpf": "11111111111"})


@pytest.mark.parametrize("valores", [{"nome": {"texto": "inválido"}}, {"ativo": "false"}])
def test_payload_tem_tipos_explicitos(valores):
    with pytest.raises(ValueError, match="Tipo inválido"):
        normalizar_da_origem("servidor", valores)
