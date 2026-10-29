"""Ganchos que os contextos de negócio registram no `ready()` (a automação não importa
nenhum deles — import-linter):

- `TipoComunicacao`: o que é a mensagem, de que fluxo, por quanto tempo vale e — o mais
  importante — `preparar(contexto)`, que relê o assunto **no momento do envio** e diz se a
  mensagem ainda faz sentido, em que versão e com que texto. Quem decide o que é verdade é
  o contexto dono do dado, não a automação nem o n8n.
- `DestinoRecebimento`: como um arquivo que chegou vira registro (ex.: o comprovante da
  prestação), quem são os candidatos de um remetente e como descrever a referência.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

PLACEHOLDER_LINK = "{{link}}"


@dataclass(frozen=True)
class PedidoLink:
    """Um link pessoal que a mensagem leva. O worker cria o link só depois de TODAS as
    revalidações (lista de testadores, telefone, limite, modelo) e troca `{{link}}` no texto
    e nos parâmetros pela URL — uma mensagem recusada não deixa link vivo nem derruba o link
    que a pessoa já tem."""

    escopo: str
    recurso: str
    servidor_id: int
    valido_ate: datetime


@dataclass(frozen=True)
class Preparo:
    """Resposta de `TipoComunicacao.preparar`: vale? com que versão e texto?"""

    valida: bool
    motivo: str = ""                      # por que não vale mais (vira "obsoleta")
    versao: str = ""
    texto: str = ""                       # texto livre (dentro da janela; e o registro)
    parametros: tuple[str, ...] = ()      # do modelo aprovado (fora da janela)
    link: PedidoLink | None = None        # `{{link}}` no texto/parâmetros vira a URL


@dataclass(frozen=True)
class Assunto:
    """Como a tela mostra o assunto de uma comunicação ou de um recebimento."""

    rotulo: str
    url: str = ""


@dataclass(frozen=True)
class TipoComunicacao:
    chave: str                            # "viagens.diarias_liberadas"
    rotulo: str                           # "Diárias liberadas"
    fluxo: str                            # a chave de liga/desliga ("diarias_liberadas")
    preparar: Callable[[dict], Preparo]
    validade: timedelta = timedelta(days=3)
    aceita_resposta: str = ""             # destino de recebimento que a resposta alimenta
    janela_resposta: timedelta = timedelta(days=15)
    assunto: Callable[[str], Assunto | None] | None = None
    exige_optin: bool = True              # só a confirmação do "SAIR" dispensa (uma vez)


@dataclass(frozen=True)
class Candidato:
    recurso: str                          # "viagens.prestacaoservidor:42"
    rotulo: str                           # "Ofício 12/2026 — diárias de 10/10"
    unidade_id: int | None = None
    contexto: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PedidoDeAssociacao:
    usuario: object                       # quem age (a pessoa que originou a comunicação)
    recurso: str
    contexto: dict
    nome: str
    conteudo: bytes
    mime: str
    sha256: str


class ErroDeAssociacao(Exception):
    """O destino recusou (prestação finalizada, arquivo inválido…): vira exceção, com a
    mensagem para a pessoa."""


@dataclass(frozen=True)
class DestinoRecebimento:
    chave: str                            # "viagens.comprovante"
    rotulo: str                           # "Comprovante de saque"
    associar: Callable[[PedidoDeAssociacao], str]   # devolve a referência criada
    candidatos: Callable[[int], list[Candidato]]   # servidor_id -> onde poderia entrar
    descrever: Callable[[str], Assunto | None]     # referência -> rótulo e link
    confirmacao: Callable[[str], str] = lambda referencia: "Recebemos o seu arquivo."
    tipos_aceitos: tuple[str, ...] = ("application/pdf", "image/jpeg", "image/png")


_TIPOS: dict[str, TipoComunicacao] = {}
_DESTINOS: dict[str, DestinoRecebimento] = {}


def registrar_tipo(tipo: TipoComunicacao) -> None:
    _TIPOS[tipo.chave] = tipo


def registrar_destino(destino: DestinoRecebimento) -> None:
    _DESTINOS[destino.chave] = destino


def tipo(chave: str) -> TipoComunicacao | None:
    return _TIPOS.get(chave)


def destino(chave: str) -> DestinoRecebimento | None:
    return _DESTINOS.get(chave)


def tipos() -> list[TipoComunicacao]:
    return sorted(_TIPOS.values(), key=lambda t: t.rotulo)


def destinos() -> list[DestinoRecebimento]:
    return sorted(_DESTINOS.values(), key=lambda d: d.rotulo)


def fluxos() -> list[tuple[str, str]]:
    """(chave do fluxo, rótulo) de todos os tipos registrados, sem repetir."""
    vistos: dict[str, str] = {}
    for t in tipos():
        vistos.setdefault(t.fluxo, t.rotulo)
    return sorted(vistos.items(), key=lambda par: par[1])


def assunto(recurso: str, chave_tipo: str = "") -> Assunto | None:
    t = _TIPOS.get(chave_tipo)
    if t and t.assunto:
        try:
            return t.assunto(recurso)
        except Exception:
            return None
    return None
