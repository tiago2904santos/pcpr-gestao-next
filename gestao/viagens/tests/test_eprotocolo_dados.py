"""Projeção RS-01 com objetos em memória, sem setup Django ou banco."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from gestao.viagens.eprotocolo import projetar_dados_eprotocolo


def _oficio(**alteracoes):
    return SimpleNamespace(**{
        "pk": 10, "situacao": "emitido", "data_oficio": date(2026, 10, 7),
        "marcador": "", "numero_formatado": "10/2026", "protocolo_formatado": "12.345.678-9",
        "protocolo_origem": "manual", "sede_id": 1, "motivo": "Motivo atual alterado",
        "arquivado": False, "documentos": Mock(side_effect=AssertionError("Consulta inesperada")),
        **alteracoes,
    })


def _snapshot(**alteracoes):
    return {
        "numero": "10/2026", "protocolo": "12.345.678-9", "assunto": "Assunto emitido.",
        "assunto_rotulo": "(Autorização)", "motivo": "Motivo da emissão",
        "viajantes": [{"nome": "Ana Original", "cpf": "123.456.789-00", "rg": "1234567"}],
        "destinos": ["Destino Original/PR"],
        "trechos": [{"saida": {"data": "31/12/2026", "hora": "23:00"},
                     "chegada": {"data": "02/01/2027", "hora": "01:00"}}],
        **alteracoes,
    }


def _doc(*, versao=1, situacao="pronto", dados=None, tipo="oficio", oficio_id=10):
    return SimpleNamespace(versao=versao, situacao=situacao, tipo=tipo,
                           oficio_id=oficio_id, dados=_snapshot() if dados is None else dados)


def _trecho(ordem, destino_id, nome, saida, chegada):
    return SimpleNamespace(ordem=ordem, destino_id=destino_id,
                           destino=SimpleNamespace(nome=nome, uf="PR"),
                           saida_em=saida, chegada_em=chegada)


def test_emitido_preserva_snapshot_apos_alteracao_de_nomes_destinos_periodo_e_motivo():
    snapshot = _snapshot()
    original = deepcopy(snapshot)
    oficio = _oficio(numero_formatado="99/2026")
    resultado = projetar_dados_eprotocolo(
        oficio, documentos=[_doc(dados=snapshot)],
        viajantes=[SimpleNamespace(servidor=SimpleNamespace(nome="Pessoa renomeada"))],
        trechos=[_trecho(1, 2, "Cidade renomeada", datetime(2027, 2, 1, tzinfo=UTC),
                        datetime(2027, 2, 5, tzinfo=UTC))],
    )
    assert resultado.disponivel and resultado.fonte == "emissao" and resultado.versao == 1
    assert resultado.dados.campos[0].valor == "Ana Original"
    assert resultado.dados.campos[2].valor == "10/2026"
    assert "DESTINO ORIGINAL/PR" in resultado.dados.detalhamento
    assert "31/12/2026 a 02/01/2027" in resultado.dados.detalhamento
    assert resultado.dados.detalhamento.endswith("\nMotivo da emissão")
    assert snapshot == original
    assert "123.456.789-00" not in repr(resultado) and "1234567" not in repr(resultado)


@pytest.mark.parametrize("situacao", ["gerando", "falhou"])
def test_ultima_versao_e_fonte_mesmo_quando_v1_esta_pronta(situacao):
    resultado = projetar_dados_eprotocolo(_oficio(), documentos=[
        _doc(versao=1), _doc(versao=2, situacao=situacao, dados=_snapshot(motivo="Versão nova")),
        _doc(versao=100, tipo="justificativa"), _doc(versao=101, oficio_id=999),
    ])
    assert resultado.versao == 2 and resultado.situacao_documento == situacao
    assert resultado.disponivel and resultado.dados.detalhamento.endswith("\nVersão nova")


@pytest.mark.parametrize("quebrado", [
    [], "texto", {}, {"motivo": "isolado"}, _snapshot(trechos=[]),
    _snapshot(viajantes=["nome fora do schema"]), _snapshot(destinos=[None]),
    _snapshot(protocolo=123456789),
    _snapshot(trechos=[{"saida": {"data": "31/02/2026"}, "chegada": {"data": "02/03/2026"}}]),
    _snapshot(trechos=[{"saida": "31/12/2026", "chegada": {"data": "02/01/2027"}}]),
])
def test_snapshot_invalido_fica_indisponivel_sem_reconstruir_dados_vivos(quebrado):
    resultado = projetar_dados_eprotocolo(_oficio(), documentos=[_doc(dados=quebrado)])
    assert not resultado.disponivel and resultado.dados is None
    assert resultado.aviso == (
        "Os dados desta emissão estão indisponíveis. Confira o documento emitido.")


def test_lista_de_documentos_vazia_nao_consulta_fallback():
    oficio = _oficio()
    resultado = projetar_dados_eprotocolo(oficio, documentos=[])
    assert not resultado.disponivel
    oficio.documentos.filter.assert_not_called()


def test_emissao_mais_recente_invalida_nao_retorna_snapshot_antigo_pronto():
    documento = _doc(versao=2, situacao="falhou")
    documento.dados = None
    resultado = projetar_dados_eprotocolo(_oficio(), documentos=[_doc(), documento])
    assert not resultado.disponivel and resultado.versao == 2
    assert resultado.situacao_documento == "falhou" and resultado.dados is None


def test_fallback_consulta_somente_ultima_emissao_do_oficio_sem_filtrar_por_pronto():
    oficio = _oficio()
    oficio.documentos.filter.return_value.order_by.return_value.first.return_value = _doc(
        versao=3, situacao="falhou")
    resultado = projetar_dados_eprotocolo(oficio)
    oficio.documentos.filter.assert_called_once_with(tipo="oficio")
    oficio.documentos.filter.return_value.order_by.assert_called_once_with("-versao")
    assert resultado.versao == 3 and resultado.situacao_documento == "falhou"


def test_rascunho_retificado_usa_vivos_sem_versao_antiga_e_converte_brasilia():
    oficio = _oficio(situacao="rascunho", marcador="retificado", data_oficio=date(2026, 12, 29))
    trechos = [
        _trecho(2, 1, "Sede", datetime(2027, 1, 2, 0, tzinfo=UTC),
                datetime(2027, 1, 2, 4, tzinfo=UTC)),
        _trecho(1, 2, "Destino Novo", datetime(2026, 12, 31, 2, tzinfo=UTC),
                datetime(2026, 12, 31, 5, tzinfo=UTC)),
    ]
    resultado = projetar_dados_eprotocolo(
        oficio, documentos=[_doc()], trechos=trechos,
        viajantes=[SimpleNamespace(servidor=SimpleNamespace(nome="Nome atual", cpf="CPF omitido"))],
    )
    assert resultado.fonte == "rascunho" and resultado.versao is None
    assert resultado.dados.campos[0].valor == "Nome atual"
    assert "(Retificado)" in resultado.dados.campos[1].valor
    assert "DESTINO NOVO/PR" in resultado.dados.detalhamento
    assert "DESTINO: SEDE" not in resultado.dados.detalhamento
    assert "30/12/2026 a 02/01/2027" in resultado.dados.detalhamento
    assert "CPF omitido" not in repr(resultado)


def test_rascunho_vazio_e_listas_vazias_explicitas_nao_exigem_setup_ou_consultas():
    resultado = projetar_dados_eprotocolo(
        _oficio(situacao="rascunho", protocolo_formatado="", motivo=""),
        documentos=[], viajantes=[], trechos=[],
    )
    assert resultado.disponivel and resultado.dados.campos[0].valor == ""
    assert "PERÍODO:" not in resultado.dados.detalhamento


def test_aviso_simulado_no_rascunho_nao_impede_copia_dos_cinco_campos():
    resultado = projetar_dados_eprotocolo(
        _oficio(situacao="rascunho", protocolo_origem="simulado"),
        documentos=[], viajantes=[], trechos=[],
    )
    assert resultado.disponivel and "Confirme o protocolo real" in resultado.aviso
    assert resultado.dados.campos[3].valor == "12.345.678-9"
    assert "Protocolo: 12.345.678-9" in resultado.dados.copiar_tudo


def test_rascunho_com_instante_invalido_nao_quebra_resumo():
    resultado = projetar_dados_eprotocolo(
        _oficio(situacao="rascunho"), viajantes=[],
        trechos=[_trecho(1, 2, "Destino", datetime(2026, 10, 8), datetime(2026, 10, 9))],
    )
    assert not resultado.disponivel and "Confira os dados salvos" in resultado.aviso


@pytest.mark.parametrize("origem,palavra", [
    ("simulado", "Número simulado"), ("treinamento", "Não vale como protocolo oficial"),
    ("eprotocolo", "Aberto no eProtocolo"), ("manual", "Protocolo digitado"),
])
def test_origem_atual_so_e_utilizada_quando_coincide_com_mascara_da_emissao(origem, palavra):
    oficio = _oficio(protocolo_origem=origem)
    resultado = projetar_dados_eprotocolo(oficio, documentos=[_doc()])
    assert resultado.disponivel and palavra in resultado.aviso
    assert resultado.aviso.startswith("Origem registrada no cadastro atual:")
    oficio.protocolo_formatado = "98.765.432-1"
    outro = projetar_dados_eprotocolo(oficio, documentos=[_doc()])
    assert "origem do protocolo desta emissão é desconhecida" in outro.aviso
    assert palavra not in outro.aviso
    assert outro.dados.campos[3].valor == "12.345.678-9"


@pytest.mark.parametrize("origem", ["", "desconhecido"])
def test_origem_ausente_nao_anuncia_oficial_ou_aberto_externamente(origem):
    resultado = projetar_dados_eprotocolo(_oficio(protocolo_origem=origem), documentos=[_doc()])
    assert resultado.aviso == ""


@pytest.mark.parametrize("situacao,arquivado,esperado", [
    ("cancelado", False, "Ofício cancelado: dados históricos"),
    ("emitido", True, "Ofício arquivado"),
])
def test_estados_historicos_sao_identificados_sem_mutacao(situacao, arquivado, esperado):
    oficio = _oficio(situacao=situacao, arquivado=arquivado)
    resultado = projetar_dados_eprotocolo(oficio, documentos=[_doc()])
    assert resultado.disponivel and esperado in resultado.aviso
    assert oficio.situacao == situacao and oficio.arquivado is arquivado
