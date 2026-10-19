"""Ganchos que os contextos de negócio registram (a assistência não importa nenhum deles —
import-linter). O app descobre `<app>/ia_usos.py` de cada app instalado no `ready()`
(`autodiscover_modules`), e cada um chama `registrar_uso`.

Um `UsoIA` diz, em código e revisável:
- o que entra (`campos_permitidos`, conferido a cada pedido) e o que nunca entra
  (`dados_excluidos`, declarado e testado);
- as instruções fixas e versionadas (`versao_prompt`) e o esquema da saída;
- `montar(usuario, recurso_id, opcoes)`: lê o registro com a política de quem pede e devolve
  os fatos — é o único caminho de dado para o modelo;
- `deterministico(ctx)`: a alternativa sem IA (regra/modelo de texto), sempre disponível;
- `validar(dados, ctx)`: os fatos da saída batem com os do sistema? (lista de códigos);
- `aplicar(...)`: grava pelo serviço do contexto, com trava, revalidação e sem sobrescrever
  texto escrito por pessoa (ausente = a sugestão só se lê, não se grava).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class RecursoInexistente(Exception):
    """Fora do escopo de quem pede ou não existe: a tela responde 404 (não confirma)."""


class Obsoleta(Exception):
    """Os dados mudaram desde a sugestão: não se aplica (a pessoa pede outra)."""


class TextoHumano(Exception):
    """O campo já tem texto escrito por uma pessoa: só com confirmação explícita."""


class AplicacaoRecusada(Exception):
    """O serviço do contexto recusou (registro emitido, sem permissão…): mensagem à pessoa."""


@dataclass(frozen=True)
class Fato:
    chave: str                 # "destinos" (o que o modelo cita em `fontes`)
    rotulo: str                # "Destinos do ofício" (o campo do sistema)
    valor: str
    livre: bool = False        # veio de texto livre (mascarado): a tela marca "confira"
    do_pedido: bool = False    # escrito por quem pediu (não é dado do registro)


@dataclass(frozen=True)
class Contexto:
    recurso_rotulo: str
    fatos: tuple[Fato, ...]
    textos_atuais: dict[str, str] = field(default_factory=dict)
    lacunas: tuple[str, ...] = ()
    extras: dict[str, Any] = field(default_factory=dict)   # para os validadores; não vai ao modelo
    contem_documento: bool = False

    @property
    def versao(self) -> str:
        """A versão da fonte: os fatos do registro e o texto atual dos campos-alvo. Mudou
        qualquer um, a sugestão fica obsoleta. O que quem pediu escreveu não entra."""
        corpo = json.dumps({"f": [[f.chave, f.valor] for f in self.fatos if not f.do_pedido],
                            "t": sorted(self.textos_atuais.items())},
                           ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(corpo.encode()).hexdigest()

    def fato(self, chave: str) -> Fato | None:
        return next((f for f in self.fatos if f.chave == chave), None)

    def valor(self, chave: str) -> str:
        f = self.fato(chave)
        return f.valor if f else ""

    def rotulos(self, chaves) -> list[str]:
        mapa = {f.chave: f.rotulo for f in self.fatos}
        return [mapa[c] for c in dict.fromkeys(chaves) if c in mapa]


@dataclass(frozen=True)
class Item:
    """Uma peça da sugestão como a tela mostra (um campo de texto, um trecho lido…)."""

    campo: str
    rotulo: str
    valor: str
    fontes: tuple[str, ...] = ()
    aplicavel: bool = True
    nota: str = ""               # "Município conferido no cadastro", "não encontrado"…


@dataclass(frozen=True)
class OpcaoPedido:
    """Um campo livre opcional do formulário de pedido (vai mascarado, como DADO)."""

    nome: str
    rotulo: str
    ajuda: str = ""
    max_caracteres: int = 600
    obrigatorio: bool = False


@dataclass(frozen=True)
class Assunto:
    rotulo: str
    url: str = ""


@dataclass(frozen=True)
class UsoIA:
    chave: str
    codigo: str                                  # "AUT-50"
    rotulo: str
    descricao: str
    versao_prompt: str
    instrucoes: str
    esquema: dict[str, Any]
    campos_permitidos: tuple[str, ...]
    dados_excluidos: tuple[str, ...]
    lacunas_conhecidas: dict[str, str]           # código → pergunta fixa para a pessoa
    montar: Callable[[Any, str, dict], Contexto]
    deterministico: Callable[[Contexto], dict[str, Any]]
    validar: Callable[[dict[str, Any], Contexto], list[str]]
    itens: Callable[[dict[str, Any], Contexto], list[Item]]
    pode_pedir: Callable[[Any, str], bool]
    pode_ver: Callable[[Any, str], bool]
    descrever: Callable[[str], Assunto | None]
    aplicar: Callable[[Any, str, dict[str, str], str, bool], None] | None = None
    versao_atual: Callable[[str], str | None] | None = None
    envolve_documento: bool = False              # ADR 0041: provedor real recusa
    opcoes: tuple[OpcaoPedido, ...] = ()
    acao: str = "Pedir rascunho"
    exemplo_demo: Callable[[], tuple[Any, str, dict] | None] | None = None


# ------------------------------------------------------------------ "minha situação"
@dataclass(frozen=True)
class PendenciaDoServidor:
    codigo: str                # estável: "PREST_SEM_COMPROVANTE"
    texto: str                 # escrito para o servidor (não para o operador)
    quem_resolve: str          # "você" | "a equipe"


@dataclass(frozen=True)
class PrestacaoDoServidor:
    chave: str                 # opaca ("ps:12"), nunca o CPF
    oficio: str                # "12/2026"
    destinos: str
    periodo: str
    liberacao: Any = None      # date | None
    prazo_saque: Any = None
    prazo_prestar: Any = None
    situacao: str = ""
    finalizada: bool = False
    pendencias: tuple[PendenciaDoServidor, ...] = ()


@dataclass(frozen=True)
class ViagemDoServidor:
    oficio: str
    destinos: str
    saida: Any = None          # datetime | None
    retorno: Any = None
    situacao: str = ""


@dataclass(frozen=True)
class SituacaoDoServidor:
    servidor_id: int
    gerada_em: Any             # datetime
    viagens: tuple[ViagemDoServidor, ...] = ()
    prestacoes: tuple[PrestacaoDoServidor, ...] = ()
    fontes: tuple[str, ...] = ()


_USOS: dict[str, UsoIA] = {}
_FONTES_SITUACAO: list[Callable[[int], Any]] = []


def registrar_uso(uso: UsoIA) -> None:
    """Recusa, já no `ready()`, um uso sem minimização declarada ou com saída aberta."""
    if not uso.campos_permitidos or not uso.dados_excluidos:
        raise ValueError(f"Uso {uso.chave}: declare os campos permitidos e os excluídos.")
    if uso.esquema.get("additionalProperties") is not False:
        raise ValueError(f"Uso {uso.chave}: a saída precisa de additionalProperties: false.")
    _USOS[uso.chave] = uso


def uso(chave: str) -> UsoIA | None:
    return _USOS.get(chave)


def usos() -> list[UsoIA]:
    return sorted(_USOS.values(), key=lambda u: (u.codigo, u.rotulo))


def registrar_fonte_situacao(fonte: Callable[[int], Any]) -> None:
    """A "minha situação" do servidor vem do contexto dono do dado (Viagens)."""
    if fonte not in _FONTES_SITUACAO:
        _FONTES_SITUACAO.append(fonte)


def fontes_situacao() -> list[Callable[[int], Any]]:
    return list(_FONTES_SITUACAO)
