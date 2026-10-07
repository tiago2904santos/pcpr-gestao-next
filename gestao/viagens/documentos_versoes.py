"""Adaptador de leitura RS-02, sem consulta ou reconstrução de snapshots.

O chamador autoriza o ofício e fornece listas/tuplas materializadas. Campos
deferred não são acessados; modelos originais permanecem disponíveis por ID.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from .dominio.documentos_versoes import (
    DocumentoVersao,
    SelecaoPorTipo,
    ViaDocumento,
    presenca_justificativa,
    selecionar_versoes,
)

if TYPE_CHECKING:
    from .models import Documento, Oficio, ViaAssinada


def _atributos(objeto: object) -> dict[str, Any]:
    try:
        return vars(objeto)
    except TypeError:
        return {}


def _id(atributos: dict[str, Any]) -> int | None:
    valor = atributos.get("id", atributos.get("pk"))
    return valor if isinstance(valor, int) and not isinstance(valor, bool) and valor > 0 else None


def _tem_arquivo(valor: object) -> bool:
    nome = valor if isinstance(valor, str) else _atributos(valor).get("name")
    return isinstance(nome, str) and bool(nome.strip())


@dataclass(frozen=True)
class ProjecaoDocumentos:
    selecoes: tuple[SelecaoPorTipo, ...]
    documentos_por_id: Mapping[int, Documento]
    vias_por_id: Mapping[int, ViaAssinada]
    documentos_prontos: frozenset[int]
    arquivos_documentos: frozenset[int]
    arquivos_vias: frozenset[int]
    avisos: tuple[str, ...] = ()

    def por_tipo(self, tipo: str) -> SelecaoPorTipo | None:
        return next((selecao for selecao in self.selecoes if selecao.tipo == tipo), None)

    def pdf_disponivel(self, documento_id: int) -> bool:
        """PDF original com estado pronto e caminho; não consulta o storage."""
        return (documento_id in self.documentos_prontos
                and documento_id in self.arquivos_documentos)

    def via_disponivel(self, via_id: int) -> bool:
        """Inclui vias históricas/revogadas; a autorização de leitura é do chamador."""
        return via_id in self.arquivos_vias

    def pdf_original(self, tipo: str) -> Documento | None:
        selecao = self.por_tipo(tipo)
        documento = selecao.pdf_corrente if selecao else None
        if documento is None or not self.pdf_disponivel(documento.id):
            return None
        return self.documentos_por_id[documento.id]

    def docx_corrente(self, tipo: str) -> Documento | None:
        selecao = self.por_tipo(tipo)
        documento = selecao.docx_corrente if selecao else None
        return self.documentos_por_id[documento.id] if documento else None

    def via_assinada(self, tipo: str) -> ViaAssinada | None:
        selecao = self.por_tipo(tipo)
        via = selecao.via_assinada_corrente if selecao else None
        if via is None or not self.via_disponivel(via.id):
            return None
        return self.vias_por_id[via.id]

    def pdf_efetivo(self, tipo: str) -> Documento | ViaAssinada | None:
        return self.via_assinada(tipo) or self.pdf_original(tipo)


def projetar_documentos(oficio: Oficio, *, documentos: Sequence[Documento],
                       vias: Sequence[ViaAssinada]) -> ProjecaoDocumentos:
    """Projeta apenas listas materializadas do objeto autorizado, sem SQL/IO.

    Metadados locais incompletos produzem aviso sem usar descritores Django.
    Não confundir o caminho preenchido com existência/validade dos bytes.
    """
    if not isinstance(documentos, (list, tuple)) or not isinstance(vias, (list, tuple)):
        raise TypeError("Forneça listas ou tuplas de documentos e vias já carregadas.")
    atributos = _atributos(oficio)
    oficio_id = _id(atributos)
    modelos: dict[int, Documento] = {}
    modelos_vias: dict[int, ViaAssinada] = {}
    descricoes = []
    descricoes_vias = []
    prontos: set[int] = set()
    arquivos: set[int] = set()
    arquivos_vias: set[int] = set()
    avisos = []
    documentos_incompletos = oficio_id is None
    vias_incompletas = False
    for documento in documentos:
        campos = _atributos(documento)
        if "oficio_id" not in campos:
            documentos_incompletos = True
            continue
        if campos["oficio_id"] != oficio_id:
            continue
        documento_id = _id(campos)
        if (documento_id is None or documento_id in modelos
                or not {"tipo", "versao", "situacao", "dados", "arquivo"} <= campos.keys()
                or not isinstance(campos["tipo"], str)
                or not isinstance(campos["situacao"], str)
                or not isinstance(campos["versao"], int)
                or isinstance(campos["versao"], bool)):
            documentos_incompletos = True
            continue
        snapshot = campos["dados"]
        try:
            descricao = DocumentoVersao(
                documento_id, campos["tipo"], campos["versao"], campos["situacao"],
                presenca_justificativa(snapshot.get("justificativa"))
                if campos["tipo"] == "oficio" and isinstance(snapshot, dict) else None)
        except ValueError:
            documentos_incompletos = True
            continue
        modelos[documento_id] = documento
        descricoes.append(descricao)
        if descricao.situacao == "pronto":
            prontos.add(documento_id)
        if _tem_arquivo(campos.get("arquivo")):
            arquivos.add(documento_id)
    for via in vias:
        campos = _atributos(via)
        if "oficio_id" not in campos:
            vias_incompletas = True
            continue
        if campos["oficio_id"] != oficio_id:
            continue
        via_id = _id(campos)
        if (via_id is None or via_id in modelos_vias
                or not {"tipo", "documento_id", "revogada_em", "arquivo"} <= campos.keys()
                or not isinstance(campos["tipo"], str)):
            vias_incompletas = True
            continue
        documento_id = campos["documento_id"]
        if documento_id not in modelos or modelos[documento_id].__dict__["tipo"] != campos["tipo"]:
            continue
        modelos_vias[via_id] = via
        descricoes_vias.append(ViaDocumento(
            via_id, campos["tipo"], documento_id, campos["revogada_em"] is not None))
        if _tem_arquivo(campos.get("arquivo")):
            arquivos_vias.add(via_id)
    if vias_incompletas:
        descricoes_vias = []
        avisos.append("As vias assinadas não foram carregadas por completo. Atualize a página.")
    selecoes: tuple[SelecaoPorTipo, ...]
    if documentos_incompletos:
        selecoes = ()
        avisos.append("Os documentos não foram carregados por completo. Atualize a página.")
        prontos.clear()
        arquivos.clear()
        arquivos_vias.clear()
    else:
        try:
            selecoes = selecionar_versoes(
                situacao_oficio=atributos.get("situacao", ""), documentos=descricoes,
                vias=descricoes_vias, arquivado=bool(atributos.get("arquivado", False)))
        except ValueError:
            selecoes = ()
            avisos.append("Confira a situação deste ofício antes de consultar os documentos.")
        for selecao in selecoes:
            avisos.extend(selecao.avisos)
            if selecao.pdf_corrente and selecao.pdf_corrente.id not in arquivos:
                avisos.append(f"O PDF original de {selecao.tipo} v{selecao.pdf_corrente.versao} "
                              "está sem arquivo. Confira as versões anteriores.")
            via_corrente = selecao.via_assinada_corrente
            if via_corrente and via_corrente.id not in arquivos_vias:
                avisos.append("A via assinada desta versão está sem arquivo. Confira o original.")
    return ProjecaoDocumentos(
        selecoes, MappingProxyType(modelos), MappingProxyType(modelos_vias),
        frozenset(prontos), frozenset(arquivos), frozenset(arquivos_vias),
        tuple(dict.fromkeys(avisos)))
