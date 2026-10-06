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
from urllib.parse import urlsplit

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
    # Permissão para o módulo aparecer (no menu e na central de módulos).
    requer: str | None = None


_MODULOS: dict[str, Modulo] = {}

# Menu superior sem transbordo (ADR 0006): links diretos + menus suspensos por módulo.
MAX_ENTRADAS_NA_BARRA = 7

# Onde a sessão guarda a tarefa que ficou aberta em outra tela (ver pagina_anterior).
CHAVE_TAREFA = "tarefa_aberta"


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
        if modulo.requer and not usuario.has_perm(modulo.requer):
            continue
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


def _rotulo_de(caminho: str) -> str:
    """O nome da página do caminho, pelo item de navegação de prefixo mais longo."""
    melhor = ("", "")
    for modulo in modulos():
        url_modulo = _url(modulo.url_name)
        if url_modulo and caminho.startswith(url_modulo) and len(url_modulo) > len(melhor[0]):
            melhor = (url_modulo, modulo.rotulo)
        for grupo in modulo.grupos:
            for item in grupo.itens:
                url = _url(item.url_name)
                if url and caminho.startswith(url) and len(url) > len(melhor[0]):
                    melhor = (url, item.rotulo)
    return melhor[1]


def _area(caminho: str) -> str:
    """Primeiro segmento do caminho ("viagens", "cadastros"…) — a "área" do sistema."""
    partes = caminho.strip("/").split("/")
    return partes[0] if partes and partes[0] else ""


def pagina_anterior(request: HttpRequest) -> dict[str, str] | None:
    """A tarefa que ficou aberta em outra tela, para o botão "Voltar para …".

    Nasce do `?de=<caminho>&de_rotulo=<nome>` do link que trouxe a pessoa: sair da folha de
    um ofício para "Gerenciar textos prontos" e poder voltar **para aquele ofício**, não
    para a lista. Como a folha salva sozinha (autosave), voltar à mesma URL devolve o
    rascunho como estava.

    E **fica guardada na sessão**: o desvio costuma ter mais de um passo (abrir os textos
    prontos, ir para cadastros, procurar um servidor…). O botão acompanha a pessoa por
    qualquer página até ela voltar — chegar ao caminho guardado apaga a marca.

    Só endereço interno entra (`url_has_allowed_host_and_scheme`); o rótulo vem da URL,
    então é cortado e o template o escapa.
    """
    from django.utils.http import url_has_allowed_host_and_scheme

    if request.method != "GET":
        return None
    sessao = getattr(request, "session", None)

    def interno(url: str) -> bool:
        return bool(url) and url.startswith("/") and url_has_allowed_host_and_scheme(
            url, allowed_hosts={request.get_host()}, require_https=request.is_secure())

    pedido = request.GET.get("de") or ""
    if interno(pedido) and pedido != request.get_full_path():
        rotulo = (espacos(request.GET.get("de_rotulo") or "")[:60]
                  or _rotulo_de(urlsplit(pedido).path) or "a página anterior")
        tarefa = {"url": pedido, "rotulo": rotulo}
        if sessao is not None:
            sessao[CHAVE_TAREFA] = tarefa
        return tarefa

    if sessao is None:
        return None
    tarefa = sessao.get(CHAVE_TAREFA)
    if not isinstance(tarefa, dict) or not interno(tarefa.get("url", "")):
        sessao.pop(CHAVE_TAREFA, None)
        return None
    # Chegou onde tinha parado: a tarefa deixou de estar aberta.
    if urlsplit(tarefa["url"]).path == request.path:
        del sessao[CHAVE_TAREFA]
        return None
    return tarefa


def espacos(texto: str) -> str:
    """Tira as pontas e junta espaços repetidos (o rótulo vem da URL)."""
    return " ".join(texto.split())
