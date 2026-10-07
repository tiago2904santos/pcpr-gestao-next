"""Natureza do pedido (Autorização × Convalidação) e assunto do documento.

Regra levantada na referência (viagens_oficios/assunto_oficio.py):
- **Autorização** quando a data do ofício é ANTERIOR à data (local) da primeira
  saída; caso contrário (mesmo dia ou depois) é **Convalidação**. Sem saída
  conhecida, assume-se Autorização.
- Marcadores opcionais, mutuamente exclusivos:
  - **Retificado**: só vale se a natureza for Autorização (ignorado na Convalidação);
  - **Complementar**: vale sempre.
  Eles mudam apenas o rótulo entre parênteses; a frase do ofício continua
  "solicito autorização…" ou "solicito convalidação…".
- O assunto nunca é texto livre (evita textos de teste/demonstração no documento).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Marcador(StrEnum):
    NENHUM = ""
    RETIFICADO = "retificado"
    COMPLEMENTAR = "complementar"


@dataclass(frozen=True)
class Assunto:
    autorizacao: bool
    rotulo: str   # "(Autorização)", "(Convalidação)", "(Retificado)", "(Complementar)"
    termo: str    # "autorização" | "convalidação" — usado na frase do ofício
    linha: str    # "Solicitação de autorização e concessão de diárias."


def resolver_assunto(data_oficio: date, primeira_saida: date | None,
                     marcador: Marcador | str = Marcador.NENHUM) -> Assunto:
    autorizacao = primeira_saida is None or data_oficio < primeira_saida
    termo = "autorização" if autorizacao else "convalidação"
    linha = f"Solicitação de {termo} e concessão de diárias."
    marcador = Marcador(marcador or "")
    if marcador is Marcador.COMPLEMENTAR:
        rotulo = "(Complementar)"
    elif marcador is Marcador.RETIFICADO and autorizacao:
        rotulo = "(Retificado)"
    else:
        rotulo = "(Autorização)" if autorizacao else "(Convalidação)"
    return Assunto(autorizacao, rotulo, termo, linha)


# ---------------------------------------------------------------- tipo (listas e resumo)
_MARCAS = {Marcador.RETIFICADO: "Retificado", Marcador.COMPLEMENTAR: "Complementar"}
_POR_QUE_MARCA = {
    Marcador.RETIFICADO: "Marcado como retificado: corrige um ofício anterior à viagem.",
    Marcador.COMPLEMENTAR: "Marcado como complementar: acrescenta ao ofício já enviado.",
}


@dataclass(frozen=True)
class TipoOficio:
    """O tipo do pedido como as listas e o resumo o mostram.

    `completo` sempre ("Autorização", "Convalidação · Complementar"); `selo` só quando foge
    do comum — Convalidação, Retificado ou Complementar — porque Autorização é o caso de
    quase todo ofício e um selo em toda linha seria ruído (decisão D4). `porque` explica
    em uma ou duas frases (o legado usava uma dica de passar o mouse, inacessível no toque).
    """

    autorizacao: bool
    marca: str    # "" | "Retificado" | "Complementar" (só a marca que vale)
    porque: str

    @property
    def natureza(self) -> str:
        return "Autorização" if self.autorizacao else "Convalidação"

    @property
    def completo(self) -> str:
        return f"{self.natureza} · {self.marca}" if self.marca else self.natureza

    @property
    def selo(self) -> str:
        if self.autorizacao:
            return self.marca
        return self.completo

    @property
    def incomum(self) -> bool:
        return bool(self.selo)


def tipo_do_oficio(data_oficio: date, primeira_saida: date | None,
                   marcador: Marcador | str = Marcador.NENHUM) -> TipoOficio:
    assunto = resolver_assunto(data_oficio, primeira_saida, marcador)
    marcador = Marcador(marcador or "")
    vale = marcador is Marcador.COMPLEMENTAR or (
        marcador is Marcador.RETIFICADO and assunto.autorizacao)
    if primeira_saida is None:
        porque = "Sem data de saída ainda: o pedido é de autorização."
    else:
        oficio, saida = f"{data_oficio:%d/%m/%Y}", f"{primeira_saida:%d/%m/%Y}"
        dias = (primeira_saida - data_oficio).days
        if dias > 0:
            porque = (f"A viagem começa em {saida}, {dias} dia{'s' if dias != 1 else ''} "
                      f"depois do ofício ({oficio}): pedido de autorização.")
        elif dias == 0:
            porque = (f"A viagem começa no mesmo dia do ofício ({oficio}): "
                      "pedido de convalidação.")
        else:
            porque = (f"A viagem começou em {saida}, antes do ofício ({oficio}): "
                      "pedido de convalidação.")
    if vale:
        porque += " " + _POR_QUE_MARCA[marcador]
    elif marcador is Marcador.RETIFICADO:
        porque += " A marca de retificado não vale na convalidação."
    return TipoOficio(assunto.autorizacao, _MARCAS[marcador] if vale else "", porque)


# ---------------------------------------------------------------- marcas no menu (LP-30, D7)
def alternar_marcador(atual: Marcador | str, marca: Marcador | str) -> Marcador:
    """O mesmo item do menu liga e desliga a marca. As marcas são mutuamente exclusivas
    (referência: retificar tira a de complementar e vice-versa): ligar uma tira a outra."""
    marca = Marcador(marca or "")
    if marca is Marcador.NENHUM:
        raise ValueError("Diga qual marca ligar ou desligar (retificado ou complementar).")
    return Marcador.NENHUM if Marcador(atual or "") is marca else marca


@dataclass(frozen=True)
class OpcaoDeMarca:
    """Um item de marca no menu: liga (`ligar`) ou desliga `marca`; `tira` é a marca que
    sai junto quando esta entra (a tela avisa — ninguém perde a outra sem saber)."""

    marca: Marcador
    ligar: bool
    tira: Marcador


def marcas_do_menu(atual: Marcador | str, *, autorizacao: bool) -> list[OpcaoDeMarca]:
    """O que o menu oferece, nesta ordem: Retificado, Complementar. "Retificado" só muda o
    rótulo de uma Autorização (`resolver_assunto`): numa Convalidação não se oferece ligá-la
    — desligar continua possível, para limpar o dado."""
    atual = Marcador(atual or "")
    opcoes = []
    for marca in (Marcador.RETIFICADO, Marcador.COMPLEMENTAR):
        ligada = atual is marca
        if marca is Marcador.RETIFICADO and not autorizacao and not ligada:
            continue
        tira = atual if not ligada and atual is not Marcador.NENHUM else Marcador.NENHUM
        opcoes.append(OpcaoDeMarca(marca, not ligada, tira))
    return opcoes
