"""Carga de dados de referência públicos (municípios do IBGE)."""

from __future__ import annotations

import csv
from pathlib import Path

CSV_MUNICIPIOS = Path(__file__).resolve().parent / "dados" / "municipios_ibge.csv"


def linhas_municipios() -> list[dict[str, str]]:
    with CSV_MUNICIPIOS.open(encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo, delimiter=";"))


def garantir_municipios(modelo=None) -> int:
    """Carrega a lista oficial se a tabela estiver vazia. Retorna o total."""
    if modelo is None:
        from .models import Municipio as modelo
    if not modelo.objects.exists():
        modelo.objects.bulk_create(
            [modelo(codigo_ibge=linha["codigo_ibge"], nome=linha["nome"], uf=linha["uf"])
             for linha in linhas_municipios()],
            batch_size=2000, ignore_conflicts=True,
        )
    return modelo.objects.count()
