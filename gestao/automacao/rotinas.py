"""Rotina diária da automação (a retenção roda mesmo sem o worker no ar)."""

from __future__ import annotations


def registrar() -> None:
    from gestao.plataforma.rotinas import registrar_rotina

    from . import manutencao

    registrar_rotina("manutenção da automação (validade e retenção)", manutencao.diaria)
