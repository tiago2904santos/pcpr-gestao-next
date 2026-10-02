"""Bate-volta: viagens que saem da sede e voltam no mesmo dia, repetidas por vários dias.

Domínio puro (sem Django). Um bloco diz destino, período e os dois horários do dia; a
expansão devolve as pernas na ordem em que acontecem — duas por dia, ida e volta. Quem grava
os trechos é o serviço; aqui só existe calendário.

Especificação: docs/superpowers/specs/2026-10-02-bate-volta-design.md
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from itertools import pairwise


class BateVoltaInvalido(ValueError):
    """Bloco que não descreve um bate-volta (mensagem pronta para o usuário)."""


@dataclass(frozen=True)
class Bloco:
    """Um destino visitado todo dia de um período, com os mesmos horários."""

    destino_id: int
    dia_inicial: date
    dia_final: date
    hora_saida: time
    hora_volta: time

    @property
    def dias(self) -> int:
        return (self.dia_final - self.dia_inicial).days + 1


@dataclass(frozen=True)
class Perna:
    """Um deslocamento gerado: de onde sai, para onde vai e quando sai."""

    origem_id: int
    destino_id: int
    saida_em: datetime


def validar(blocos: list[Bloco]) -> None:
    """Recusa o que o banco não consegue recusar sozinho: período invertido, volta antes da
    saída e blocos que se sobrepõem no calendário."""
    for i, bloco in enumerate(blocos, start=1):
        if bloco.dia_final < bloco.dia_inicial:
            raise BateVoltaInvalido(
                f"Bate-volta {i}: o último dia não pode ser antes do primeiro.")
        if bloco.hora_volta <= bloco.hora_saida:
            raise BateVoltaInvalido(
                f"Bate-volta {i}: a volta precisa ser depois da saída, no mesmo dia.")
    for i, (a, b) in enumerate(pairwise(blocos), start=1):
        if b.dia_inicial <= a.dia_final:
            raise BateVoltaInvalido(
                f"Bate-volta {i + 1} começa antes de o {i} terminar: os períodos não podem "
                "se sobrepor.")


def expandir(blocos: list[Bloco], sede_id: int) -> list[Perna]:
    """Pernas de todos os blocos, na ordem: por bloco e, dentro dele, dia a dia."""
    validar(blocos)
    pernas: list[Perna] = []
    for bloco in blocos:
        if bloco.destino_id == sede_id:
            raise BateVoltaInvalido("O destino do bate-volta não pode ser a própria sede.")
        for passo in range(bloco.dias):
            dia = bloco.dia_inicial + timedelta(days=passo)
            pernas.append(Perna(sede_id, bloco.destino_id,
                                datetime.combine(dia, bloco.hora_saida)))
            pernas.append(Perna(bloco.destino_id, sede_id,
                                datetime.combine(dia, bloco.hora_volta)))
    return pernas
