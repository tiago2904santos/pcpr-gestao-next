"""Modelos de Ordem de Serviço (Python puro, sem Django).

Um modelo cadastrado tem um texto por **etapa** da viagem (ida, dias antes do evento, dias do
evento, dias depois, volta) e um texto por **função** da equipe. O documento sai no formato da
OS real: `DETERMINO` e itens I, II, III… — primeiro um por função que tenha alguém, depois um
por etapa presente. Que etapas existem, e em que dias, vem dos dois períodos da OS: o da
viagem (saída e chegada) e o do evento, que cabe dentro dele.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, time, timedelta

from .escrita import MESES, lista_com_e
from .ordem_servico import (
    DadosOS,
    equipe_no_texto,
    motivo_no_texto,
    municipios_no_texto,
    periodo_por_extenso,
)

ETAPAS = ("ida", "ida_e_antes", "antes", "evento", "depois", "depois_e_volta", "volta")
COMBINADAS = frozenset({"ida_e_antes", "depois_e_volta"})

# O que cada texto pode usar. `{servidores}` nas etapas é "Ana Lima e Bruno Rocha" (sem cargo);
# nas funções, só quem tem a função. `{equipe_sujeito}` é a equipe como sujeito ("os agentes de
# polícia judiciária A e B"); `{data_do}` é "do dia 15 de outubro de 2026" e `{data_durante}`,
# "durante todo o dia 15 de outubro de 2026" (vários dias: "dos dias…", "durante os dias…").
# Um texto de etapa com uma linha em branco no meio sai em itens separados.
MARCADORES_ETAPA = frozenset({"equipe", "equipe_sujeito", "servidores", "destino", "municipio",
                              "data", "data_do", "data_durante", "motivo", "hora", "sede"})
MARCADORES_FUNCAO = frozenset({"equipe", "servidores", "destino", "municipio", "motivo",
                               "sede"})

# Textos exatos das pendências (a conferência da tela os mostra como "Falta …").
FALTA_PERIODO = "período"
FALTA_FUNCAO = "função da equipe"
FALTA_HORA = "horário do briefing"

_MARCADOR = re.compile(r"\{([a-z_]+)\}")
# Concordância: "{conduza|conduzam}" vira a forma do singular com uma pessoa no item e a do
# plural com mais de uma (a função: quem a tem; a etapa: a equipe toda).
_CONCORDANCIA = re.compile(r"\{([^{}|]*)\|([^{}|]*)\}")
_UM_DIA = timedelta(days=1)


@dataclass(frozen=True)
class Funcao:
    codigo: str
    nome: str
    texto: str
    icone: str = ""


@dataclass(frozen=True)
class Modelo:
    nome: str
    referencia: str
    textos: Mapping[str, str]  # etapa -> texto (as sete de ETAPAS; vazio = etapa sem item)
    funcoes: tuple[Funcao, ...] = ()
    justificativas: tuple[str, ...] = ()
    finalidade: str = ""

    @property
    def usa_hora(self) -> bool:
        return any("hora" in marcadores(t) for t in self.textos.values())

    @property
    def combinados(self) -> frozenset[str]:
        """As etapas combinadas (véspera + ida, volta + dia seguinte) que têm texto."""
        return frozenset(e for e in COMBINADAS if (self.textos.get(e) or "").strip())


@dataclass(frozen=True)
class Etapa:
    nome: str
    inicio: date
    fim: date


@dataclass(frozen=True)
class TextosModelo:
    referencia: str
    itens: list[str]
    justificativas: list[str]
    finalidade: str


def distribuir_etapas(saida: date, chegada: date, evento_inicio: date | None = None,
                      evento_fim: date | None = None, *,
                      combinados: frozenset[str] = frozenset()) -> list[Etapa]:
    """Em que dias cai cada etapa. Viagem 3–8 com evento 5–6: ida 3, antes 4, evento 5–6,
    depois 7, volta 8. Saída na véspera do evento vira `ida_e_antes` (se o modelo tem o
    texto; senão só `ida`); chegada no dia seguinte, `depois_e_volta`. A ida é sempre o
    primeiro item e a volta o último, separados — mesmo com a saída no 1.º dia do evento ou a
    chegada no último (pedido do usuário, 15/10/2026). Sem evento informado, o evento são os
    dias entre a ida e a volta (viagem de até dois dias: a viagem inteira). Evento fora da
    viagem é erro (a OS valida antes)."""
    if chegada < saida:
        raise ValueError("A chegada não pode ser antes da saída.")
    if evento_inicio is None and (chegada - saida) > _UM_DIA:
        evento_inicio, evento_fim = saida + _UM_DIA, chegada - _UM_DIA
    ev_ini = evento_inicio or saida
    ev_fim = evento_fim or (evento_inicio or chegada)
    if ev_fim < ev_ini or ev_ini < saida or ev_fim > chegada:
        raise ValueError("O período do evento precisa caber no período da viagem.")
    etapas: list[Etapa] = []
    if saida < ev_ini and ev_ini - saida == _UM_DIA and "ida_e_antes" in combinados:
        etapas.append(Etapa("ida_e_antes", saida, saida))
    else:
        etapas.append(Etapa("ida", saida, saida))
        if ev_ini - saida > _UM_DIA:
            etapas.append(Etapa("antes", saida + _UM_DIA, ev_ini - _UM_DIA))
    etapas.append(Etapa("evento", ev_ini, ev_fim))
    if chegada > ev_fim and chegada - ev_fim == _UM_DIA and "depois_e_volta" in combinados:
        etapas.append(Etapa("depois_e_volta", chegada, chegada))
    else:
        if chegada - ev_fim > _UM_DIA:
            etapas.append(Etapa("depois", ev_fim + _UM_DIA, chegada - _UM_DIA))
        etapas.append(Etapa("volta", chegada, chegada))
    return etapas


def marcadores(texto: str) -> set[str]:
    return set(_MARCADOR.findall(texto or ""))


def marcadores_invalidos(texto: str, permitidos: frozenset[str]) -> set[str]:
    return marcadores(texto) - permitidos


def data_da_etapa(etapa: Etapa) -> str:
    """"no dia 4 de maio de 2026", "nos dias 5 e 6 de maio de 2026", "nos dias 5 a 7 de maio
    de 2026" (meses diferentes: as duas datas por extenso)."""
    ini, fim = etapa.inicio, etapa.fim
    if fim - ini == _UM_DIA and (ini.month, ini.year) == (fim.month, fim.year):
        return f"nos dias {ini.day} e {fim.day} de {MESES[ini.month - 1]} de {ini.year}"
    return periodo_por_extenso(ini, fim)


def data_do(etapa: Etapa) -> str:
    """"do dia 15 de outubro de 2026", "dos dias 15 e 16 de outubro de 2026"."""
    texto = data_da_etapa(etapa)
    return "do" + texto[2:] if texto.startswith("no ") else "d" + texto[1:]


def data_durante(etapa: Etapa) -> str:
    """"durante todo o dia 15 de outubro de 2026", "durante os dias 15 e 16 de outubro…"."""
    texto = data_da_etapa(etapa)
    return ("durante todo o " + texto[3:] if texto.startswith("no ")
            else "durante os " + texto[4:])


def sujeito(equipe_texto: str) -> str:
    """A equipe como sujeito da frase: "dos agentes A e B" → "os agentes A e B"."""
    for de, para in (("dos ", "os "), ("do ", "o "), ("da ", "a ")):
        if equipe_texto.startswith(de):
            return para + equipe_texto[len(de):]
    return equipe_texto


def hora_no_texto(hora: time | None) -> str:
    return f"às {hora.hour:02d}h{hora.minute:02d}min" if hora else ""


def romano(n: int) -> str:
    valores = ((50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
    saida = ""
    for valor, letra in valores:
        while n >= valor:
            saida += letra
            n -= valor
    return saida


def concordar(texto: str, pessoas: int) -> str:
    """Escolhe "{singular|plural}" pelo número de pessoas do item (nenhuma conta como uma)."""
    return _CONCORDANCIA.sub(lambda m: m.group(1) if pessoas <= 1 else m.group(2), texto)


def _limpar(texto: str) -> str:
    """Marcador vazio não deixa espaço duplo nem " ." para trás."""
    return " ".join(texto.split()).replace(" .", ".").replace(" ,", ",")


def _valores(dados: DadosOS) -> dict[str, str]:
    return {
        "equipe": equipe_no_texto(dados.equipe),
        "equipe_sujeito": sujeito(equipe_no_texto(dados.equipe)),
        "servidores": lista_com_e([p.nome for p in dados.equipe]),
        "destino": lista_com_e(dados.destinos) or "destino informado",
        "municipio": municipios_no_texto(dados.destinos),
        "motivo": motivo_no_texto(dados.motivo) or "atuação na atividade institucional designada",
        "hora": hora_no_texto(dados.hora),
        "sede": dados.sede or "sede de lotação",
    }


def itens_da_os(dados: DadosOS, modelo: Modelo) -> TextosModelo:
    """Os itens do DETERMINO: um por função com alguém, depois um por etapa presente."""
    valores = _valores(dados)
    itens: list[str] = []
    for funcao in modelo.funcoes:
        quem = [p for p in dados.equipe if dados.funcoes.get(p.id) == funcao.codigo]
        if quem and funcao.texto.strip():
            # {equipe} e {servidores} na função são só quem a tem.
            itens.append(_limpar(concordar(funcao.texto, len(quem)).format_map(
                {**valores, "equipe": equipe_no_texto(quem),
                 "servidores": lista_com_e([p.nome for p in quem])})))
    if dados.inicio:
        etapas = distribuir_etapas(dados.inicio, dados.fim or dados.inicio,
                                   dados.evento_inicio, dados.evento_fim,
                                   combinados=modelo.combinados)
        for etapa in etapas:
            texto = (modelo.textos.get(etapa.nome) or "").strip()
            datas = {"data": data_da_etapa(etapa), "data_do": data_do(etapa),
                     "data_durante": data_durante(etapa)}
            # Linha em branco no texto da etapa: itens separados (briefing e permanência).
            for parte in re.split(r"\n\s*\n", texto):
                if parte.strip():
                    itens.append(_limpar(concordar(parte, len(dados.equipe)).format_map(
                        {**valores, **datas})))
    return TextosModelo(referencia=modelo.referencia, itens=itens,
                        justificativas=[j for j in modelo.justificativas if j.strip()],
                        finalidade=modelo.finalidade.strip())


def faltam_para_o_modelo(dados: DadosOS, modelo: Modelo) -> list[str]:
    """O que o modelo pede e a OS ainda não tem (a OS sinaliza; não bloqueia)."""
    falta: list[str] = []
    if not dados.inicio:
        falta.append(FALTA_PERIODO)
    if modelo.funcoes and dados.equipe and not any(
            dados.funcoes.get(p.id) for p in dados.equipe):
        falta.append(FALTA_FUNCAO)
    if modelo.usa_hora and dados.hora is None:
        falta.append(FALTA_HORA)
    return falta

