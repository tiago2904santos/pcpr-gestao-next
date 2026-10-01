"""Salvaguardas por ambiente (LAB / DEV / PREVIEW / STAGING / PRODUCTION / TEST).

Regras (docs/adr/0010-ambientes-e-segredos.md e 0011-ambiente-preview-demo.md):
- operações destrutivas (apagar dados, recriar banco, carga sintética) só em
  LAB, DEV e TEST; o dataset de demonstração só em PREVIEW (e TEST);
- a entrada sem senha (DEMO) só vale com APP_ENV=preview **e** DEMO_MODE=true;
- ferramentas do agente operam em PRODUCTION somente em leitura.
"""

from __future__ import annotations

from django.conf import settings

AMBIENTES = ("lab", "dev", "preview", "staging", "production", "test")
DESTRUTIVOS_PERMITIDOS = frozenset({"lab", "dev", "test"})
DEMONSTRACAO_PERMITIDA = frozenset({"preview", "test"})


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


def exigir_ambiente_de_demonstracao(operacao: str) -> None:
    """Dataset DEMO (apaga e recria tudo): só no PREVIEW (e nos testes)."""
    if atual() not in DEMONSTRACAO_PERMITIDA:
        raise OperacaoBloqueadaPorAmbiente(
            f"'{operacao}' apaga e recria os dados de demonstração e só roda em PREVIEW "
            f"(ambiente atual: {atual().upper()})."
        )


def demo_ativo() -> bool:
    """Entrada sem senha do usuário de demonstração. Nunca fora do PREVIEW."""
    return atual() == "preview" and getattr(settings, "DEMO_MODE", False) is True


def exigir_demo_somente_no_preview() -> None:
    """Falha o startup se DEMO_MODE estiver ligado fora do PREVIEW."""
    from django.core.exceptions import ImproperlyConfigured

    if getattr(settings, "DEMO_MODE", False) and atual() != "preview":
        raise ImproperlyConfigured(
            f"DEMO_MODE=true com APP_ENV={atual()}: a entrada sem senha só existe no PREVIEW."
        )
