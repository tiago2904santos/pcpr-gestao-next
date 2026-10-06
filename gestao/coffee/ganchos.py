"""Origem do pedido de coffee break (CB7b; paridade com `coffee_break/origem.py`): o "Pedir
coffee break" da solicitação de evento (Eventos Sociais) e da palestra (Palestras) abre a
nova OS já preenchida e as duas ficam ligadas — a OS mostra de onde veio e avisa quando o
evento foi remarcado.

O Coffee Break não conhece os outros contextos (import-linter): cada um registra aqui a sua
`Origem` no `ready` do app. `obter` devolve os dados só se quem pede enxerga a origem (a
permissão de ver do módulo dela); `data_de` lê só a data, para o aviso de remarcação.

`DadosDaOrigem.iniciais` usa os nomes do formulário da OS: municipio ("Cidade/UF"),
data_evento, horario, descricao, local_entrega, endereco, bairro, cep, responsavel,
quantidade."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from django.urls import reverse

from . import policies

LIMITES = {"descricao": 2000, "local_entrega": 255, "endereco": 255, "bairro": 120, "cep": 9,
           "responsavel": 200}


@dataclass(frozen=True)
class DadosDaOrigem:
    rotulo: str  # "Solicitação de evento #12"
    url: str
    iniciais: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Origem:
    chave: str  # "evento" | "palestra"
    nome: str  # "Solicitação de evento" — o rótulo para quem não enxerga a origem
    obter: Callable[[object, int], DadosDaOrigem | None]
    data_de: Callable[[int], date | None]


_ORIGENS: dict[str, Origem] = {}


def registrar_origem(origem: Origem) -> None:
    _ORIGENS[origem.chave] = origem


def juntar(*partes: object, separador: str = " – ") -> str:
    return separador.join(str(p).strip() for p in partes if p and str(p).strip())


def _limpar(iniciais: dict) -> dict:
    saida = {}
    for chave, valor in iniciais.items():
        if valor in ("", None):
            continue
        if isinstance(valor, str):
            valor = " ".join(valor.split())[:LIMITES.get(chave, 255)]
        saida[chave] = valor
    return saida


def resolver(usuario, texto: str | None) -> tuple[Origem, int, DadosDaOrigem] | None:
    """`"evento:12"` → a origem, o id e os dados, se existe e quem pede a enxerga."""
    chave, _, pk = (texto or "").strip().partition(":")
    origem = _ORIGENS.get(chave)
    if origem is None or not pk.isdecimal() or len(pk) > 9:
        return None
    dados = origem.obter(usuario, int(pk))
    if dados is None:
        return None
    return origem, int(pk), DadosDaOrigem(dados.rotulo, dados.url, _limpar(dados.iniciais))


def url_para_pedir(usuario, chave: str, pk: int) -> str:
    """O link do "Pedir coffee break" (vazio para quem não tem o módulo)."""
    if chave not in _ORIGENS or not policies.pode_acessar(usuario):
        return ""
    return f"{reverse('coffee:nova')}?origem={chave}:{pk}"


@dataclass(frozen=True)
class Cartao:
    rotulo: str
    url: str  # vazio quando quem vê não enxerga a origem
    aviso: str


def cartao(usuario, s) -> Cartao | None:
    """O que a folha mostra da origem: rótulo, link e o aviso de remarcação (a data da
    origem mudou depois do pedido)."""
    origem = _ORIGENS.get(s.origem_tipo or "")
    if origem is None or s.origem_id is None:
        return None
    dados = origem.obter(usuario, s.origem_id)
    data = origem.data_de(s.origem_id)
    aviso = ""
    if data and s.data_evento and data != s.data_evento and not s.cancelada:
        aviso = (f"O evento foi remarcado para {data:%d/%m/%Y}, e a OS está com "
                 f"{s.data_evento:%d/%m/%Y}. Confira a data e avise o fornecedor.")
    if dados is None:
        return Cartao(f"{origem.nome} #{s.origem_id}", "", aviso)
    return Cartao(dados.rotulo, dados.url, aviso)
