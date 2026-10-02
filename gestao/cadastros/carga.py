"""Carga de dados de referência públicos (municípios do IBGE)."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

CSV_MUNICIPIOS = Path(__file__).resolve().parent / "dados" / "municipios_ibge.csv"
CSV_COORDENADAS = Path(__file__).resolve().parent / "dados" / "municipios_coordenadas.csv"


def linhas_municipios() -> list[dict[str, str]]:
    with CSV_MUNICIPIOS.open(encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo, delimiter=";"))


def coordenadas() -> dict[str, tuple[Decimal, Decimal]]:
    with CSV_COORDENADAS.open(encoding="utf-8") as arquivo:
        return {linha["codigo_ibge"]: (Decimal(linha["latitude"]), Decimal(linha["longitude"]))
                for linha in csv.DictReader(arquivo, delimiter=";")}


def garantir_municipios(modelo=None) -> int:
    """Carrega a lista oficial se a tabela estiver vazia (com coordenadas). Retorna o total."""
    if modelo is None:
        from .models import Municipio as modelo
    if not modelo.objects.exists():
        # Na migração 0002 o modelo histórico ainda não tem coordenadas (vêm na 0003).
        com_coordenadas = any(f.name == "latitude" for f in modelo._meta.get_fields())
        coords = coordenadas() if com_coordenadas else {}

        def novo(linha: dict[str, str]):
            extra = {}
            if com_coordenadas:
                lat, lon = coords.get(linha["codigo_ibge"], (None, None))
                extra = {"latitude": lat, "longitude": lon}
            return modelo(codigo_ibge=linha["codigo_ibge"], nome=linha["nome"], uf=linha["uf"],
                          **extra)

        modelo.objects.bulk_create([novo(linha) for linha in linhas_municipios()],
                                   batch_size=2000, ignore_conflicts=True)
    return modelo.objects.count()


def preencher_coordenadas(modelo) -> int:
    """Completa latitude/longitude de municípios já carregados (migração)."""
    coords = coordenadas()
    faltando = list(modelo.objects.filter(latitude__isnull=True))
    for m in faltando:
        if m.codigo_ibge in coords:
            m.latitude, m.longitude = coords[m.codigo_ibge]
    modelo.objects.bulk_update(faltando, ["latitude", "longitude"], batch_size=2000)
    return len(faltando)
