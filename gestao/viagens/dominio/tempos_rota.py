"""Tempo calibrado de estrada e adicional, conforme a referência confirmada.

Fonte e exemplos: docs/product/tempos-de-rota.md. Distâncias são quilômetros,
tempos são minutos; o provedor converte seus segundos com minutos_da_api primeiro.
"""

from __future__ import annotations

from decimal import Decimal

VELOCIDADE_MEDIA_KMH = 74.0
DISTANCIA_FIXA_KM = 12.0
PESO_DA_API = 0.15
PASSO_MIN = 15
VIAGEM_MINIMA_PARA_ADICIONAL_MIN = 30

Numero = int | float | Decimal


def minutos_da_api(segundos: Numero | None) -> int:
    """Segundos do provedor → minutos inteiros, com empate para par e mínimo zero."""
    return max(0, int(round(float(segundos or 0) / 60.0)))  # noqa: RUF046 — contrato da referência


def arredondar_a_15(minutos: Numero) -> int:
    """Inteiro primeiro; resto até cinco desce, acima de cinco sobe ao passo de 15."""
    inteiro = max(0, int(round(minutos)))  # noqa: RUF046 — inteiro antes do passo de 15
    resto = inteiro % PASSO_MIN
    base = inteiro - resto
    return base if resto <= 5 else base + PASSO_MIN


def tempo_de_viagem(distancia_km: Numero, duracao_api_min: Numero | None) -> int:
    """Mistura 85% da estimativa calibrada com 15% dos minutos informados pela API."""
    calibrado = (float(distancia_km) + DISTANCIA_FIXA_KM) / VELOCIDADE_MEDIA_KMH * 60.0
    combinado = (1 - PESO_DA_API) * calibrado + PESO_DA_API * float(duracao_api_min or 0)
    return arredondar_a_15(combinado)


def tempo_adicional_sugerido(tempo_viagem_min: Numero) -> int:
    """Abaixo de 30 min, zero; demais, 1/6 da viagem arredondado, mínimo 15 min."""
    if tempo_viagem_min < VIAGEM_MINIMA_PARA_ADICIONAL_MIN:
        return 0
    # A viagem persistida é inteira; Decimal também funciona sem dividir Decimal por float.
    minutos = float(tempo_viagem_min) if isinstance(tempo_viagem_min, Decimal) else tempo_viagem_min
    return max(PASSO_MIN, arredondar_a_15(minutos / 6.0))
