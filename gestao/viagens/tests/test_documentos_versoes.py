"""RS-02 puro: identidade, disponibilidade, assinatura e história sem banco."""

from dataclasses import FrozenInstanceError
from itertools import permutations

import pytest

from gestao.viagens.dominio.documentos_versoes import (
    DocumentoVersao,
    ViaDocumento,
    presenca_justificativa,
    selecionar_versoes,
)


def _oficio(id=10, versao=1, situacao="pronto", justificativa=False):
    return DocumentoVersao(id, "oficio", versao, situacao, justificativa)


def _tipo(resultado, tipo="oficio"):
    return next(selecao for selecao in resultado if selecao.tipo == tipo)


@pytest.mark.parametrize("situacao", ["gerando", "falhou", "pronto"])
def test_identidade_maxima_nao_promove_versao_anterior_pronta(situacao):
    v1 = _oficio()
    v2 = _oficio(20, 2, situacao)
    for documentos in permutations([v1, v2]):
        selecao = _tipo(selecionar_versoes(situacao_oficio="emitido", documentos=documentos))
        assert selecao.ultima_emissao == v2
        assert selecao.corrente.documento == v2
        assert selecao.estado_geracao == situacao
        assert [versao.documento for versao in selecao.historico] == [v1]
        assert selecao.historico[0].pdf_disponivel
        assert selecao.pdf_corrente == (v2 if situacao == "pronto" else None)
        assert selecao.docx_corrente == selecao.pdf_corrente


@pytest.mark.parametrize("situacao", ["rascunho", "cancelado"])
def test_reaberto_e_cancelado_preservam_historicos_legiveis_sem_corrente(situacao):
    v1, v2 = _oficio(), _oficio(20, 2)
    via = ViaDocumento(30, "oficio", v1.id, revogada=True)
    selecao = _tipo(selecionar_versoes(
        situacao_oficio=situacao, documentos=[v1, v2], vias=[via]))
    assert selecao.ultima_emissao == v2
    assert selecao.corrente is None
    assert selecao.pdf_corrente is None and selecao.docx_corrente is None
    assert selecao.via_assinada_corrente is None
    assert selecao.estado_geracao == ""
    assert [versao.documento for versao in selecao.historico] == [v2, v1]
    assert all(versao.pdf_disponivel for versao in selecao.historico)
    assert selecao.historico[1].vias == (via,)


@pytest.mark.parametrize("situacao", ["rascunho", "emitido", "cancelado"])
def test_arquivado_e_ortogonal_a_identidade_e_ao_historico(situacao):
    documentos = [_oficio(), _oficio(20, 2, "falhou")]
    vias = [ViaDocumento(30, "oficio", 10, revogada=True)]
    aberto = selecionar_versoes(situacao_oficio=situacao, documentos=documentos, vias=vias)
    arquivado = selecionar_versoes(
        situacao_oficio=situacao, documentos=documentos, vias=vias, arquivado=True)
    assert arquivado == aberto


def test_via_corrente_precisa_da_identidade_e_tipo_exatos_sem_revogacao():
    v1, v2 = _oficio(), _oficio(20, 2)
    antiga = ViaDocumento(30, "oficio", v1.id)
    revogada = ViaDocumento(31, "oficio", v2.id, revogada=True)
    outro_tipo = ViaDocumento(32, "justificativa", v2.id)
    sem_vinculo = ViaDocumento(33, "oficio", None)
    corrente = ViaDocumento(34, "oficio", v2.id)
    selecao = _tipo(selecionar_versoes(
        situacao_oficio="emitido", documentos=[v1, v2],
        vias=[antiga, revogada, outro_tipo, sem_vinculo, corrente]))
    assert selecao.via_assinada_corrente == corrente
    assert selecao.corrente.vias == (corrente, revogada)
    assert selecao.historico[0].vias == (antiga,)
    assert not selecao.avisos


def test_via_da_versao_antiga_nao_assina_a_corrente():
    v1, v2 = _oficio(), _oficio(20, 2)
    antiga = ViaDocumento(30, "oficio", v1.id)
    selecao = _tipo(selecionar_versoes(
        situacao_oficio="emitido", documentos=[v1, v2], vias=[antiga]))
    assert selecao.via_assinada_corrente is None
    assert selecao.pdf_corrente == v2
    assert selecao.historico[0].vias == (antiga,)


@pytest.mark.parametrize("situacao", ["gerando", "falhou"])
def test_via_inconsistente_nao_habilita_arquivo_ou_assinado(situacao):
    documento = _oficio(situacao=situacao)
    via = ViaDocumento(30, "oficio", documento.id)
    selecao = _tipo(selecionar_versoes(
        situacao_oficio="emitido", documentos=[documento], vias=[via]))
    assert selecao.corrente.vias == (via,)
    assert selecao.pdf_corrente is None and selecao.docx_corrente is None
    assert selecao.via_assinada_corrente is None
    assert "não corresponde a um PDF pronto" in selecao.avisos[0]


def test_duas_vias_vigentes_exatas_nao_escolhem_arbitrariamente_uma():
    documento = _oficio()
    vias = [ViaDocumento(30, "oficio", 10), ViaDocumento(31, "oficio", 10)]
    selecao = _tipo(selecionar_versoes(
        situacao_oficio="emitido", documentos=[documento], vias=vias))
    assert selecao.pdf_corrente == documento
    assert selecao.via_assinada_corrente is None
    assert len(selecao.corrente.vias) == 2
    assert "vias assinadas ambíguas" in selecao.avisos[0]


@pytest.mark.parametrize("valor,esperado", [
    ("Texto congelado", True), ("  Texto congelado\n", True), ("", False),
    (" \n\t ", False), (None, None), (False, None), (0, None), ([], None), ({}, None),
])
def test_campo_de_snapshot_justificativa_presente_vazio_ou_invalido(valor, esperado):
    assert presenca_justificativa(valor) is esperado


def test_justificativa_vazia_da_nova_emissao_deixa_antiga_somente_no_historico():
    v1 = _oficio(justificativa=True)
    v2 = _oficio(20, 2, justificativa=False)
    justificativa = DocumentoVersao(11, "justificativa", 1, "pronto")
    via = ViaDocumento(30, "justificativa", justificativa.id)
    resultado = selecionar_versoes(
        situacao_oficio="emitido", documentos=[v1, justificativa, v2], vias=[via])
    selecao = _tipo(resultado, "justificativa")
    assert selecao.ultima_emissao == justificativa
    assert selecao.corrente is None and selecao.pdf_corrente is None
    assert selecao.via_assinada_corrente is None
    assert selecao.historico[0].documento == justificativa
    assert selecao.historico[0].pdf_disponivel
    assert selecao.historico[0].vias == (via,)
    assert not selecao.avisos


def test_versoes_de_tipos_diferentes_nao_precisam_ter_numeros_iguais():
    oficio = _oficio(20, 3, justificativa=True)
    justificativa = DocumentoVersao(21, "justificativa", 1, "pronto")
    resultado = selecionar_versoes(
        situacao_oficio="emitido", documentos=[justificativa, oficio])
    assert _tipo(resultado).corrente.documento == oficio
    assert _tipo(resultado, "justificativa").corrente.documento == justificativa


def test_justificativa_pendente_nao_promove_a_versao_anterior_pronta():
    oficio = _oficio(20, 2, justificativa=True)
    j1 = DocumentoVersao(11, "justificativa", 1, "pronto")
    j2 = DocumentoVersao(21, "justificativa", 2, "falhou")
    resultado = selecionar_versoes(situacao_oficio="emitido", documentos=[j1, oficio, j2])
    selecao = _tipo(resultado, "justificativa")
    assert selecao.corrente.documento == j2
    assert selecao.estado_geracao == "falhou"
    assert selecao.pdf_corrente is None and selecao.docx_corrente is None
    assert selecao.historico[0].documento == j1


def test_snapshot_indeterminado_nao_promove_justificativa_antiga():
    oficio = _oficio(20, 2, justificativa=None)
    justificativa = DocumentoVersao(11, "justificativa", 1, "pronto")
    resultado = selecionar_versoes(situacao_oficio="emitido", documentos=[oficio, justificativa])
    selecao = _tipo(resultado, "justificativa")
    assert _tipo(resultado).pdf_corrente == oficio
    assert selecao.corrente is None
    assert selecao.historico[0].documento == justificativa
    assert "Não foi possível identificar" in selecao.avisos[0]


def test_snapshot_indeterminado_sem_justificativa_tem_indisponibilidade_explicita():
    resultado = selecionar_versoes(
        situacao_oficio="emitido", documentos=[_oficio(justificativa=None)])
    selecao = _tipo(resultado, "justificativa")
    assert selecao.corrente is None and not selecao.historico
    assert selecao.avisos


def test_justificativa_esperada_mas_ausente_avisa_sem_reconstituir():
    resultado = selecionar_versoes(
        situacao_oficio="emitido", documentos=[_oficio(justificativa=True)])
    selecao = _tipo(resultado, "justificativa")
    assert selecao.ultima_emissao is None and selecao.corrente is None
    assert selecao.historico == ()
    assert "justificativa desta emissão está indisponível" in selecao.avisos[0]


def test_justificativa_sem_oficio_nao_e_corrente():
    justificativa = DocumentoVersao(11, "justificativa", 1, "pronto")
    resultado = selecionar_versoes(situacao_oficio="emitido", documentos=[justificativa])
    assert _tipo(resultado).avisos
    selecao = _tipo(resultado, "justificativa")
    assert selecao.corrente is None and selecao.avisos
    assert selecao.historico[0].documento == justificativa


def test_empate_de_maior_versao_nao_promove_nem_desempata_por_id():
    v1 = _oficio()
    v2 = _oficio(20, 2, "gerando")
    outro_v2 = _oficio(21, 2, "pronto")
    for documentos in permutations([v1, v2, outro_v2]):
        selecao = _tipo(selecionar_versoes(situacao_oficio="emitido", documentos=documentos))
        assert selecao.ultima_emissao is None and selecao.corrente is None
        assert selecao.pdf_corrente is None and selecao.docx_corrente is None
        assert [versao.documento for versao in selecao.historico] == [v2, outro_v2, v1]
        assert "versões documentais ambíguas" in selecao.avisos[0]


def test_estado_desconhecido_preserva_identidade_mas_nao_habilita_download():
    documento = _oficio(situacao="desconhecido")
    selecao = _tipo(selecionar_versoes(situacao_oficio="emitido", documentos=[documento]))
    assert selecao.corrente.documento == documento
    assert selecao.estado_geracao == "desconhecido"
    assert selecao.pdf_corrente is None and selecao.docx_corrente is None
    assert "estado de geração é desconhecido" in selecao.avisos[0]


def test_ordem_oficio_justificativa_outros_nao_depende_da_entrada():
    documentos = [_oficio(justificativa=True),
                  DocumentoVersao(11, "justificativa", 1, "pronto"),
                  DocumentoVersao(12, "anexo-b", 1, "pronto"),
                  DocumentoVersao(13, "anexo-a", 1, "pronto")]
    for entrada in permutations(documentos):
        resultado = selecionar_versoes(situacao_oficio="emitido", documentos=entrada)
        assert [selecao.tipo for selecao in resultado] == [
            "oficio", "justificativa", "anexo-a", "anexo-b"]


def test_entrada_sem_documentos_nao_fabrica_emissao():
    selecao = _tipo(selecionar_versoes(situacao_oficio="emitido", documentos=[]))
    assert selecao.ultima_emissao is None and selecao.corrente is None
    assert not selecao.historico and selecao.avisos


def test_inputs_nao_mutam_e_dtos_sao_imutaveis():
    documentos = [_oficio(20, 2), _oficio()]
    vias = [ViaDocumento(30, "oficio", 10, True)]
    antes = documentos.copy(), vias.copy()
    resultado = selecionar_versoes(situacao_oficio="emitido", documentos=documentos, vias=vias)
    assert (documentos, vias) == antes
    assert resultado == selecionar_versoes(
        situacao_oficio="emitido", documentos=documentos, vias=vias)
    with pytest.raises(FrozenInstanceError):
        resultado[0].tipo = "alterado"
    with pytest.raises(FrozenInstanceError):
        documentos[0].versao = 99


@pytest.mark.parametrize("id,tipo,versao", [(0, "oficio", 1), (-1, "oficio", 1),
                                         (1, " ", 1), (1, "oficio", 0)])
def test_metadados_de_identidade_invalidos_sao_recusados(id, tipo, versao):
    with pytest.raises(ValueError, match="identidade"):
        DocumentoVersao(id, tipo, versao, "pronto")


def test_arquivado_nao_e_situacao_subjacente():
    with pytest.raises(ValueError, match="situação subjacente"):
        selecionar_versoes(situacao_oficio="arquivado", documentos=[])
