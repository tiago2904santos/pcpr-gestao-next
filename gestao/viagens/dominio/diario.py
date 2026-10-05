"""Diário de bordo em Python puro: a conferência do hodômetro (paridade com
`conferir_hodometro` da referência; textos dela).

Tudo é aviso — nada impede de salvar, exceto o km final menor que o inicial na mesma
linha (o banco recusa):
- o km de saída de um trecho menor que o de chegada do anterior (voltou para trás);
- o rodado de um trecho fora da tolerância da distância prevista (20%, nunca menos de
  10 km — desvio, abastecimento, entrada na cidade);
- o km de saída da primeira linha menor que o último km registrado da mesma viatura.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TOLERANCIA_KM_PERCENTUAL = 20
TOLERANCIA_KM_MINIMA = 10


def tolerancia_km(prevista: int) -> int:
    return max(TOLERANCIA_KM_MINIMA, (prevista * TOLERANCIA_KM_PERCENTUAL + 99) // 100)


def km(valor: int) -> str:
    """1234 → "1.234"."""
    return f"{int(valor):,}".replace(",", ".")


def numero_do_km(texto: object) -> int | None:
    """O que a pessoa digitou ("12.345", "12345 km") → 12345; vazio → None."""
    digitos = "".join(c for c in str(texto or "") if c.isdigit())
    return int(digitos) if digitos else None


@dataclass(frozen=True)
class Linha:
    rota: str  # "Curitiba/PR → Londrina/PR"
    km_inicial: int | None
    km_final: int | None
    prevista: int | None  # distância prevista do trecho (km)


@dataclass(frozen=True)
class UltimoKm:
    km: int
    data: str  # dd/mm/aaaa
    oficio: str  # 12/2026


@dataclass
class Conferencia:
    rodados: list[int | None] = field(default_factory=list)
    total_rodado: int = 0
    total_previsto: int = 0
    avisos: list[str] = field(default_factory=list)


def conferir(linhas: list[Linha], ultimo: UltimoKm | None = None) -> Conferencia:
    c = Conferencia()
    primeira = linhas[0] if linhas else None
    if (ultimo and primeira is not None and primeira.km_inicial is not None
            and primeira.km_inicial < ultimo.km):
        c.avisos.append(
            f"O km de saída ({km(primeira.km_inicial)}) é menor que o último km registrado "
            f"desta viatura ({km(ultimo.km)}, em {ultimo.data}, Ofício {ultimo.oficio}).")
    anterior: Linha | None = None
    for linha in linhas:
        rodado = None
        if linha.km_inicial is not None and linha.km_final is not None:
            rodado = linha.km_final - linha.km_inicial
            c.total_rodado += rodado
        if linha.prevista:
            c.total_previsto += linha.prevista
        if (anterior is not None and anterior.km_final is not None
                and linha.km_inicial is not None and linha.km_inicial < anterior.km_final):
            c.avisos.append(
                f"{linha.rota}: o km de saída ({km(linha.km_inicial)}) é menor que o de "
                f"chegada do trecho anterior ({km(anterior.km_final)}) — o hodômetro voltou "
                "para trás.")
        if (rodado is not None and linha.prevista
                and abs(rodado - linha.prevista) > tolerancia_km(linha.prevista)):
            c.avisos.append(
                f"{linha.rota}: {km(rodado)} km rodados, e a distância prevista é de "
                f"{km(linha.prevista)} km (diferença de {km(abs(rodado - linha.prevista))} km).")
        c.rodados.append(rodado)
        anterior = linha
    return c


def preenchido(linhas: list[Linha]) -> bool:
    """Todos os trechos com km inicial e final (o que a finalização cobra)."""
    return bool(linhas) and all(
        linha.km_inicial is not None and linha.km_final is not None for linha in linhas)
