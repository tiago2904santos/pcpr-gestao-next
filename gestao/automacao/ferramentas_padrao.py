"""Ferramentas da própria automação (registradas no `ready`)."""

from __future__ import annotations

from . import chaves, comunicacoes, ferramentas, policies
from .ferramentas import Campo, Ferramenta, FerramentaRecusada
from .models import Comunicacao


def _estado(usuario, entrada: dict) -> dict:
    return {"automacao_ligada": chaves.geral_ligada()}


def _com(entrada: dict) -> Comunicacao | None:
    return Comunicacao.objects.filter(pk=entrada["comunicacao"]).first()


def _pode_ver(usuario, entrada: dict) -> bool:
    c = _com(entrada)
    return c is not None and policies.pode_ver_objeto(usuario, c)


def _pode_operar(usuario, entrada: dict) -> bool:
    c = _com(entrada)
    return c is not None and policies.pode_operar_objeto(usuario, c)


def _situacao(usuario, entrada: dict) -> dict:
    c = _com(entrada)
    if c is None:
        raise FerramentaRecusada("Comunicação inexistente.")
    return {"id": c.pk, "situacao": c.situacao, "entrega": c.entrega, "tipo": c.tipo}


def _cancelar(usuario, entrada: dict) -> dict:
    try:
        c = comunicacoes.cancelar(usuario, entrada["comunicacao"],
                                  "Cancelada por pedido da automação, aprovado por uma pessoa.")
    except comunicacoes.ComunicacaoInvalida as erro:
        raise FerramentaRecusada(str(erro)) from erro
    return {"id": c.pk, "situacao": c.situacao}


def registrar() -> None:
    ferramentas.registrar(Ferramenta(
        nome="automacao.estado", risco=ferramentas.LEITURA, descricao="A automação está ligada?",
        entrada={}, executar=_estado, permitido=lambda u, e: policies.pode_ver(u)))
    ferramentas.registrar(Ferramenta(
        nome="comunicacoes.situacao", risco=ferramentas.LEITURA,
        descricao="Situação e entrega de uma comunicação.",
        entrada={"comunicacao": Campo("inteiro")}, executar=_situacao, permitido=_pode_ver,
        recurso=lambda e: f"automacao.comunicacao:{e['comunicacao']}"))
    ferramentas.registrar(Ferramenta(
        nome="comunicacoes.cancelar", risco=ferramentas.IRREVERSIVEL,
        descricao="Cancela uma comunicação que ainda não saiu (só com aprovação humana).",
        entrada={"comunicacao": Campo("inteiro")}, executar=_cancelar, permitido=_pode_operar,
        recurso=lambda e: f"automacao.comunicacao:{e['comunicacao']}",
        unidade=lambda e: getattr(_com(e), "unidade_id", None),
        resumo=lambda e: f"Cancelar a comunicação #{e['comunicacao']}"))
