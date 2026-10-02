"""Rotas entre municípios: distância, tempo de estrada e traçado para o mapa (ADR 0016).

Provedores (settings.ROTAS_PROVEDOR): "osrm" (ROTAS_URL), "openrouteservice" (ROTAS_CHAVE)
ou "estimativa". Qualquer falha do provedor cai na estimativa offline — o formulário nunca
depende da rede para funcionar. Resultados de provedor ficam em cache (DistanciaMunicipios).
"""

from __future__ import annotations

import json
import logging
import math
import urllib.request
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

from gestao.cadastros.models import Municipio

from .models import DistanciaMunicipios

log = logging.getLogger(__name__)

FATOR_ESTRADA = 1.3  # linha reta → estrada (estimativa)
VELOCIDADE_MEDIA_KMH = 70
ARREDONDAMENTO_MIN = 15  # como na referência: tempo de viagem em múltiplos de 15 min
MAX_PONTOS_TRACADO = 250


@dataclass(frozen=True)
class Perna:
    km: Decimal
    minutos: int
    fonte: str
    tracado: list[list[float]] = field(default_factory=list)  # [[lat, lon], ...]

    @property
    def adicional_sugerido(self) -> int:
        return tempo_adicional_sugerido(self.minutos)


def tempo_adicional_sugerido(minutos: int) -> int:
    """Pausas: 15 min a cada 2 h completas de estrada (ex.: 4h30 → 30 min)."""
    return (minutos // 120) * 15


def arredondar_minutos(minutos: float) -> int:
    """Para cima, em múltiplos de 15 min (mínimo 15)."""
    return max(ARREDONDAMENTO_MIN, math.ceil(minutos / ARREDONDAMENTO_MIN) * ARREDONDAMENTO_MIN)


def _coords(m: Municipio) -> tuple[float, float] | None:
    if m.latitude is None or m.longitude is None:
        return None
    return float(m.latitude), float(m.longitude)


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def estimar(origem: Municipio, destino: Municipio) -> Perna:
    a, b = _coords(origem), _coords(destino)
    if a is None or b is None:
        return Perna(Decimal(0), ARREDONDAMENTO_MIN, "estimativa")
    km = _haversine_km(a, b) * FATOR_ESTRADA
    return Perna(Decimal(str(round(km, 1))), arredondar_minutos(km / VELOCIDADE_MEDIA_KMH * 60),
                 "estimativa", [list(a), list(b)])


def _simplificar(pontos: list[list[float]]) -> list[list[float]]:
    if len(pontos) <= MAX_PONTOS_TRACADO:
        return pontos
    passo = len(pontos) / (MAX_PONTOS_TRACADO - 1)
    return [pontos[int(i * passo)] for i in range(MAX_PONTOS_TRACADO - 1)] + [pontos[-1]]


def _baixar_json(url: str, *, corpo: dict | None = None, cabecalhos: dict | None = None):
    if not url.startswith(("https://", "http://")):
        raise ValueError("URL de rotas inválida")
    dados = json.dumps(corpo).encode() if corpo is not None else None
    pedido = urllib.request.Request(url, data=dados, headers={  # noqa: S310
        "Accept": "application/json", "Content-Type": "application/json",
        "User-Agent": "pcpr-gestao/1.0", **(cabecalhos or {})})
    with urllib.request.urlopen(pedido, timeout=settings.ROTAS_TIMEOUT) as resposta:  # noqa: S310  # nosec B310 — esquema verificado acima
        return json.loads(resposta.read().decode())


def _osrm(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float, list]:
    base = settings.ROTAS_URL.rstrip("/")
    url = (f"{base}/route/v1/driving/{a[1]:.5f},{a[0]:.5f};{b[1]:.5f},{b[0]:.5f}"
           "?overview=full&geometries=geojson")
    rota = _baixar_json(url)["routes"][0]
    return rota["distance"], rota["duration"], rota["geometry"]["coordinates"]


def _openrouteservice(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float, list]:
    base = (settings.ROTAS_URL or "https://api.openrouteservice.org").rstrip("/")
    dados = _baixar_json(f"{base}/v2/directions/driving-car/geojson",
                         corpo={"coordinates": [[a[1], a[0]], [b[1], b[0]]]},
                         cabecalhos={"Authorization": settings.ROTAS_CHAVE})
    rota = dados["features"][0]
    resumo = rota["properties"]["summary"]
    return resumo["distance"], resumo["duration"], rota["geometry"]["coordinates"]


PROVEDORES = {"osrm": _osrm, "openrouteservice": _openrouteservice}


def calcular(origem: Municipio, destino: Municipio) -> Perna:
    """Rota de origem a destino: cache → provedor configurado → estimativa."""
    if origem.pk == destino.pk:
        return Perna(Decimal(0), 0, "estimativa")
    provedor = PROVEDORES.get(settings.ROTAS_PROVEDOR)
    if provedor is None:
        return estimar(origem, destino)
    em_cache = DistanciaMunicipios.objects.filter(origem=origem, destino=destino).first()
    if em_cache:
        return Perna(em_cache.km, em_cache.minutos, em_cache.fonte, em_cache.geometria)
    a, b = _coords(origem), _coords(destino)
    if a is None or b is None:
        return estimar(origem, destino)
    try:
        metros, segundos, coordenadas = provedor(a, b)
    except Exception:  # rede, cota, formato: a estimativa mantém o formulário funcionando
        log.warning("Rota indisponível (%s): %s → %s", settings.ROTAS_PROVEDOR, origem, destino,
                    exc_info=True)
        return estimar(origem, destino)
    km = Decimal(str(metros / 1000)).quantize(Decimal("0.1"), ROUND_HALF_UP)
    tracado = _simplificar([[round(lat, 5), round(lon, 5)] for lon, lat in coordenadas])
    perna = Perna(km, arredondar_minutos(segundos / 60), settings.ROTAS_PROVEDOR, tracado)
    DistanciaMunicipios.objects.update_or_create(
        origem=origem, destino=destino,
        defaults={"km": perna.km, "minutos": perna.minutos, "geometria": tracado,
                  "fonte": perna.fonte})
    return perna
