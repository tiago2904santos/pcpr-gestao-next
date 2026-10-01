"""Salvaguardas por ambiente (LAB / DEV / STAGING / PRODUCTION / TEST).

Regras (docs/adr/0010-ambientes-e-segredos.md):
- operações destrutivas (apagar dados, recriar banco, carga sintética) só em
  LAB, DEV e TEST;
- ferramentas do agente operam em PRODUCTION somente em leitura.
"""

from __future__ import annotations

from django.conf import settings

AMBIENTES = ("lab", "dev", "staging", "production", "test")
DESTRUTIVOS_PERMITIDOS = frozenset({"lab", "dev", "test"})


class OperacaoBloqueadaPorAmbiente(RuntimeError):
    pass


def atual() -> str:
    return getattr(settings, "APP_ENV", "dev")


def exigir_ambiente_destrutivo(operacao: str) -> None:
    if atual() not in DESTRUTIVOS_PERMITIDOS:
        raise OperacaoBloqueadaPorAmbiente(
            f"'{operacao}' é destrutiva e só pode rodar em LAB/DEV/TEST (ambiente atual: "
            f"{atual().upper()})."
        )


def eh_producao() -> bool:
    return atual() == "production"
