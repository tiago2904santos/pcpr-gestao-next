"""Virada de exercício (CB6b; paridade com `coffee_break/virada.py`, §8.4): "Abrir exercício
N+1" copia os lotes vigentes do maior exercício — municípios, texto original, orientações e
especificações —, pedindo só a quantidade e o empenho de cada um; opcionalmente encerra os
de origem. Só o administrador do módulo (quem altera o cadastro de lotes)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction

from . import policies
from .models import Lote

MSG_SEM_LOTES = "Não há lotes vigentes para copiar."
MSG_MARQUE = "Marque ao menos um lote para abrir o exercício."
MSG_CORRIJA = "Corrija as linhas destacadas."
MSG_QUANTIDADE = "Informe a quantidade do novo exercício."


class ViradaInvalida(Exception):
    pass


def exercicio_de_origem() -> int | None:
    """O maior exercício (numérico) entre os lotes vigentes; None sem lotes."""
    anos = [int(e) for e in Lote.objects.filter(ativo=True).values_list("exercicio", flat=True)
            if e.isdecimal()]
    return max(anos) if anos else None


def lotes_de_origem(ano: int) -> list[Lote]:
    return list(Lote.objects.filter(ativo=True, exercicio=str(ano))
                .select_related("contrato__fornecedor")
                .prefetch_related("contrato__aditivos", "municipios")
                .order_by("contrato__numero", "numero", "pk"))


def impedimento(lote: Lote, destino: int) -> str:
    """Por que o lote não pode ir para o ano `destino` ("" quando pode)."""
    if Lote.objects.filter(contrato=lote.contrato, numero=lote.numero,
                           exercicio=str(destino)).exists():
        return f"O Lote {lote.numero} ({destino}) deste contrato já existe."
    fim = lote.contrato.fim_efetivo()
    if fim and fim < date(destino, 1, 1):
        return f"Contrato vencido em {fim:%d/%m/%Y}: providencie o aditivo de prorrogação antes."
    return ""


def aviso_de_vigencia(lote: Lote, destino: int) -> str:
    """A vigência acaba durante o ano novo: o lote pode ser criado, com aviso."""
    fim = lote.contrato.fim_efetivo()
    if fim and date(destino, 1, 1) <= fim < date(destino, 12, 31):
        return f"O contrato vai até {fim:%d/%m/%Y}: o lote de {destino} só cobre eventos até lá."
    return ""


@dataclass
class Linha:
    origem: Lote
    criar: bool
    quantidade: int | None
    empenho: str = ""
    valor_empenho: Decimal | None = None
    erro: str = ""


@transaction.atomic
def abrir_exercicio(usuario, destino: int, linhas: list[Linha], encerrar: bool) -> list[Lote]:
    """Cria os lotes do ano `destino` das linhas marcadas; devolve os criados. Recusa tudo
    se alguma linha marcada tiver impedimento ou faltar a quantidade (`linha.erro`)."""
    if not policies.pode_gerir_cadastros(usuario, "lotes"):
        raise PermissionDenied
    marcadas = [linha for linha in linhas if linha.criar]
    if not marcadas:
        raise ViradaInvalida(MSG_MARQUE)
    for linha in marcadas:
        linha.erro = impedimento(linha.origem, destino) or (
            "" if linha.quantidade and linha.quantidade > 0 else MSG_QUANTIDADE)
    if any(linha.erro for linha in marcadas):
        raise ViradaInvalida(MSG_CORRIJA)
    criados = []
    for linha in marcadas:
        o = linha.origem
        novo = Lote.objects.create(
            contrato=o.contrato, numero=o.numero, exercicio=str(destino),
            quantidade_total=linha.quantidade or 0, empenho=linha.empenho.strip()[:60],
            valor_empenho=linha.valor_empenho, municipios_texto=o.municipios_texto,
            orientacoes=o.orientacoes, especificacoes=o.especificacoes,
            observacoes=f"Aberto na virada do exercício a partir do Lote {o.numero} "
                        f"({o.exercicio}).", ativo=True)
        novo.municipios.set(o.municipios.all())
        criados.append(novo)
        if encerrar:
            o.ativo = False
            o.save(update_fields=["ativo", "atualizado_em"])
    return criados


def mensagem(criados: list[Lote], origem: int, destino: int, encerrar: bool) -> str:
    n = len(criados)
    s = "s" if n != 1 else ""
    texto = (f"Exercício {destino} aberto: {n} lote{s} criado{s} com os municípios, "
             f"orientações e especificações de {origem}.")
    if encerrar:
        texto += f" Os lotes de {origem} copiados foram encerrados."
    return texto
