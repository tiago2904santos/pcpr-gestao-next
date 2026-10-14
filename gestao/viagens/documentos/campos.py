"""Campos do cadastro que aparecem no documento e podem ser escritos de dentro dele.

Cada campo vinculado é um ``<span data-campo="chave">`` no modelo. Editar o trecho na folha
grava no ofício (pelos serviços, com a mesma concorrência otimista do formulário), e toda
renderização lê o valor atual — por isso o texto em volta pode ser editado sem congelar o
que vem do cadastro.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CampoVinculado:
    chave: str
    atributo: str          # campo do modelo Oficio
    rotulo: str
    documento: str         # "oficio" | "justificativa"
    obrigatorio: bool = False
    multilinha: bool = False
    maximo: int = 2000
    secao: str = "dados"   # cartão da folha de edição que também o mostra
    # "texto" grava a string; "data" converte de dd/mm/aaaa para date antes de gravar.
    formato: str = "texto"


CAMPOS: dict[str, CampoVinculado] = {c.chave: c for c in [
    CampoVinculado("data_oficio", "data_oficio", "Data do ofício", "oficio",
                   obrigatorio=True, maximo=10, formato="data"),
    CampoVinculado("protocolo", "protocolo", "Protocolo do eProtocolo", "oficio",
                   obrigatorio=True, maximo=20),
    CampoVinculado("motivo", "motivo", "Motivo da viagem", "oficio", obrigatorio=True,
                   multilinha=True),
    CampoVinculado("custeio_instituicao", "custeio_instituicao", "Instituição que custeia",
                   "oficio", maximo=160),
    CampoVinculado("justificativa", "justificativa", "Justificativa", "justificativa",
                   obrigatorio=True, multilinha=True, maximo=4000, secao="justificativa"),
]}


def campos_do_documento(tipo: str) -> list[CampoVinculado]:
    return [c for c in CAMPOS.values() if c.documento == tipo]


# Saída e chegada de cada trecho do roteiro ("trecho_3_saida"): escritas no documento como
# "dd/mm/aaaa hh:mm", gravam no trecho — mudar a saída leva a chegada junto (os tempos
# ficam); mudar a chegada refaz o tempo de viagem. As diárias se recalculam.
_TRECHO = re.compile(r"^trecho_(\d{1,2})_(saida|chegada)$")


def trecho_do_campo(chave: str) -> tuple[int, str] | None:
    m = _TRECHO.match(chave or "")
    return (int(m.group(1)), m.group(2)) if m else None


def campo_de(chave: str) -> CampoVinculado | None:
    """O campo vinculado da chave: um dos fixos ou a saída/chegada de um trecho."""
    if chave in CAMPOS:
        return CAMPOS[chave]
    if chave == "destinos":
        # "Destino da viagem": trocar o nome de um destino (Cidade/UF) troca a cidade em
        # todos os trechos do roteiro. Incluir ou tirar destino é no roteiro da folha.
        return CampoVinculado("destinos", "", "Destinos da viagem", "oficio", obrigatorio=True,
                              maximo=600, secao="roteiro", formato="destinos")
    trecho = trecho_do_campo(chave)
    if trecho is None:
        return None
    ordem, lado = trecho
    rotulo = f"{'Saída' if lado == 'saida' else 'Chegada'} do trecho {ordem}"
    return CampoVinculado(chave, "", rotulo, "oficio", obrigatorio=True, maximo=16,
                          secao="roteiro", formato="trecho")
