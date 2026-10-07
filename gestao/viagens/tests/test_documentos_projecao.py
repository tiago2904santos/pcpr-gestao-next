"""Adaptador RS-02 com objetos carregados e armadilhas para descritores/I/O."""

from copy import deepcopy
from datetime import UTC, datetime

import pytest

from gestao.viagens.documentos_versoes import projetar_documentos


class ModeloCarregado:
    def __init__(self, **campos):
        self.__dict__.update(campos)

    def __getattr__(self, nome):
        if nome.startswith("__"):
            raise AttributeError(nome)
        raise AssertionError(f"Descritor/relação não carregado: {nome}")


class ArquivoCarregado(ModeloCarregado):
    @property
    def name(self):
        raise AssertionError("Não resolver descritor de arquivo")

    @property
    def url(self):
        raise AssertionError("Não consultar storage/URL")

    def open(self, *_args, **_kwargs):
        raise AssertionError("Não abrir arquivo")


def _oficio(**campos):
    return ModeloCarregado(**{"id": 1, "situacao": "emitido", "arquivado": False, **campos})


def _documento(id=10, **campos):
    return ModeloCarregado(**{
        "id": id, "oficio_id": 1, "tipo": "oficio", "versao": 1, "situacao": "pronto",
        "dados": {"justificativa": "", "motivo": "Congelado", "viajantes": [{"nome": "Ana"}]},
        "arquivo": ArquivoCarregado(name="documentos/oficio-v1.pdf"), **campos,
    })


def _via(id=30, **campos):
    return ModeloCarregado(**{
        "id": id, "oficio_id": 1, "tipo": "oficio", "documento_id": 10,
        "revogada_em": None, "arquivo": ArquivoCarregado(name="assinados/oficio.pdf"),
        **campos,
    })


def test_projecao_carregada_nao_resolve_orm_storage_ou_descritores():
    oficio, documento, via = _oficio(), _documento(), _via()
    projecao = projetar_documentos(oficio, documentos=[documento], vias=[via])
    assert projecao.pdf_original("oficio") is documento
    assert projecao.docx_corrente("oficio") is documento
    assert projecao.via_assinada("oficio") is via
    assert projecao.pdf_efetivo("oficio") is via
    assert projecao.documentos_por_id[10] is documento
    assert projecao.vias_por_id[30] is via
    assert not projecao.avisos


@pytest.mark.parametrize("situacao", ["gerando", "falhou"])
def test_maior_identidade_sem_pdf_nao_promove_anterior_pronta(situacao):
    anterior = _documento()
    atual = _documento(20, versao=2, situacao=situacao, arquivo="")
    antiga = _via()
    projecao = projetar_documentos(_oficio(), documentos=[anterior, atual], vias=[antiga])
    selecao = projecao.por_tipo("oficio")
    assert selecao.ultima_emissao.id == 20
    assert selecao.estado_geracao == situacao
    assert projecao.pdf_original("oficio") is None
    assert projecao.docx_corrente("oficio") is None
    assert projecao.via_assinada("oficio") is None
    assert projecao.pdf_efetivo("oficio") is None
    assert projecao.pdf_disponivel(10)
    assert selecao.historico[0].documento.id == 10
    assert selecao.historico[0].vias[0].id == 30


@pytest.mark.parametrize("arquivo", ["", " \n ", None, ArquivoCarregado(name="")])
def test_pronto_sem_caminho_nao_oferece_pdf_original_mas_preserva_estado_e_snapshot(arquivo):
    documento = _documento(arquivo=arquivo)
    projecao = projetar_documentos(_oficio(), documentos=[documento], vias=[])
    assert projecao.por_tipo("oficio").estado_geracao == "pronto"
    assert 10 in projecao.documentos_prontos
    assert projecao.pdf_original("oficio") is None
    assert not projecao.pdf_disponivel(10)
    # DOCX é composto do snapshot; não precisa abrir o PDF, mas exige estado pronto.
    assert projecao.docx_corrente("oficio") is documento
    assert "está sem arquivo" in projecao.avisos[0]


def test_assinado_com_caminho_exato_pode_ser_pdf_mesmo_sem_original_no_storage():
    documento, via = _documento(arquivo=""), _via()
    projecao = projetar_documentos(_oficio(), documentos=[documento], vias=[via])
    assert projecao.pdf_original("oficio") is None
    assert projecao.pdf_efetivo("oficio") is via
    assert projecao.via_assinada("oficio") is via


def test_via_sem_arquivo_avisa_e_original_exato_permanece_disponivel():
    documento, via = _documento(), _via(arquivo="")
    projecao = projetar_documentos(_oficio(), documentos=[documento], vias=[via])
    assert projecao.vias_por_id[30] is via
    assert not projecao.via_disponivel(30)
    assert projecao.via_assinada("oficio") is None
    assert projecao.pdf_efetivo("oficio") is documento
    assert "via assinada desta versão está sem arquivo" in projecao.avisos[0]


def test_arquivo_registrado_nao_prova_existencia_dos_bytes():
    documento = _documento(arquivo="arquivo-que-nao-foi-verificado.pdf")
    projecao = projetar_documentos(_oficio(), documentos=[documento], vias=[])
    assert projecao.pdf_disponivel(10)
    assert projecao.pdf_original("oficio") is documento


@pytest.mark.parametrize("situacao", ["rascunho", "cancelado"])
def test_historico_cancelado_ou_reaberto_preserva_modelos_e_vias_revogadas(situacao):
    documento = _documento()
    revogada = _via(revogada_em=datetime(2026, 10, 7, tzinfo=UTC))
    projecao = projetar_documentos(
        _oficio(situacao=situacao), documentos=[documento], vias=[revogada])
    assert projecao.pdf_efetivo("oficio") is None
    assert projecao.docx_corrente("oficio") is None
    assert projecao.pdf_disponivel(10) and projecao.via_disponivel(30)
    assert projecao.por_tipo("oficio").historico[0].vias[0].revogada
    assert projecao.documentos_por_id[10] is documento
    assert projecao.vias_por_id[30] is revogada


def test_arquivado_nao_muda_selecao_ou_disponibilidade():
    documentos, vias = [_documento()], [_via()]
    normal = projetar_documentos(_oficio(), documentos=documentos, vias=vias)
    arquivado = projetar_documentos(_oficio(arquivado=True), documentos=documentos, vias=vias)
    assert arquivado == normal


def test_doc_e_via_de_outro_oficio_nao_entram_nos_mapas_ou_selecao():
    documento, via = _documento(), _via()
    externo = _documento(20, oficio_id=2, versao=99)
    via_externa = _via(31, oficio_id=2, documento_id=10)
    projecao = projetar_documentos(
        _oficio(), documentos=[externo, documento], vias=[via_externa, via])
    assert set(projecao.documentos_por_id) == {10}
    assert set(projecao.vias_por_id) == {30}
    assert projecao.pdf_efetivo("oficio") is via
    assert not projecao.pdf_disponivel(20) and not projecao.via_disponivel(31)


@pytest.mark.parametrize("campos", [
    {"documento_id": None}, {"documento_id": 999}, {"tipo": "justificativa"},
])
def test_via_sem_identidade_tipo_exatos_nao_e_promovida(campos):
    documento, via = _documento(), _via(**campos)
    projecao = projetar_documentos(_oficio(), documentos=[documento], vias=[via])
    assert not projecao.vias_por_id
    assert projecao.via_assinada("oficio") is None
    assert projecao.pdf_efetivo("oficio") is documento


@pytest.mark.parametrize("campo", ["versao", "situacao", "dados", "arquivo", "oficio_id"])
def test_campo_documental_deferred_nao_dispara_query_nem_promove_v1(campo):
    anterior, atual = _documento(), _documento(20, versao=2)
    del atual.__dict__[campo]
    projecao = projetar_documentos(_oficio(), documentos=[anterior, atual], vias=[])
    assert projecao.selecoes == ()
    assert projecao.pdf_original("oficio") is None
    assert projecao.docx_corrente("oficio") is None
    assert not projecao.pdf_disponivel(10)
    assert "não foram carregados por completo" in projecao.avisos[0]


@pytest.mark.parametrize("campo", ["tipo", "documento_id", "revogada_em", "arquivo", "oficio_id"])
def test_vias_deferred_nao_consultam_nem_escondem_possivel_ambiguidade(campo):
    documento, via, incompleta = _documento(), _via(), _via(31)
    del incompleta.__dict__[campo]
    projecao = projetar_documentos(_oficio(), documentos=[documento], vias=[via, incompleta])
    assert projecao.via_assinada("oficio") is None
    assert projecao.pdf_original("oficio") is documento
    assert "vias assinadas não foram carregadas" in projecao.avisos[0]


@pytest.mark.parametrize("snapshot", [None, [], "", {}, {"justificativa": False}])
def test_snapshot_invalido_indetermina_justificativa_sem_reconstruir(snapshot):
    oficio = _documento(20, versao=2, dados=snapshot)
    antiga = _documento(11, tipo="justificativa")
    projecao = projetar_documentos(_oficio(), documentos=[oficio, antiga], vias=[])
    selecao = projecao.por_tipo("justificativa")
    assert selecao.corrente is None
    assert selecao.historico[0].documento.id == antiga.id
    assert projecao.pdf_original("justificativa") is None
    assert projecao.docx_corrente("justificativa") is None
    assert "Não foi possível identificar" in projecao.avisos[0]
    assert oficio.dados is snapshot


@pytest.mark.parametrize("texto,corrente", [("", False), (" \n ", False), ("Texto", True)])
def test_snapshot_da_ultima_emissao_define_se_justificativa_e_corrente(texto, corrente):
    antigo = _documento(dados={"justificativa": "Texto antigo"})
    atual = _documento(20, versao=2, dados={"justificativa": texto})
    justificativa = _documento(11, tipo="justificativa")
    projecao = projetar_documentos(
        _oficio(), documentos=[antigo, justificativa, atual], vias=[])
    assert bool(projecao.por_tipo("justificativa").corrente) is corrente
    assert (projecao.pdf_original("justificativa") is justificativa) is corrente


def test_modelos_snapshot_e_listas_sao_preservados_por_identidade():
    documento, via = _documento(), _via()
    documentos, vias = [documento], [via]
    snapshot = deepcopy(documento.dados)
    projecao = projetar_documentos(_oficio(), documentos=documentos, vias=vias)
    assert documentos == [documento] and vias == [via]
    assert documento.dados == snapshot
    assert projecao.documentos_por_id[10] is documento
    assert projecao.vias_por_id[30] is via
    with pytest.raises(TypeError):
        projecao.documentos_por_id[20] = documento
    with pytest.raises(TypeError):
        projecao.vias_por_id[31] = via


def test_listas_vazias_sao_explicitas_sem_fallback_de_manager():
    projecao = projetar_documentos(_oficio(), documentos=(), vias=())
    assert not projecao.documentos_por_id and not projecao.vias_por_id
    assert projecao.por_tipo("oficio").ultima_emissao is None
    assert projecao.pdf_efetivo("oficio") is None


class ColecaoNaoMaterializada:
    def __iter__(self):
        raise AssertionError("Não avaliar queryset/generator")


@pytest.mark.parametrize("qual", ["documentos", "vias"])
def test_colecao_lazy_e_recusada_antes_de_avaliar(qual):
    listas = {"documentos": [], "vias": []}
    listas[qual] = ColecaoNaoMaterializada()
    with pytest.raises(TypeError, match="já carregadas"):
        projetar_documentos(_oficio(), **listas)


def test_identidade_documental_duplicada_avisa_sem_escolher_uma():
    projecao = projetar_documentos(
        _oficio(), documentos=[_documento(), _documento(versao=2)], vias=[])
    assert projecao.selecoes == ()
    assert projecao.pdf_original("oficio") is None
    assert projecao.avisos


def test_id_pk_carregado_e_aceito_sem_acessar_propriedade():
    oficio = _oficio(pk=1)
    documento = _documento(pk=10)
    via = _via(pk=30)
    for modelo in [oficio, documento, via]:
        del modelo.__dict__["id"]
    projecao = projetar_documentos(oficio, documentos=[documento], vias=[via])
    assert projecao.pdf_efetivo("oficio") is via


def test_situacao_deferred_nao_faz_consulta_para_resolver():
    oficio = _oficio()
    del oficio.__dict__["situacao"]
    projecao = projetar_documentos(oficio, documentos=[_documento()], vias=[])
    assert projecao.selecoes == ()
    assert "Confira a situação" in projecao.avisos[0]
