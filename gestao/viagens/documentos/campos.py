"""Campos do cadastro que aparecem no documento e podem ser escritos de dentro dele.

Cada campo vinculado é um ``<span data-campo="chave">`` no modelo. Editar o trecho na folha
grava no ofício (pelos serviços, com a mesma concorrência otimista do formulário), e toda
renderização lê o valor atual — por isso o texto em volta pode ser editado sem congelar o
que vem do cadastro.
"""

from __future__ import annotations

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


CAMPOS: dict[str, CampoVinculado] = {c.chave: c for c in [
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
