"""Seleção de versões sem Django/I/O (docs/product/oficios-documentos-versoes.md).

O adaptador autoriza o ofício e fornece somente seus documentos/vias. Arquivamento
é ortogonal à identidade; permissão, arquivo físico e URLs ficam fora do domínio.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentoVersao:
    id: int
    tipo: str
    versao: int
    situacao: str
    # Somente o último ofício informa quais tipos sua emissão contém.
    tem_justificativa: bool | None = None

    def __post_init__(self) -> None:
        if self.id <= 0 or self.versao <= 0 or not self.tipo.strip():
            raise ValueError("Informe identidade, tipo e versão válidos do documento.")


@dataclass(frozen=True)
class ViaDocumento:
    id: int
    tipo: str
    documento_id: int | None
    revogada: bool = False


@dataclass(frozen=True)
class VersaoDocumental:
    documento: DocumentoVersao
    vias: tuple[ViaDocumento, ...] = ()

    @property
    def pdf_disponivel(self) -> bool:
        """Estado registrado, sem afirmar existência/legibilidade do arquivo físico."""
        return self.documento.situacao == "pronto"


@dataclass(frozen=True)
class SelecaoPorTipo:
    tipo: str
    ultima_emissao: DocumentoVersao | None
    corrente: VersaoDocumental | None
    historico: tuple[VersaoDocumental, ...]
    avisos: tuple[str, ...] = ()

    @property
    def estado_geracao(self) -> str:
        return self.corrente.documento.situacao if self.corrente else ""

    @property
    def pdf_corrente(self) -> DocumentoVersao | None:
        if self.corrente and self.corrente.pdf_disponivel:
            return self.corrente.documento
        return None

    @property
    def docx_corrente(self) -> DocumentoVersao | None:
        # Preserva o contrato atual: exportação emitida somente da identidade pronta.
        return self.pdf_corrente

    @property
    def via_assinada_corrente(self) -> ViaDocumento | None:
        if self.pdf_corrente is None or self.corrente is None:
            return None
        vigentes = [via for via in self.corrente.vias if not via.revogada]
        return vigentes[0] if len(vigentes) == 1 else None


def presenca_justificativa(valor_do_snapshot: object) -> bool | None:
    """Classifica apenas o campo congelado; ausente/shape inválido é indeterminado."""
    if not isinstance(valor_do_snapshot, str):
        return None
    return bool(valor_do_snapshot.strip())


def _ultima(documentos: Sequence[DocumentoVersao]) -> DocumentoVersao | None:
    if not documentos:
        return None
    maior = max(documento.versao for documento in documentos)
    candidatas = [documento for documento in documentos if documento.versao == maior]
    return candidatas[0] if len(candidatas) == 1 else None


def _ordem_tipo(tipo: str) -> tuple[int, str]:
    return ({"oficio": 0, "justificativa": 1}.get(tipo, 2), tipo)


def selecionar_versoes(*, situacao_oficio: str, documentos: Sequence[DocumentoVersao],
                       vias: Sequence[ViaDocumento] = (),
                       arquivado: bool = False) -> tuple[SelecaoPorTipo, ...]:
    """Identidade máxima, corrente e histórico por tipo, sem promover primeira pronta.

    Rascunho/cancelado mantêm todas as versões históricas. Arquivamento não altera
    esta escolha; suas restrições de ação continuam nas políticas do chamador.
    Não adaptar termos/OS de outros modelos como documentos fictícios.
    """
    if situacao_oficio not in {"rascunho", "emitido", "cancelado"}:
        raise ValueError("Informe a situação subjacente do ofício, sem usar arquivado.")
    grupos: dict[str, list[DocumentoVersao]] = {}
    for documento in documentos:
        grupos.setdefault(documento.tipo, []).append(documento)
    ultimo_oficio = _ultima(grupos.get("oficio", ()))
    # Ofício é o documento principal, mesmo ausente. Justificativa esperada ou
    # indeterminada precisa ter estado explícito, inclusive sem registros do tipo.
    grupos.setdefault("oficio", [])
    if (situacao_oficio == "emitido" and ultimo_oficio is not None
            and ultimo_oficio.tem_justificativa is not False):
        grupos.setdefault("justificativa", [])
    resultado = []
    for tipo in sorted(grupos, key=_ordem_tipo):
        registros = grupos[tipo]
        ultima = _ultima(registros)
        avisos = []
        if registros and ultima is None:
            avisos.append("Há versões documentais ambíguas. Confira o histórico.")
        corrente = ultima if situacao_oficio == "emitido" else None
        if tipo == "oficio" and situacao_oficio == "emitido" and not registros:
            avisos.append("Os dados da emissão estão indisponíveis. Confira o histórico.")
        if tipo == "justificativa" and situacao_oficio == "emitido":
            if ultimo_oficio is None or ultimo_oficio.tem_justificativa is None:
                corrente = None
                avisos.append("Não foi possível identificar a justificativa desta emissão. "
                              "Confira o documento emitido e o histórico.")
            elif not ultimo_oficio.tem_justificativa:
                corrente = None
            elif not registros:
                avisos.append("A justificativa desta emissão está indisponível. "
                              "Confira o documento emitido.")
        versoes = tuple(VersaoDocumental(documento, tuple(sorted(
            (via for via in vias if via.documento_id == documento.id and via.tipo == tipo),
            key=lambda via: via.id, reverse=True)))
            for documento in sorted(registros, key=lambda doc: (-doc.versao, doc.id)))
        atual = next((versao for versao in versoes if versao.documento is corrente), None)
        if atual is not None:
            if atual.documento.situacao not in {"pronto", "gerando", "falhou"}:
                avisos.append("O estado de geração é desconhecido. Confira o documento emitido.")
            vigentes = [via for via in atual.vias if not via.revogada]
            if len(vigentes) > 1:
                avisos.append("Há vias assinadas ambíguas desta versão. Confira o histórico.")
            elif vigentes and not atual.pdf_disponivel:
                avisos.append("A via assinada não corresponde a um PDF pronto. "
                              "Confira o histórico desta versão.")
        resultado.append(SelecaoPorTipo(
            tipo, ultima, atual,
            tuple(versao for versao in versoes if versao is not atual), tuple(avisos)))
    return tuple(resultado)
