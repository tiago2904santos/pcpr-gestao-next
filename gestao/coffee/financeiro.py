"""Escritas do fluxo financeiro da solicitação de coffee break (CB3): etapas 2 (nota fiscal,
quantidade faturada, ofício ao GAF, PCPR protocolo) e 3 (protocolo de pagamento, atesto,
ordem bancária, envio à empresa), o andamento do próximo marco e a reabertura para correção
(paridade com `coffee_break/services.py`; mensagens da referência)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from . import dominio_pedido as regras
from . import policies, queries
from .models import Lote, Movimento, Solicitacao
from .pedidos import PedidoInvalido

ROTULOS = {"nota_fiscal": "nº da nota fiscal", "quantidade_faturada": "quantidade faturada",
           "numero_oficio": "nº do ofício", "data_oficio": "data do ofício",
           "protocolo_pcpr": "PCPR protocolo n.º",
           "protocolo_pagamento": "protocolo de pagamento",
           "atesto_em": "atesto e envio ao GAF", "ordem_bancaria_em": "ordem bancária",
           "envio_empresa_em": "envio à empresa", "observacoes": "observações"}
CAMPOS = tuple(ROTULOS)


def _exigir(usuario) -> None:
    if not policies.pode_acessar(usuario):
        raise PermissionDenied


def _mover(s: Solicitacao, usuario, acao: str, texto: str) -> None:
    Movimento.objects.create(solicitacao=s, acao=acao, texto=texto.strip(), usuario=usuario)


def _fmt(valor) -> str:
    if valor in (None, ""):
        return "—"
    return f"{valor:%d/%m/%Y}" if isinstance(valor, date) else str(valor)


def _travar(usuario, pk: int, versao: str | None) -> Solicitacao:
    _exigir(usuario)
    s = Solicitacao.objects.select_for_update().get(pk=pk)
    if s.bloqueada:
        raise PermissionDenied(regras.MSG_BLOQUEADA)
    if versao is not None and versao != s.atualizado_em.isoformat():
        raise PedidoInvalido(regras.MSG_VERSAO)
    return s


def _numero_oficio(s: Solicitacao, digitado: str, ano: int) -> str:
    """O mesmo número vale para todas as OS do pagamento conjunto."""
    from . import conjunto
    try:
        numero = regras.formatar_numero(digitado, ano)
    except ValueError:
        raise PedidoInvalido("O número do ofício deve ser 1 ou mais.", "numero_oficio") from None
    if not numero:
        return queries.proximo_oficio(ano)
    grupo = [x.pk for x in conjunto.membros(s)]
    if Solicitacao.objects.filter(numero_oficio=numero).exclude(pk__in=grupo).exists():
        raise PedidoInvalido(f"O ofício {numero} já existe. O próximo livre é "
                             f"{queries.proximo_oficio(ano)}.", "numero_oficio")
    return numero


@transaction.atomic
def salvar_financeiro(usuario, pk: int, dados: dict[str, Any], *, versao: str | None = None,
                      hoje: date | None = None) -> Solicitacao:
    """Grava as etapas 2 e 3 de uma vez, com a ordem dos marcos conferida. Com a nota, o
    ofício em branco recebe o próximo número e a data em branco, hoje; o protocolo de
    pagamento também vale como "PCPR protocolo n.º" quando este está em branco."""
    hoje = hoje or timezone.localdate()
    s = _travar(usuario, pk, versao)
    antes = {c: getattr(s, c) for c in CAMPOS}
    novo = {c: dados.get(c, antes[c]) for c in CAMPOS}
    for c in ("nota_fiscal", "protocolo_pcpr", "observacoes"):
        novo[c] = " ".join(str(novo[c] or "").split()) if c != "observacoes" else (
            novo[c] or "").strip()
    try:
        novo["protocolo_pagamento"] = regras.formatar_protocolo(novo["protocolo_pagamento"])
    except ValueError as exc:
        raise PedidoInvalido(str(exc), "protocolo_pagamento") from None
    if antes["protocolo_pagamento"] and not novo["nota_fiscal"]:
        raise PedidoInvalido(regras.MSG_NOTA_OBRIGATORIA, "nota_fiscal")
    erros = regras.erros_dos_marcos(novo["nota_fiscal"], novo["protocolo_pagamento"],
                                    novo["atesto_em"], novo["ordem_bancaria_em"],
                                    novo["envio_empresa_em"])
    if erros:
        campo, mensagem = next(iter(erros.items()))
        raise PedidoInvalido(mensagem, campo)
    if novo["nota_fiscal"]:
        novo["numero_oficio"] = _numero_oficio(
            s, str(novo["numero_oficio"] or ""), (novo["data_oficio"] or hoje).year)
        novo["data_oficio"] = novo["data_oficio"] or hoje
    elif novo["numero_oficio"]:
        novo["numero_oficio"] = _numero_oficio(s, str(novo["numero_oficio"]),
                                               (novo["data_oficio"] or hoje).year)
    if novo["protocolo_pagamento"] and not novo["protocolo_pcpr"]:
        novo["protocolo_pcpr"] = novo["protocolo_pagamento"]
    from . import conjunto
    for campo in ("protocolo_pagamento", "atesto_em"):
        if novo[campo] and not antes[campo]:
            conjunto.conferir_notas(s, campo)
    if novo["quantidade_faturada"] is not None and novo["quantidade_faturada"] < 1:
        raise PedidoInvalido(regras.MSG_QUANTIDADE, "quantidade_faturada")
    for c in CAMPOS:
        setattr(s, c, novo[c])
    if not s.cancelada and novo["quantidade_faturada"] != antes["quantidade_faturada"]:
        lote = Lote.objects.select_for_update().get(pk=s.lote_id)
        sal = queries.saldo(lote, exceto=s.pk)
        if s.quantidade_efetiva > sal.restante:
            raise PedidoInvalido(regras.MSG_SALDO.format(restante=sal.restante, total=sal.total),
                                 "quantidade_faturada")
    s.save()
    mudancas = [c for c in CAMPOS if antes[c] != novo[c]]
    conjunto.espelhar(s, usuario, mudancas)
    if s.em_correcao:
        for c in mudancas:
            _mover(s, usuario, Movimento.Acao.CORRECAO,
                   f"Correção — {ROTULOS[c]}: {_fmt(antes[c])} → {_fmt(novo[c])}.")
    elif mudancas:
        _mover(s, usuario, Movimento.Acao.ATUALIZADA,
               "Campos atualizados: " + ", ".join(ROTULOS[c] for c in mudancas) + ".")
    if (texto := regras.texto_faturada(s.quantidade, antes["quantidade_faturada"],
                                       novo["quantidade_faturada"])):
        _mover(s, usuario, Movimento.Acao.ATUALIZADA, texto)
    return s


@transaction.atomic
def registrar_marco(usuario, pk: int, valor: str, anotacao: str = "", *,
                    hoje: date | None = None) -> Solicitacao:
    """Grava só o próximo marco (nota → protocolo → atesto → OB → envio)."""
    s = _travar(usuario, pk, None)
    marco = regras.proximo_marco(s.valores_dos_marcos, s.cancelada)
    if marco is None:
        raise PedidoInvalido(regras.MSG_SEM_MARCO)
    campo, rotulo, tipo = marco
    valor = (valor or "").strip()
    if not valor:
        raise PedidoInvalido(f"Informe: {rotulo.lower()}.")
    dado: Any = valor
    if tipo == "data":
        try:
            dado = datetime.strptime(valor, "%d/%m/%Y").date()
        except ValueError:
            try:
                dado = date.fromisoformat(valor)
            except ValueError:
                raise PedidoInvalido("Data inválida.") from None
    elif campo == "protocolo_pagamento":
        try:
            dado = regras.formatar_protocolo(valor)
        except ValueError as exc:
            raise PedidoInvalido(str(exc)) from None
    from . import conjunto
    conjunto.conferir_notas(s, campo)
    valores = {**s.valores_dos_marcos, campo: dado}
    erros = regras.erros_dos_marcos(valores["nota_fiscal"], valores["protocolo_pagamento"],
                                    valores["atesto_em"], valores["ordem_bancaria_em"],
                                    valores["envio_empresa_em"])
    if erros:
        raise PedidoInvalido(next(iter(erros.values())))
    setattr(s, campo, dado)
    if campo == "protocolo_pagamento" and not s.protocolo_pcpr:
        s.protocolo_pcpr = dado
    s.save()
    conjunto.espelhar(s, usuario, [campo, "protocolo_pcpr"])
    texto = f"{rotulo}: {_fmt(dado)}"
    anotacao = (anotacao or "").strip()
    _mover(s, usuario, Movimento.Acao.ANDAMENTO, f"{texto} — {anotacao}" if anotacao else texto)
    return s


@transaction.atomic
def reabrir_correcao(usuario, pk: int, motivo: str) -> Solicitacao:
    """Só o administrador do módulo; só concluída; motivo obrigatório."""
    if not policies.pode_gerir_cadastros(usuario):
        raise PermissionDenied
    s = Solicitacao.objects.select_for_update().get(pk=pk)
    if not s.concluida:
        raise PedidoInvalido(regras.MSG_SO_CONCLUIDA)
    if s.em_correcao:
        raise PedidoInvalido(regras.MSG_JA_EM_CORRECAO)
    motivo = (motivo or "").strip()[:255]
    if not motivo:
        raise PedidoInvalido(regras.MSG_MOTIVO_CORRECAO)
    s.em_correcao = True
    s.save(update_fields=["em_correcao", "atualizado_em"])
    _mover(s, usuario, Movimento.Acao.CORRECAO, f"Reaberta para correção: {motivo}")
    return s


@transaction.atomic
def encerrar_correcao(usuario, pk: int) -> Solicitacao:
    if not policies.pode_gerir_cadastros(usuario):
        raise PermissionDenied
    s = Solicitacao.objects.select_for_update().get(pk=pk)
    if not s.em_correcao:
        raise PedidoInvalido(regras.MSG_NAO_EM_CORRECAO)
    s.em_correcao = False
    s.save(update_fields=["em_correcao", "atualizado_em"])
    _mover(s, usuario, Movimento.Acao.CORRECAO, "Correção encerrada.")
    return s
