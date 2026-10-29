"""Roda o gabarito do AUT-91 e devolve os resultados caso a caso (sem rede, sem custo)."""

from __future__ import annotations

from dataclasses import dataclass

from .. import assistente
from ..dominio import leitura
from ..dominio.validacao import codigo, validar_texto
from . import casos


@dataclass(frozen=True)
class Resultado:
    grupo: str
    nome: str
    passou: bool
    detalhe: str = ""


def validador() -> list[Resultado]:
    saida = []
    for c in casos.VALIDADOR:
        erros = {codigo(e) for e in validar_texto(c.texto, fatos=c.fatos,
                                                    nomes_proibidos=casos.NOMES,
                                                    catalogo=casos.CATALOGO)}
        passou = (not erros) if not c.esperado else set(c.esperado) <= erros
        saida.append(Resultado("validador", c.nome, passou, ", ".join(sorted(erros)) or "ok"))
    return saida


def leitura_por_regra() -> list[Resultado]:
    saida = []
    for c in casos.LEITURA:
        datas = tuple(a.valor for a in leitura.datas(c.texto, 2026))
        horas = tuple(a.valor for a in leitura.horas(c.texto))
        passou = datas == c.datas and horas == c.horas
        saida.append(Resultado("leitura", c.nome, passou, f"datas={datas} horas={horas}"))
    return saida


def assistente_deterministico() -> list[Resultado]:
    saida = []
    for c in casos.ASSISTENTE:
        r = assistente.responder(c.pergunta, None, publico=c.publico)
        artigos = [f.referencia for f in r.fontes if f.tipo == "artigo"]
        passou = bool(r.categoria == c.categoria
                      and (not c.artigo or (artigos and artigos[0] == c.artigo))
                      and set(c.lacunas) <= set(r.lacunas))
        saida.append(Resultado("assistente", c.nome, passou,
                               f"{r.categoria} {artigos[:1]} {r.lacunas}"))
    return saida


def tudo() -> list[Resultado]:
    return validador() + leitura_por_regra() + assistente_deterministico()
