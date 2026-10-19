"""Registro de ferramentas tipadas (ADR 0020): o único jeito de a automação (n8n, IA, cliente
MCP) ler ou mudar algo no PCPR.

Cada ferramenta declara nome, versão, risco, entrada tipada e a policy (que chama a policy do
contexto dono). `executar` confere a entrada, o risco, as chaves e a policy do usuário
EFETIVO (o dono do token pessoal ou quem emitiu a delegação), registra a execução e:
- `leitura`: executa (mesmo com a automação desligada);
- `preparacao`: executa só com a automação ligada; no modo sombra só registra;
- `irreversivel`: nunca executa direto — vira `PedidoAprovacao` que uma pessoa aprova na tela.

O que a automação NÃO pode, por desenho: escolher equipe, motorista ou viatura; inventar km,
pagamento, atividade ou valor; calcular diária por linguagem natural; emitir, cancelar,
assinar, aprovar prestação ou decidir despacho. Essas ferramentas simplesmente não existem.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from . import chaves, policies
from .models_api import ExecucaoFerramenta, PedidoAprovacao

LEITURA, PREPARACAO, IRREVERSIVEL = "leitura", "preparacao", "irreversivel"
RISCOS = (LEITURA, PREPARACAO, IRREVERSIVEL)
FLUXO = "ferramentas"
TIPOS = {"inteiro": int, "texto": str, "booleano": bool, "lista": list}
PROIBIDAS = ("equipe", "motorista", "viatura", "km", "pagamento", "diaria", "emitir",
             "assinar", "aprovar", "despacho", "finalizar")


class FerramentaInvalida(Exception):
    """Entrada fora do esquema ou ferramenta desconhecida (422)."""


class FerramentaRecusada(Exception):
    """Recurso terminal ou obsoleto (409)."""


class AutomacaoDesligada(Exception):
    """423: nada foi feito."""


@dataclass(frozen=True)
class Campo:
    tipo: str
    obrigatorio: bool = True
    maximo: int = 200


@dataclass(frozen=True)
class Ferramenta:
    nome: str                                   # "prestacao.situacao"
    descricao: str
    risco: str
    entrada: dict[str, Campo]
    executar: Callable[[object, dict], dict]    # (usuario, entrada) -> saída
    permitido: Callable[[object, dict], bool]   # policy do contexto para o usuário efetivo
    recurso: Callable[[dict], str] = lambda e: ""
    unidade: Callable[[dict], int | None] = lambda e: None
    resumo: Callable[[dict], str] = lambda e: ""
    versao: int = 1
    saida: dict[str, str] = field(default_factory=dict)

    def descrever(self) -> dict:
        return {"nome": self.nome, "versao": self.versao, "descricao": self.descricao,
                "risco": self.risco,
                "entrada": {k: {"tipo": c.tipo, "obrigatorio": c.obrigatorio}
                            for k, c in self.entrada.items()},
                "saida": self.saida}


_REGISTRO: dict[str, Ferramenta] = {}


def registrar(f: Ferramenta) -> None:
    if f.risco not in RISCOS:
        raise ValueError(f"Risco inválido: {f.risco}")
    nome = f.nome.lower()
    if f.risco != LEITURA and any(p in nome for p in PROIBIDAS):
        raise ValueError(f"Ferramenta proibida por desenho (ADR 0020): {f.nome}")
    _REGISTRO[f.nome] = f


def obter(nome: str) -> Ferramenta | None:
    return _REGISTRO.get(nome)


def todas() -> list[Ferramenta]:
    return sorted(_REGISTRO.values(), key=lambda f: f.nome)


def validar(f: Ferramenta, entrada: object) -> dict:
    if not isinstance(entrada, dict):
        raise FerramentaInvalida("A entrada é um objeto JSON.")
    extras = set(entrada) - set(f.entrada)
    if extras:
        raise FerramentaInvalida(f"Campos não aceitos: {', '.join(sorted(extras))}.")
    saida = {}
    for nome, campo in f.entrada.items():
        if nome not in entrada:
            if campo.obrigatorio:
                raise FerramentaInvalida(f"Falta o campo {nome}.")
            continue
        valor = entrada[nome]
        tipo = TIPOS[campo.tipo]
        if (isinstance(valor, bool) and tipo is int) or not isinstance(valor, tipo):
            raise FerramentaInvalida(f"{nome} deve ser {campo.tipo}.")
        if isinstance(valor, str) and len(valor) > campo.maximo:
            raise FerramentaInvalida(f"{nome} passa de {campo.maximo} caracteres.")
        saida[nome] = valor
    return saida


def _registrar(f: Ferramenta, *, usuario, credencial, delegacao, origem, entrada, resultado,
               detalhe="", inicio=None, correlacao="") -> ExecucaoFerramenta:
    return ExecucaoFerramenta.objects.create(
        ferramenta=f.nome, versao=f.versao, risco=f.risco, usuario=usuario,
        credencial=credencial, delegacao=delegacao, origem=origem,
        entrada={k: v for k, v in entrada.items() if not isinstance(v, str) or len(v) <= 80},
        resultado=resultado, detalhe=detalhe[:255], correlacao=correlacao[:120],
        duracao_ms=int((time.monotonic() - inicio) * 1000) if inicio else None)


@dataclass(frozen=True)
class Resultado:
    execucao: ExecucaoFerramenta
    saida: dict | None = None
    aprovacao: PedidoAprovacao | None = None


def executar(nome: str, entrada: object, *, usuario, credencial=None, delegacao=None,
             origem: str = "api", correlacao: str = "") -> Resultado:
    """Negações e erros são gravados numa transação própria, depois de desfeita a da
    execução — um token roubado sondando ids deixa rastro."""
    f = obter(nome)
    if f is None:
        raise FerramentaInvalida("Ferramenta desconhecida.")
    inicio = time.monotonic()
    dados = validar(f, entrada)
    comum = {"usuario": usuario, "credencial": credencial, "delegacao": delegacao,
             "origem": origem, "entrada": dados, "inicio": inicio, "correlacao": correlacao}
    if not (getattr(usuario, "is_active", False) and f.permitido(usuario, dados)):
        with transaction.atomic():
            _registrar(f, resultado=ExecucaoFerramenta.Resultado.NEGADA,
                       detalhe="Policy negada para o usuário efetivo.", **comum)
        raise PermissionDenied("Policy negada para quem a automação representa.")
    if f.risco != LEITURA:
        permissao = chaves.permissao_de_efeito(None, FLUXO)
        if not permissao.permitido:
            raise AutomacaoDesligada(permissao.motivo)
        if permissao.modo == "sombra":
            with transaction.atomic():
                e = _registrar(f, resultado=ExecucaoFerramenta.Resultado.SOMBRA,
                               detalhe="Modo sombra: registrada, não executada.", **comum)
            return Resultado(e)
        if f.risco == IRREVERSIVEL or permissao.modo == "assistido":
            with transaction.atomic():
                e = _registrar(f, resultado=ExecucaoFerramenta.Resultado.PENDENTE,
                               detalhe="Aguardando aprovação humana.", **comum)
                pedido = PedidoAprovacao.objects.create(
                    ferramenta=f.nome, entrada=dados,
                    resumo=(f.resumo(dados) or f.descricao)[:255],
                    recurso=f.recurso(dados)[:80], unidade_id=f.unidade(dados),
                    pedido_por=usuario, execucao=e,
                    expira_em=timezone.now() + timedelta(days=2))
            return Resultado(e, aprovacao=pedido)
    try:
        with transaction.atomic():
            saida = f.executar(usuario, dados)
            e = _registrar(f, resultado=ExecucaoFerramenta.Resultado.OK, **comum)
    except (FerramentaRecusada, FerramentaInvalida, PermissionDenied) as erro:
        with transaction.atomic():
            _registrar(f, resultado=ExecucaoFerramenta.Resultado.ERRO, detalhe=str(erro),
                       **comum)
        raise
    return Resultado(e, saida=saida)


# ------------------------------------------------------------------ aprovação humana
def _pedido(usuario, pk: int) -> PedidoAprovacao:
    p = PedidoAprovacao.objects.select_for_update(of=("self",)).select_related(
        "execucao").get(pk=pk)
    policies.exigir(policies.pode_operar_objeto(usuario, p),
                    "Você não pode decidir este pedido.")
    if p.situacao != PedidoAprovacao.Situacao.PENDENTE:
        raise FerramentaRecusada("Este pedido já foi decidido.")
    if p.expira_em <= timezone.now():
        raise PedidoVencido("O pedido expirou: peça de novo.")
    return p


class PedidoVencido(FerramentaRecusada):
    """Venceu antes da decisão: quem chama grava EXPIRADO fora da transação desfeita."""


def _marcar_vencido(pk: int) -> None:
    PedidoAprovacao.objects.filter(pk=pk, situacao=PedidoAprovacao.Situacao.PENDENTE).update(
        situacao=PedidoAprovacao.Situacao.EXPIRADO)


def _decidir(funcao, usuario, pk: int, *args):
    """A decisão roda numa transação; se o pedido tinha vencido, a marca EXPIRADO é gravada
    DEPOIS do rollback (senão ele ficaria pendente para sempre, falhando a cada clique)."""
    try:
        with transaction.atomic():
            return funcao(usuario, pk, *args)
    except PedidoVencido:
        _marcar_vencido(pk)
        raise


def conferir_portao(f: Ferramenta) -> None:
    """Chave geral e fluxo das ferramentas, ANTES de qualquer efeito colateral (consumir a
    delegação, inclusive): desligado é 423 sem gastar nada."""
    if f.risco != LEITURA:
        permissao = chaves.permissao_de_efeito(None, FLUXO)
        if not permissao.permitido:
            raise AutomacaoDesligada(permissao.motivo)


def aprovar(usuario, pk: int) -> PedidoAprovacao:
    return _decidir(_aprovar, usuario, pk)


def recusar(usuario, pk: int, motivo: str) -> PedidoAprovacao:
    return _decidir(_recusar, usuario, pk, motivo)


def _aprovar(usuario, pk: int) -> PedidoAprovacao:
    """Quem aprova executa com a PRÓPRIA permissão (não a de quem pediu)."""
    p = _pedido(usuario, pk)
    if p.pedido_por_id == usuario.pk:
        raise PermissionDenied("Quem pediu a ação não pode aprovar o próprio pedido.")
    permissao = chaves.permissao_de_efeito(None, FLUXO)
    if not permissao.permitido:
        raise FerramentaRecusada(f"Nada se aprova agora: {permissao.motivo}")
    if permissao.modo == "sombra":  # sombra registra, nunca executa — nem o que já estava na fila
        raise FerramentaRecusada("O fluxo das ferramentas está em modo sombra: nada é "
                                 "executado. Volte para assistido para aprovar.")
    f = obter(p.ferramenta)
    agora = timezone.now()
    p.decidido_por, p.decidido_em = usuario, agora
    if f is None or not f.permitido(usuario, p.entrada):
        raise PermissionDenied("Você não tem permissão para esta ação.")
    try:
        with transaction.atomic():
            f.executar(usuario, p.entrada)
    except (FerramentaRecusada, FerramentaInvalida) as erro:
        p.situacao, p.motivo = PedidoAprovacao.Situacao.FALHOU, str(erro)[:255]
        p.execucao.resultado = ExecucaoFerramenta.Resultado.ERRO
        p.execucao.detalhe = f"Aprovada por {usuario}, mas falhou: {erro}"[:255]
        p.execucao.save(update_fields=["resultado", "detalhe"])
    else:
        p.situacao = PedidoAprovacao.Situacao.APROVADO
        p.execucao.resultado = ExecucaoFerramenta.Resultado.OK
        p.execucao.detalhe = f"Aprovada e executada por {usuario}."[:255]
        p.execucao.save(update_fields=["resultado", "detalhe"])
    p.save()
    return p


def _recusar(usuario, pk: int, motivo: str) -> PedidoAprovacao:
    p = _pedido(usuario, pk)
    p.situacao, p.motivo = PedidoAprovacao.Situacao.RECUSADO, (motivo or "Recusado.")[:255]
    p.decidido_por, p.decidido_em = usuario, timezone.now()
    p.save()
    p.execucao.resultado = ExecucaoFerramenta.Resultado.NEGADA
    p.execucao.detalhe = f"Recusada por {usuario}."[:255]
    p.execucao.save(update_fields=["resultado", "detalhe"])
    return p
