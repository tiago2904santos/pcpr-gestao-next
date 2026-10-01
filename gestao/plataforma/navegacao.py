"""Registro de navegação (menu superior).

Cada contexto de negócio registra seu módulo no `AppConfig.ready()`; a
plataforma só monta o menu, sem conhecer os contextos (inversão de
dependência). Itens podem exigir uma permissão (`requer`).

Na barra superior, grupos comuns viram links diretos; grupos com
`em_menu=True` viram um menu suspenso (ex.: "Cadastros ▾"). Regra do Design
System: no máximo 7 entradas de primeiro nível por módulo — o resto vai para
menus (docs/design-system/navigation.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.http import HttpRequest
from django.urls import NoReverseMatch, reverse


@dataclass(frozen=True)
class Item:
    rotulo: str
    url_name: str
    icone: str
    requer: str | None = None
    # Prefixos de caminho que também marcam o item como ativo.
    ativo_em: tuple[str, ...] = ()


@dataclass(frozen=True)
class Grupo:
    rotulo: str
    itens: tuple[Item, ...]
    em_menu: bool = False


@dataclass(frozen=True)
class Modulo:
    chave: str
    rotulo: str
    icone: str
    url_name: str
    descricao: str = ""
    grupos: tuple[Grupo, ...] = field(default_factory=tuple)
    ordem: int = 100


_MODULOS: dict[str, Modulo] = {}

# Menu superior sem transbordo (ADR 0006): links diretos + menus suspensos por módulo.
MAX_ENTRADAS_NA_BARRA = 7


def entradas_na_barra(modulo: Modulo) -> int:
    """Entradas de primeiro nível: cada item de grupo comum + um por grupo suspenso."""
    return sum(1 if g.em_menu else len(g.itens) for g in modulo.grupos)


def registrar_modulo(modulo: Modulo) -> None:
    if entradas_na_barra(modulo) > MAX_ENTRADAS_NA_BARRA:
        raise ValueError(
            f"Módulo {modulo.chave!r} teria {entradas_na_barra(modulo)} entradas no menu "
            f"superior (máximo {MAX_ENTRADAS_NA_BARRA}): agrupe o excedente num menu suspenso."
        )
    _MODULOS[modulo.chave] = modulo


def modulos() -> list[Modulo]:
    return sorted(_MODULOS.values(), key=lambda m: m.ordem)


def _url(nome: str) -> str | None:
    try:
        return reverse(nome)
    except NoReverseMatch:
        return None


def navegacao_para(request: HttpRequest) -> dict[str, Any]:
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {"modulos": [], "atual": None}
    caminho = request.path
    visiveis: list[dict[str, Any]] = []
    atual: dict[str, Any] | None = None
    for modulo in modulos():
        grupos: list[dict[str, Any]] = []
        for grupo in modulo.grupos:
            itens: list[dict[str, Any]] = []
            for item in grupo.itens:
                if item.requer and not usuario.has_perm(item.requer):
                    continue
                url = _url(item.url_name)
                if url is None:
                    continue
                ativo = caminho.startswith(url) or any(caminho.startswith(p) for p in item.ativo_em)
                itens.append({"rotulo": item.rotulo, "url": url, "icone": item.icone,
                              "ativo": ativo, "tamanho_url": len(url)})
            if itens:
                grupos.append({"rotulo": grupo.rotulo, "itens": itens,
                               "em_menu": grupo.em_menu})
        url_modulo = _url(modulo.url_name)
        if not grupos and url_modulo is None:
            continue
        # Só o item de prefixo mais longo fica ativo (evita "Início" sempre aceso).
        todos = [i for g in grupos for i in g["itens"]]
        ativos = [i for i in todos if i["ativo"]]
        if ativos:
            melhor = max(ativos, key=lambda i: i["tamanho_url"])
            for i in todos:
                i["ativo"] = i is melhor
        for g in grupos:
            g["ativo"] = any(i["ativo"] for i in g["itens"])
        entrada = {"chave": modulo.chave, "rotulo": modulo.rotulo, "icone": modulo.icone,
                   "url": url_modulo, "descricao": modulo.descricao, "grupos": grupos,
                   "ativo": bool(ativos)}
        visiveis.append(entrada)
        if ativos and atual is None:
            atual = entrada
    return {"modulos": visiveis, "atual": atual}
