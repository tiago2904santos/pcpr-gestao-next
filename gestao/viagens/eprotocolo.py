"""Projeção de leitura dos campos copiáveis (docs/product/oficios-eprotocolo.md).

O chamador autoriza o acesso ao ofício antes de chamar esta projeção. Não escreve,
abre processos ou gera documentos. Listas já carregadas evitam novas consultas.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Literal
from zoneinfo import ZoneInfo

from django.utils import timezone

from .dominio.assunto import resolver_assunto
from .dominio.eprotocolo import DadosEprotocolo, dados_eprotocolo

if TYPE_CHECKING:
    from .models import Documento, Oficio, Trecho, Viajante

BRASILIA = ZoneInfo("America/Sao_Paulo")
_INDISPONIVEL = "Os dados desta emissão estão indisponíveis. Confira o documento emitido."


@dataclass(frozen=True)
class ProjecaoEprotocolo:
    dados: DadosEprotocolo | None
    fonte: Literal["rascunho", "emissao"]
    versao: int | None = None
    situacao_documento: str = ""
    aviso: str = ""

    @property
    def disponivel(self) -> bool:
        return self.dados is not None


class _SnapshotInvalido(ValueError):
    pass


def _texto(valor: object) -> str:
    if not isinstance(valor, str):
        raise _SnapshotInvalido
    return valor


def _data_do_snapshot(trecho: object, evento: str) -> date:
    if not isinstance(trecho, dict) or not isinstance(trecho.get(evento), dict):
        raise _SnapshotInvalido
    bruto = _texto(trecho[evento].get("data"))
    try:
        return datetime.strptime(bruto, "%d/%m/%Y").date()
    except ValueError as exc:
        raise _SnapshotInvalido from exc


def _dados_do_snapshot(snapshot: object) -> DadosEprotocolo:
    if not isinstance(snapshot, dict):
        raise _SnapshotInvalido
    textos = {chave: _texto(snapshot.get(chave)) for chave in (
        "numero", "protocolo", "assunto", "assunto_rotulo", "motivo")}
    pessoas, destinos, trechos = (snapshot.get(chave) for chave in (
        "viajantes", "destinos", "trechos"))
    if (not isinstance(pessoas, list) or not isinstance(destinos, list)
            or not isinstance(trechos, list) or not trechos):
        raise _SnapshotInvalido
    nomes = []
    for pessoa in pessoas:
        if not isinstance(pessoa, dict):
            raise _SnapshotInvalido
        nomes.append(_texto(pessoa.get("nome")))
    locais = [_texto(destino) for destino in destinos]
    # Validar os trechos usados pela projeção, sem transformar texto congelado em UTC.
    saida = _data_do_snapshot(trechos[0], "saida")
    retorno = _data_do_snapshot(trechos[-1], "chegada")
    return dados_eprotocolo(
        numero=textos["numero"], protocolo=textos["protocolo"],
        assunto_linha=textos["assunto"], assunto_rotulo=textos["assunto_rotulo"],
        motivo=textos["motivo"], servidores=nomes, destinos=locais,
        saida=saida, retorno=retorno,
    )


def _aviso_da_origem(oficio: Oficio, protocolo: str, *, historico: bool = False) -> str:
    if historico and oficio.protocolo_formatado != protocolo:
        return "A origem do protocolo desta emissão é desconhecida. Confira o número emitido."
    origem = oficio.protocolo_origem
    aviso = {
        "simulado": "Número simulado. Confirme o protocolo real antes de protocolar.",
        "treinamento": "Protocolo de treinamento. Não vale como protocolo oficial.",
        "eprotocolo": "Aberto no eProtocolo.",
        "manual": "Protocolo digitado.",
    }.get(origem, "")
    if historico and aviso:
        return f"Origem registrada no cadastro atual: {aviso}"
    return aviso


def _dados_vivos(oficio: Oficio, viajantes: Sequence[Viajante],
                 trechos: Sequence[Trecho]) -> DadosEprotocolo:
    ordenados = sorted(trechos, key=lambda trecho: trecho.ordem)
    saida = timezone.localtime(ordenados[0].saida_em, BRASILIA).date() if ordenados else None
    retorno = (timezone.localtime(ordenados[-1].chegada_em, BRASILIA).date()
               if ordenados else None)
    destinos = []
    for trecho in ordenados:
        if trecho.destino_id != oficio.sede_id:
            rotulo = f"{trecho.destino.nome}/{trecho.destino.uf}"
            if rotulo not in destinos:
                destinos.append(rotulo)
    assunto = resolver_assunto(oficio.data_oficio, saida, oficio.marcador)
    return dados_eprotocolo(
        numero=oficio.numero_formatado, protocolo=oficio.protocolo_formatado,
        assunto_linha=assunto.linha, assunto_rotulo=assunto.rotulo,
        destinos=destinos, saida=saida, retorno=retorno,
        servidores=[v.servidor.nome for v in viajantes], motivo=oficio.motivo,
    )


def projetar_dados_eprotocolo(oficio: Oficio, *, documentos: Sequence[Documento] | None = None,
                             viajantes: Sequence[Viajante] | None = None,
                             trechos: Sequence[Trecho] | None = None) -> ProjecaoEprotocolo:
    """Dados do rascunho atual ou da última emissão, incluindo geração pendente/falha.

    Na revisão, receber o ofício já preparado com a data prevista para emitir.
    Uma lista vazia fornecida significa ausência; não dispara consulta de fallback.
    """
    if oficio.situacao == "rascunho":
        if viajantes is None:
            from .queries import viajantes_de

            viajantes = viajantes_de(oficio)
        if trechos is None:
            from .queries import trechos_de

            trechos = trechos_de(oficio)
        try:
            dados = _dados_vivos(oficio, viajantes, trechos)
        except (AttributeError, TypeError, ValueError):
            return ProjecaoEprotocolo(
                None, "rascunho", aviso="Confira os dados salvos e o roteiro deste rascunho.")
        aviso = _aviso_da_origem(oficio, dados.campos[3].valor)
        if oficio.arquivado:
            aviso = f"Ofício arquivado. {aviso}".strip()
        return ProjecaoEprotocolo(dados, "rascunho", aviso=aviso)

    if documentos is None:
        documento = oficio.documentos.filter(tipo="oficio").order_by("-versao").first()
    else:
        documento = max((d for d in documentos if d.tipo == "oficio" and d.oficio_id == oficio.pk),
                        key=lambda d: d.versao, default=None)
    if documento is None:
        return ProjecaoEprotocolo(None, "emissao", aviso=_INDISPONIVEL)
    try:
        dados = _dados_do_snapshot(documento.dados)
    except _SnapshotInvalido:
        return ProjecaoEprotocolo(None, "emissao", documento.versao,
                                 documento.situacao, _INDISPONIVEL)
    aviso = _aviso_da_origem(oficio, dados.campos[3].valor, historico=True)
    if oficio.situacao == "cancelado":
        aviso = f"Ofício cancelado: dados históricos da emissão. {aviso}".strip()
    elif oficio.arquivado:
        aviso = f"Ofício arquivado. {aviso}".strip()
    return ProjecaoEprotocolo(dados, "emissao", documento.versao, documento.situacao, aviso)
