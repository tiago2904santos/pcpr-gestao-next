"""Configuração da porta de IA, lida em um lugar só.

Fonte: `settings.IA` (dict montado das variáveis de ambiente em `config/settings/base.py`);
sem ele, as próprias variáveis `IA_*`. Nada de segredo em código ou documento.

- `modo`: `simulado` (padrão em todo ambiente; nada sai para a rede) ou `anthropic`.
- O modo real só vale com `IA_MODO=anthropic` **e** `IA_API_KEY` **e** fora do PREVIEW: no
  PREVIEW/DEMO público a IA é sempre simulada (o mesmo princípio da ADR 0046 para o WhatsApp).
- Preços: tabela oficial por milhão de tokens (prompt até 100 mil tokens), usada só para o
  custo **estimado**. Estimativa não é cobrança: a fatura é a do provedor.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings

from gestao.plataforma import ambiente

SIMULADO = "simulado"
ANTHROPIC = "anthropic"
MODOS = (SIMULADO, ANTHROPIC)

MODELO_PADRAO = "claude-opus-5-5"
BASE_URL = "https://api.anthropic.com"
VERSAO_API = "2023-06-01"
#: Beta do recurso de "fallback" no servidor (troca de modelo quando o primeiro recusa).
BETA_FALLBACK = "server-side-fallback-2026-07-01"


@dataclass(frozen=True)
class Preco:
    """US$ por milhão de tokens (entrada, saída, leitura de cache)."""

    entrada: Decimal
    saida: Decimal
    cache_lido: Decimal


#: Preços oficiais consultados em 17/10/2026 (docs/automacao/desempenho-e-custos.md §11.2).
PRECOS: dict[str, Preco] = {
    "claude-opus-5-5": Preco(Decimal("4.00"), Decimal("20.00"), Decimal("0.20")),
    "claude-sonnet-5-5": Preco(Decimal("2.00"), Decimal("10.00"), Decimal("0.10")),
    "claude-haiku-5-5": Preco(Decimal("0.10"), Decimal("0.50"), Decimal("0.01")),
}
SEM_CUSTO = Preco(Decimal(0), Decimal(0), Decimal(0))
MILHAO = Decimal(1_000_000)


def preco_de(modelo: str) -> Preco | None:
    return PRECOS.get(modelo)


def custo_estimado(modelo: str, entrada: int, saida: int, cache_lido: int = 0) -> Decimal:
    """Custo ESTIMADO em US$ (tokens × tabela). Modelo fora da tabela → o mais caro dela,
    para nunca subestimar o orçamento."""
    p = PRECOS.get(modelo) or max(PRECOS.values(), key=lambda x: x.saida)
    total = (Decimal(entrada) * p.entrada + Decimal(saida) * p.saida
             + Decimal(cache_lido) * p.cache_lido) / MILHAO
    return total.quantize(Decimal("0.000001"))


@dataclass(frozen=True)
class Configuracao:
    modo: str = SIMULADO
    modelo: str = MODELO_PADRAO
    api_key: str = field(default="", repr=False)
    base_url: str = BASE_URL
    timeout: float = 30.0
    max_tentativas: int = 2
    max_tokens_saida: int = 2000
    limite_entrada_caracteres: int = 24_000
    esforco: str = "low"
    fallback_no_servidor: bool = True
    bloqueado_no_ambiente: bool = False  # pediram o modo real onde não pode (PREVIEW)

    @property
    def real(self) -> bool:
        return (self.modo == ANTHROPIC and bool(self.api_key)
                and not self.bloqueado_no_ambiente)

    def faltantes(self) -> list[str]:
        return [] if self.api_key else ["IA_API_KEY"]

    def descricao(self) -> str:
        if self.bloqueado_no_ambiente:
            return "Simulada — o PREVIEW público nunca chama um provedor de IA"
        if self.modo == SIMULADO:
            return "Simulada (nada sai para a rede; sem custo)"
        if not self.real:
            return "Simulada — falta a chave do provedor (IA_API_KEY)"
        return f"Anthropic · {self.modelo}"


def _bruto() -> dict:
    valor = getattr(settings, "IA", None)
    if isinstance(valor, dict):
        return dict(valor)
    env = os.environ.get
    return {
        "modo": env("IA_MODO", SIMULADO), "modelo": env("IA_MODELO", MODELO_PADRAO),
        "api_key": env("IA_API_KEY", ""), "base_url": env("IA_BASE_URL", BASE_URL),
        "timeout": env("IA_TIMEOUT", "30"), "max_tentativas": env("IA_MAX_TENTATIVAS", "2"),
        "max_tokens_saida": env("IA_MAX_TOKENS_SAIDA", "2000"),
        "limite_entrada_caracteres": env("IA_LIMITE_ENTRADA", "24000"),
        "esforco": env("IA_ESFORCO", "low"),
        "fallback_no_servidor": env("IA_FALLBACK_SERVIDOR", "true"),
    }


def _inteiro(valor: object, padrao: int, teto: int) -> int:
    try:
        return min(teto, max(1, int(str(valor))))
    except (TypeError, ValueError):
        return padrao


def _real(valor: object, padrao: float, teto: float) -> float:
    try:
        return min(teto, max(1.0, float(str(valor))))
    except (TypeError, ValueError):
        return padrao


def carregar() -> Configuracao:
    bruto = _bruto()
    modo = str(bruto.get("modo") or SIMULADO).strip().lower()
    if modo not in MODOS:
        modo = SIMULADO
    bloqueado = modo == ANTHROPIC and ambiente.atual() == "preview"
    modelo = str(bruto.get("modelo") or MODELO_PADRAO).strip()
    base = str(bruto.get("base_url") or BASE_URL).strip().rstrip("/")
    if not base.startswith("https://"):
        base = BASE_URL
    esforco = str(bruto.get("esforco") or "low").strip().lower()
    if esforco not in ("low", "medium", "high"):
        esforco = "low"
    fallback = str(bruto.get("fallback_no_servidor", "true")).strip().lower()
    return Configuracao(
        modo=modo, modelo=modelo,
        api_key=str(bruto.get("api_key") or "").strip(),
        base_url=base,
        timeout=_real(bruto.get("timeout"), 30.0, 120.0),
        max_tentativas=_inteiro(bruto.get("max_tentativas"), 2, 3),
        max_tokens_saida=_inteiro(bruto.get("max_tokens_saida"), 2000, 8000),
        limite_entrada_caracteres=_inteiro(bruto.get("limite_entrada_caracteres"), 24_000,
                                           100_000),
        esforco=esforco,
        fallback_no_servidor=fallback not in {"false", "0", "no", "nao", "não"},
        bloqueado_no_ambiente=bloqueado,
    )
