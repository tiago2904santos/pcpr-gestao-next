"""Antecedência mínima e obrigatoriedade da justificativa.

Regra (comportamento observado na referência e no texto do Decreto nº 6.358/2024
citado nas justificativas): a solicitação deve chegar com **mais de** N dias de
antecedência (N = configuração institucional, padrão 10). Quando a antecedência —
dias entre a data do ofício e a data (local) da primeira saída — é **igual ou
menor** que N, ou a saída é anterior ao ofício, a justificativa é obrigatória.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class SituacaoPrazo(StrEnum):
    INDEFINIDA = "indefinida"      # sem data de saída ainda
    NO_PRAZO = "no_prazo"          # antecedência > prazo
    FORA_DO_PRAZO = "fora_do_prazo"  # antecedência <= prazo
    RETROATIVA = "retroativa"      # saída antes da data do ofício


@dataclass(frozen=True)
class AvaliacaoPrazo:
    situacao: SituacaoPrazo
    dias_antecedencia: int | None
    prazo_dias: int
    data_oficio: date
    primeira_saida: date | None

    @property
    def justificativa_obrigatoria(self) -> bool:
        return self.situacao in {SituacaoPrazo.FORA_DO_PRAZO, SituacaoPrazo.RETROATIVA}

    @property
    def mensagem(self) -> str:
        if self.situacao is SituacaoPrazo.INDEFINIDA or self.primeira_saida is None:
            return "Informe a data de saída para avaliar o prazo."
        saida = f"{self.primeira_saida:%d/%m/%Y}"
        if self.situacao is SituacaoPrazo.RETROATIVA:
            return (f"A viagem começou em {saida}, antes da data do ofício "
                    f"({self.data_oficio:%d/%m/%Y}). Justificativa obrigatória.")
        if self.situacao is SituacaoPrazo.FORA_DO_PRAZO:
            dias = self.dias_antecedencia
            return (f"A viagem começa em {saida}: {dias} dia{'s' if dias != 1 else ''} de "
                    f"antecedência, e o prazo exige mais de {self.prazo_dias}. "
                    "Justificativa obrigatória.")
        return (f"A viagem começa em {saida}, com {self.dias_antecedencia} dias de "
                "antecedência: dentro do prazo, justificativa dispensada.")


def avaliar_prazo(
    data_oficio: date, primeira_saida: date | None, prazo_dias: int
) -> AvaliacaoPrazo:
    if primeira_saida is None:
        return AvaliacaoPrazo(SituacaoPrazo.INDEFINIDA, None, prazo_dias, data_oficio, None)
    dias = (primeira_saida - data_oficio).days
    if dias < 0:
        situacao = SituacaoPrazo.RETROATIVA
    elif dias <= prazo_dias:
        situacao = SituacaoPrazo.FORA_DO_PRAZO
    else:
        situacao = SituacaoPrazo.NO_PRAZO
    return AvaliacaoPrazo(situacao, dias, prazo_dias, data_oficio, primeira_saida)
