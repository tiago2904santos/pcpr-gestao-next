"""Anexos da prestação de contas (módulo 9d, paridade com `anexo_services` e
`PrestacaoDocumentoAnexo` da referência; ficha em docs/migration/prestacao.md).

- Da equipe: despacho assinado (somam) e diário de bordo assinado (um; anexar de novo
  substitui). Do servidor: comprovantes de saque/transferência (somam; valor, data e
  operação) e o RT assinado (um).
- PDF, PNG ou JPG até 10 MB (conferido pelo conteúdo, não só pelo nome).
- Remover ou substituir só marca: fica 30 dias em "versões anteriores" e dá para voltar.
- Trava: o do servidor com ele finalizado; o da equipe com todos finalizados.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from . import diario, policies
from .models import AnexoPrestacao, PrestacaoContas, PrestacaoServidor

TAMANHO_MAXIMO = 10 * 1024 * 1024  # referência: PRIVATE_UPLOAD_MAX_BYTES
DIAS_DE_GUARDA = 30
UNICOS = {AnexoPrestacao.Tipo.RT_ASSINADO, AnexoPrestacao.Tipo.DB_ASSINADO}
DO_SERVIDOR = {AnexoPrestacao.Tipo.COMPROVANTE, AnexoPrestacao.Tipo.RT_ASSINADO}
ASSINATURAS = {".pdf": (b"%PDF-",), ".png": (b"\x89PNG",), ".jpg": (b"\xff\xd8\xff",),
               ".jpeg": (b"\xff\xd8\xff",)}
TIPO_DE_CONTEUDO = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg"}


class AnexoInvalido(Exception):
    pass


def extensao(nome: str) -> str:
    nome = (nome or "").lower()
    return nome[nome.rfind("."):] if "." in nome else ""


def validar(nome: str, tamanho: int, inicio: bytes) -> None:
    ext = extensao(nome)
    if ext not in ASSINATURAS:
        raise AnexoInvalido("Envie um PDF ou uma imagem (PNG ou JPG).")
    if tamanho > TAMANHO_MAXIMO:
        raise AnexoInvalido("O arquivo excede o limite de 10 MB.")
    if not any(inicio.startswith(a) for a in ASSINATURAS[ext]):
        raise AnexoInvalido("O conteúdo do arquivo não confere com o tipo (PDF, PNG ou JPG).")


def ativos(qs=None):
    return (qs if qs is not None else AnexoPrestacao.objects).filter(removido_em__isnull=True)


# ---------------------------------------------------------------- leitura em lote
@dataclass
class Situacao:
    """O que os anexos (e o diário/RT) dizem de várias prestações, em poucas consultas —
    para as pendências e os selos da lista e da planilha."""
    diarios: set[int] = field(default_factory=set)  # prestações com diário preenchido
    relatorios: set[int] = field(default_factory=set)  # prestações com RT preenchido
    despachos: set[int] = field(default_factory=set)
    db_assinados: set[int] = field(default_factory=set)
    rt_assinados: set[int] = field(default_factory=set)  # ps
    comprovantes: dict[int, list[Decimal | None]] = field(default_factory=dict)  # ps → valores


def situacao(prestacao_ids) -> Situacao:
    from . import relatorio
    ids = list(prestacao_ids)
    s = Situacao(diarios=diario.preenchidos(ids), relatorios=relatorio.preenchidos(ids))
    for tipo, prestacao_id, servidor_id, valor in (
            ativos(AnexoPrestacao.objects.filter(prestacao_id__in=ids))
            .values_list("tipo", "prestacao_id", "servidor_id", "valor")):
        if tipo == AnexoPrestacao.Tipo.DESPACHO:
            s.despachos.add(prestacao_id)
        elif tipo == AnexoPrestacao.Tipo.DB_ASSINADO:
            s.db_assinados.add(prestacao_id)
        elif tipo == AnexoPrestacao.Tipo.RT_ASSINADO:
            s.rt_assinados.add(servidor_id)
        else:
            s.comprovantes.setdefault(servidor_id, []).append(valor)
    return s


def divergencia(ps: PrestacaoServidor, valores: list[Decimal | None],
                liberada: Decimal | None) -> tuple[Decimal, Decimal] | None:
    """(soma, esperado) quando os comprovantes não batem com a diária (a recebida, ou a
    liberada); None quando batem ou não dá para saber (sem comprovante ou algum sem valor)."""
    if not valores or any(v is None for v in valores):
        return None
    esperado = ps.diaria_valor_override or liberada
    if esperado is None:
        return None
    soma = sum((v for v in valores if v is not None), Decimal("0"))
    return None if soma == esperado else (soma, esperado)


# ---------------------------------------------------------------- escrita
def _travado(prestacao: PrestacaoContas, ps: PrestacaoServidor | None) -> bool:
    if ps is not None:
        return ps.finalizada
    return diario.equipe_finalizada(prestacao)


def _conferir_dono(usuario, prestacao: PrestacaoContas, ps: PrestacaoServidor | None) -> None:
    policies.exigir(policies.pode_editar_equipe_prestacao(usuario, prestacao),
                    "Você não pode alterar os documentos desta prestação.")
    if _travado(prestacao, ps):
        raise AnexoInvalido("Prestação finalizada — reabra para editar.")


@transaction.atomic
def anexar(usuario, prestacao_pk: int, tipo: str, *, nome: str, conteudo: bytes,
           servidor_pk: int | None = None, valor: Decimal | None = None,
           data_operacao: date | None = None, operacao: str = "") -> AnexoPrestacao:
    if tipo not in AnexoPrestacao.Tipo.values:
        raise AnexoInvalido("Tipo de documento inválido.")
    validar(nome, len(conteudo), conteudo[:8])
    prestacao = (PrestacaoContas.objects.select_for_update().select_related("oficio")
                 .get(pk=prestacao_pk))
    ps = None
    if tipo in DO_SERVIDOR:
        ps = (PrestacaoServidor.objects.filter(prestacao=prestacao, pk=servidor_pk or 0,
                                               removida_em__isnull=True).first())
        if ps is None:
            raise AnexoInvalido("Escolha o servidor do documento.")
    _conferir_dono(usuario, prestacao, ps)
    if valor is not None and valor <= 0:
        raise AnexoInvalido("O valor da operação precisa ser maior que zero.")
    if operacao and operacao not in AnexoPrestacao.Operacao.values:
        operacao = ""
    comprovante = tipo == AnexoPrestacao.Tipo.COMPROVANTE
    anexo = AnexoPrestacao(prestacao=prestacao, servidor=ps, tipo=tipo,
                           nome_original=(nome or "")[:255],
                           sha256=hashlib.sha256(conteudo).hexdigest(), tamanho=len(conteudo),
                           valor=valor if comprovante else None,
                           data_operacao=data_operacao if comprovante else None,
                           operacao=operacao if comprovante else "", enviado_por=usuario)
    anexo.arquivo.save(f"{tipo}-{prestacao.pk}{extensao(nome)}", ContentFile(conteudo),
                       save=False)
    try:  # se a gravação falhar, o arquivo não fica órfão no disco
        if tipo in UNICOS:
            ativos(AnexoPrestacao.objects.filter(prestacao=prestacao, tipo=tipo, servidor=ps)
                   ).update(removido_em=timezone.now(),
                            removido_motivo=AnexoPrestacao.Removido.SUBSTITUIDO)
        anexo.save()
    except Exception:
        anexo.arquivo.delete(save=False)
        raise
    return anexo


def _travar_anexo(usuario, anexo_pk: int) -> AnexoPrestacao:
    anexo = (AnexoPrestacao.objects.select_for_update(of=("self",))
             .select_related("prestacao__oficio", "servidor").get(pk=anexo_pk))
    _conferir_dono(usuario, anexo.prestacao, anexo.servidor)
    return anexo


@transaction.atomic
def remover(usuario, anexo_pk: int) -> AnexoPrestacao:
    anexo = _travar_anexo(usuario, anexo_pk)
    if anexo.removido:
        raise AnexoInvalido("Este documento já tinha sido removido.")
    anexo.removido_em, anexo.removido_motivo = timezone.now(), AnexoPrestacao.Removido.EXCLUIDO
    anexo.save(update_fields=["removido_em", "removido_motivo"])
    return anexo


@transaction.atomic
def restaurar(usuario, anexo_pk: int) -> AnexoPrestacao:
    """Volta um removido/substituído (dentro dos 30 dias); o assinado em uso sai."""
    anexo = _travar_anexo(usuario, anexo_pk)
    if not anexo.removido:
        raise AnexoInvalido("Este documento já está em uso.")
    if anexo.removido_em and anexo.removido_em < timezone.now() - timedelta(days=DIAS_DE_GUARDA):
        raise AnexoInvalido(f"Passaram mais de {DIAS_DE_GUARDA} dias: este documento não "
                            "pode mais voltar.")
    if anexo.tipo in UNICOS:
        ativos(AnexoPrestacao.objects.filter(prestacao=anexo.prestacao, tipo=anexo.tipo,
                                             servidor=anexo.servidor)
               ).update(removido_em=timezone.now(),
                        removido_motivo=AnexoPrestacao.Removido.SUBSTITUIDO)
    anexo.removido_em, anexo.removido_motivo = None, ""
    anexo.save(update_fields=["removido_em", "removido_motivo"])
    return anexo


@transaction.atomic
def editar_comprovante(usuario, anexo_pk: int, *, valor: Decimal | None,
                       data_operacao: date | None, operacao: str) -> AnexoPrestacao:
    anexo = _travar_anexo(usuario, anexo_pk)
    if anexo.tipo != AnexoPrestacao.Tipo.COMPROVANTE or anexo.removido:
        raise AnexoInvalido("Só o comprovante em uso tem valor, data e operação.")
    if valor is not None and valor <= 0:
        raise AnexoInvalido("O valor da operação precisa ser maior que zero.")
    anexo.valor, anexo.data_operacao = valor, data_operacao
    anexo.operacao = operacao if operacao in AnexoPrestacao.Operacao.values else ""
    anexo.save(update_fields=["valor", "data_operacao", "operacao"])
    return anexo


def versoes_anteriores(prestacao: PrestacaoContas):
    limite = timezone.now() - timedelta(days=DIAS_DE_GUARDA)
    return (AnexoPrestacao.objects.filter(prestacao=prestacao, removido_em__gte=limite)
            .select_related("servidor__servidor").order_by("-removido_em"))
