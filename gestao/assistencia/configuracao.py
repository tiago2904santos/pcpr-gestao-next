"""Liga/desliga, modo e limites por uso. Sem linha: ligado no modo REGRA (sem IA) — a IA só
entra quando alguém que administra escolhe o modo IA para aquele uso."""

from __future__ import annotations

from django.db import transaction

from . import ganchos, policies
from .models import ConfiguracaoUso

LIMITES = {
    "max_chamadas_dia": (1, 1000),
    "max_pedidos_pessoa_dia": (1, 200),
    "max_tokens_saida": (100, 8000),
    "max_entrada_caracteres": (1000, 100_000),
    "tempo_limite_s": (1, 120),
    "max_tentativas": (1, 3),
}


def de(uso: str) -> ConfiguracaoUso:
    """A configuração em vigor (não grava nada)."""
    return ConfiguracaoUso.objects.filter(uso=uso).first() or ConfiguracaoUso(uso=uso)


def todas() -> dict[str, ConfiguracaoUso]:
    existentes = {c.uso: c for c in ConfiguracaoUso.objects.select_related("alterada_por")}
    return {u.chave: existentes.get(u.chave) or ConfiguracaoUso(uso=u.chave)
            for u in ganchos.usos()}


@transaction.atomic
def alterar(usuario, uso: str, *, ligado: bool, modo: str, motivo: str = "",
            **limites: int) -> ConfiguracaoUso:
    policies.exigir(policies.pode_administrar(usuario),
                    "Só quem administra a IA liga, desliga ou muda o modo de um uso.")
    if ganchos.uso(uso) is None:
        raise ValueError("Uso desconhecido.")
    if modo not in ConfiguracaoUso.Modo.values:
        raise ValueError("Modo inválido.")
    config, _ = ConfiguracaoUso.objects.select_for_update().get_or_create(uso=uso)
    config.ligado, config.modo = bool(ligado), modo
    for nome, valor in limites.items():
        if nome not in LIMITES:
            raise ValueError(f"Limite desconhecido: {nome}.")
        minimo, maximo = LIMITES[nome]
        if not minimo <= int(valor) <= maximo:
            rotulo = getattr(ConfiguracaoUso._meta.get_field(nome), "verbose_name", nome)
            raise ValueError(f"{rotulo}: entre {minimo} e {maximo}.")
        setattr(config, nome, int(valor))
    config.motivo = (motivo or "").strip()[:255]
    config.alterada_por = usuario
    config.save()
    return config
