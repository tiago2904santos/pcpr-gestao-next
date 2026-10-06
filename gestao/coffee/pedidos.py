"""Escritas da solicitação de coffee break (CB2): registrar/editar a etapa 1 com o lote
escolhido pelo município e o saldo conferido sob a trava do lote, cancelar, reativar e
excluir (paridade com `coffee_break/services.py` e `views.py`; mensagens da referência)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import dominio_pedido as regras
from . import policies, queries
from .models import Lote, Movimento, Solicitacao


class PedidoInvalido(Exception):
    def __init__(self, mensagem: str, campo: str | None = None):
        super().__init__(mensagem)
        self.campo = campo


@dataclass
class Resultado:
    solicitacao: Solicitacao
    aviso: str = ""


ROTULOS = {"municipio": "município", "data_solicitacao": "data da solicitação",
           "numero": "Nº da OS", "descricao": "descrição", "quantidade": "quantidade",
           "data_evento": "data do evento", "horario": "horário",
           "local_entrega": "local de entrega", "endereco": "endereço", "bairro": "bairro",
           "cep": "CEP", "responsavel": "responsável pelo recebimento"}
CAMPOS = tuple(ROTULOS)


def _exigir(usuario) -> None:
    if not policies.pode_acessar(usuario):
        raise PermissionDenied


def _mover(s: Solicitacao, usuario, acao: str, texto: str = "") -> None:
    Movimento.objects.create(solicitacao=s, acao=acao, texto=texto.strip(), usuario=usuario)


def _numero(s: Solicitacao, digitado: str, ano: int) -> str:
    """Em branco: o próximo. Digitado: conferido contra os já usados."""
    try:
        numero = regras.formatar_numero(digitado, ano)
    except ValueError as exc:
        raise PedidoInvalido(str(exc), "numero") from None
    if not numero:
        return queries.proximo_numero(ano)
    outra = Solicitacao.objects.filter(numero=numero).exclude(pk=s.pk).first()
    if outra is not None:
        raise PedidoInvalido(f"A OS {numero} já existe ({outra.descricao[:60]}). A próxima "
                             f"livre é {queries.proximo_numero(ano)}.", "numero")
    return numero


@transaction.atomic
def salvar(usuario, dados: dict[str, Any], solicitacao: Solicitacao | None = None, *,
           retroativo: bool = False, justificativa: str = "",
           duplicada_de: Solicitacao | None = None, hoje: date | None = None,
           versao: str | None = None) -> Resultado:
    """Grava a etapa 1. O lote vem do município (registro existente só troca de lote se o
    município mudar); vigência só para pedido novo ou quando município/data mudam; o saldo
    é revalidado com a linha do lote travada."""
    _exigir(usuario)
    hoje = hoje or timezone.localdate()
    novo = solicitacao is None
    s = solicitacao if solicitacao is not None else Solicitacao(criado_por=usuario)
    if not novo:
        s = Solicitacao.objects.select_for_update().get(pk=s.pk)
        if s.bloqueada:
            raise PermissionDenied(regras.MSG_BLOQUEADA)
        if versao is not None and versao != s.atualizado_em.isoformat():
            raise PedidoInvalido(regras.MSG_VERSAO)
        if s.financeiro_iniciado:  # travados: valem os gravados (relidos sob a trava)
            dados = {**dados, **{c: getattr(s, c) for c in (
                "municipio", "data_solicitacao", "descricao", "quantidade", "data_evento")},
                "numero": s.numero}
    antes = {c: getattr(s, c) for c in CAMPOS} if not novo else {}
    municipio = dados["municipio"]
    data_ref = dados.get("data_evento") or dados["data_solicitacao"]
    mudou_local = novo or municipio.pk != s.municipio_id or data_ref != (
        s.data_evento or s.data_solicitacao)
    try:
        regras.conferir_retroativo(dados.get("data_evento"), dados["data_solicitacao"],
                                   retroativo, justificativa)
    except ValueError as exc:
        raise PedidoInvalido(str(exc), "data_evento") from None
    if novo or municipio.pk != s.municipio_id:
        info = queries.lote_para(municipio, data_ref)
        if info is None:
            raise PedidoInvalido(regras.MSG_SEM_LOTE.format(
                municipio=f"{municipio.nome}/{municipio.uf}"), "municipio")
        lote = info.lote
        s.valor_unitario = lote.contrato.valor_unitario  # preço do contrato, congelado
    else:
        lote = s.lote
    lote = Lote.objects.select_for_update().select_related("contrato").get(pk=lote.pk)
    if mudou_local:
        try:
            regras.conferir_vigencia(lote.contrato.fim_efetivo(), data_ref,
                                     lote.contrato.numero, str(lote))
        except ValueError as exc:
            raise PedidoInvalido(str(exc), "data_evento") from None
    for campo in CAMPOS:
        if campo in dados and campo != "numero":
            setattr(s, campo, dados[campo])
    s.descricao = " ".join((s.descricao or "").split())
    s.lote = lote
    s.numero = _numero(s, dados.get("numero", ""), (dados["data_solicitacao"] or hoje).year)
    sal = queries.saldo(lote, exceto=s.pk)
    if s.quantidade_efetiva > sal.restante:
        raise PedidoInvalido(regras.MSG_SALDO.format(restante=sal.restante, total=sal.total),
                             "quantidade")
    em_branco = not (dados.get("numero") or "").strip()
    for tentativa in range(3):
        try:
            with transaction.atomic():
                s.save()
            break
        except IntegrityError as exc:
            restricao = getattr(getattr(exc.__cause__, "diag", None), "constraint_name", "")
            if restricao != "coffee_os_numero_unico":
                raise
            if not em_branco or tentativa == 2:
                raise PedidoInvalido(
                    f"A OS {s.numero} acabou de ser usada. A próxima livre é "
                    f"{queries.proximo_numero(dados['data_solicitacao'].year)}.",
                    "numero") from None
            s.numero = queries.proximo_numero(dados["data_solicitacao"].year)
    if novo:
        origem = f" Duplicada da solicitação {duplicada_de}." if duplicada_de else ""
        _mover(s, usuario, Movimento.Acao.CRIADA,
               f"Solicitação {s.numero} registrada no {lote} ({lote.contrato.fornecedor})."
               + origem)
    else:
        mudancas = [ROTULOS[c] for c in CAMPOS if antes.get(c) != getattr(s, c)]
        _mover(s, usuario, Movimento.Acao.ATUALIZADA,
               f"Campos atualizados: {', '.join(mudancas)}." if mudancas
               else "Solicitação salva sem alteração de campos.")
    if retroativo and justificativa.strip():
        _mover(s, usuario, Movimento.Acao.ATUALIZADA,
               f"Registro retroativo: {justificativa.strip()}")
    aviso = regras.aviso_antecedencia(s.data_evento, hoje, lote.contrato.antecedencia_minima_dias,
                                      lote.contrato.numero)
    return Resultado(s, aviso)


@transaction.atomic
def cancelar(usuario, pk: int, motivo: str) -> Solicitacao:
    _exigir(usuario)
    s = Solicitacao.objects.select_for_update().get(pk=pk)
    if s.cancelada:
        raise PedidoInvalido(regras.MSG_JA_CANCELADA)
    if s.concluida:
        raise PedidoInvalido(regras.MSG_CONCLUIDA_NAO_CANCELA)
    motivo = (motivo or "").strip()[:255]
    if not motivo:
        raise PedidoInvalido(regras.MSG_MOTIVO, "motivo")
    s.cancelada, s.cancelada_em, s.cancelada_por = True, timezone.now(), usuario
    s.motivo_cancelamento = motivo
    s.save(update_fields=["cancelada", "cancelada_em", "cancelada_por", "motivo_cancelamento",
                          "atualizado_em"])
    _mover(s, usuario, Movimento.Acao.CANCELADA, motivo)
    return s


@transaction.atomic
def reativar(usuario, pk: int) -> Solicitacao:
    _exigir(usuario)
    s = Solicitacao.objects.select_for_update().get(pk=pk)
    if not s.cancelada:
        raise PedidoInvalido(regras.MSG_NAO_CANCELADA)
    if s.quantidade_efetiva < 1:
        raise PedidoInvalido("Informe uma quantidade válida antes de reativar a solicitação.")
    lote = Lote.objects.select_for_update().get(pk=s.lote_id)
    sal = queries.saldo(lote, exceto=s.pk)
    if s.quantidade_efetiva > sal.restante:
        raise PedidoInvalido(regras.MSG_SALDO.format(restante=sal.restante, total=sal.total))
    s.cancelada, s.cancelada_em, s.cancelada_por, s.motivo_cancelamento = False, None, None, ""
    s.save(update_fields=["cancelada", "cancelada_em", "cancelada_por", "motivo_cancelamento",
                          "atualizado_em"])
    _mover(s, usuario, Movimento.Acao.REATIVADA, "Solicitação reativada e saldo consumido.")
    return s


@transaction.atomic
def excluir(usuario, pk: int) -> str:
    """Só antes da nota e do protocolo (financeiro não iniciado)."""
    _exigir(usuario)
    s = Solicitacao.objects.select_for_update().get(pk=pk)
    if s.financeiro_iniciado:
        raise PedidoInvalido(regras.MSG_EXCLUIR.format(numero=s.numero or f"#{s.pk}"))
    numero = s.numero or f"#{s.pk}"
    s.delete()
    return numero


def dados_para_duplicar(s: Solicitacao) -> dict[str, Any]:
    """Município, descrição, quantidade, horário, local, endereço e responsável; nunca datas,
    número, nota, ofício, protocolo ou pagamento."""
    return {"municipio": f"{s.municipio.nome}/{s.municipio.uf}", "descricao": s.descricao,
            "quantidade": s.quantidade, "horario": s.horario, "local_entrega": s.local_entrega,
            "endereco": s.endereco, "bairro": s.bairro, "cep": s.cep,
            "responsavel": s.responsavel}
