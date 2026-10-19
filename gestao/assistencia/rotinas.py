"""Rotina diária da assistência (a retenção roda mesmo sem o worker no ar)."""

from __future__ import annotations


def registrar() -> None:
    from gestao.plataforma.rotinas import registrar_rotina

    from . import manutencao

    registrar_rotina("retenção da assistência por IA", manutencao.diaria)
