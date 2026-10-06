"""Entregas e ocorrências do Coffee Break (CB6a; paridade com `coffee_break/services.py`
§7): registrar a partir do dia do evento (não em cancelada), com o que aconteceu, a nota de
1 a 5, quem recebeu, a observação (obrigatória quando há ocorrência) e uma foto ou documento.
O resumo por fornecedor junta as entregas, a nota média e as ocorrências."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from . import dominio_painel as regras
from . import policies
from .models import Entrega, Movimento, Solicitacao
from .pedidos import PedidoInvalido

# Extensão → início do conteúdo (a extensão sozinha não prova o tipo).
ASSINATURAS = {".pdf": b"%PDF-", ".png": b"\x89PNG\r\n\x1a\n",".jpg": b"\xff\xd8\xff",
               ".jpeg": b"\xff\xd8\xff"}
TAMANHO_MAXIMO = 10 * 1024 * 1024
MSG_TIPO = "Envie uma foto (PNG ou JPG) ou um PDF."
MSG_CONTEUDO = ("O conteúdo do arquivo não corresponde à extensão: envie uma foto (PNG ou JPG) "
                "ou um PDF.")
MSG_CANCELADA = "Solicitação cancelada não recebe registro de entrega."


def _conferir_anexo(arquivo) -> None:
    nome = str(getattr(arquivo, "name", "")).lower()
    extensao = nome[nome.rfind("."):] if "." in nome else ""
    if extensao not in ASSINATURAS:
        raise PedidoInvalido(MSG_TIPO, "anexo")
    if getattr(arquivo, "size", 0) > TAMANHO_MAXIMO:
        raise PedidoInvalido("O arquivo passa de 10 MB.", "anexo")
    inicio = arquivo.read(8)
    arquivo.seek(0)
    if not inicio.startswith(ASSINATURAS[extensao]):
        raise PedidoInvalido(MSG_CONTEUDO, "anexo")


def pode_registrar(s: Solicitacao, hoje: date) -> bool:
    return not s.cancelada and (s.data_evento is None or s.data_evento <= hoje)


@transaction.atomic
def registrar(usuario, pk: int, *, tipo: str, avaliacao: int | None, recebido_por: str,
              observacao: str, anexo=None, hoje: date | None = None) -> Entrega:
    if not policies.pode_acessar(usuario):
        raise PermissionDenied
    hoje = hoje or timezone.localdate()
    s = Solicitacao.objects.select_for_update().get(pk=pk)
    if s.cancelada:
        raise PedidoInvalido(MSG_CANCELADA)
    if s.data_evento and s.data_evento > hoje:
        raise PedidoInvalido(regras.MSG_ENTREGA_ANTES)
    if tipo not in regras.ROTULO_ENTREGA:
        raise PedidoInvalido("Escolha o que aconteceu na entrega.", "tipo")
    if avaliacao is not None and not 1 <= avaliacao <= 5:
        raise PedidoInvalido("A avaliação vai de 1 a 5.", "avaliacao")
    observacao = (observacao or "").strip()
    if tipo != "sem_ocorrencia" and not observacao:
        raise PedidoInvalido(regras.MSG_DESCREVA, "observacao")
    if anexo:
        _conferir_anexo(anexo)
    e = Entrega.objects.create(solicitacao=s, tipo=tipo, avaliacao=avaliacao,
                               recebido_por=(recebido_por or "").strip()[:150],
                               observacao=observacao, anexo=anexo or "",
                               registrado_por=usuario)
    try:
        _historico(e, usuario)
    except Exception:
        if e.anexo:  # o arquivo já foi para o disco: não fica órfão se o registro não sai
            e.anexo.storage.delete(str(e.anexo.name))
        raise
    return e


def _historico(e: Entrega, usuario) -> None:
    tipo, avaliacao, observacao = e.tipo, e.avaliacao, e.observacao
    partes = [f"Entrega registrada: {regras.ROTULO_ENTREGA[tipo]}"]
    if avaliacao:
        partes.append(f"avaliação {avaliacao}/5")
    if e.recebido_por:
        partes.append(f"recebido por {e.recebido_por}")
    texto = "; ".join(partes) + "." + (f" {observacao}" if observacao else "")
    Movimento.objects.create(solicitacao=e.solicitacao, acao=Movimento.Acao.ENTREGA,
                             texto=texto, usuario=usuario)


def mensagem(e: Entrega) -> str:
    return f"Entrega registrada: {regras.ROTULO_ENTREGA[e.tipo]}."


@dataclass
class Resumo:
    entregas: int = 0
    media: float | None = None
    ocorrencias: int = 0
    por_tipo: dict[str, int] = field(default_factory=dict)

    @property
    def texto(self) -> str:
        if not self.entregas:
            return "Nenhuma entrega registrada"
        plural = "s" if self.entregas != 1 else ""
        partes = [f"{self.entregas} entrega{plural} registrada{plural}"]
        if self.media is not None:
            partes.append(f"nota média {self.media:.1f}".replace(".", ","))
        if self.ocorrencias:
            partes.append(f"{self.ocorrencias} ocorrência{'s' if self.ocorrencias != 1 else ''}")
        return " · ".join(partes)


def resumos(fornecedores: list[int]) -> dict[int, Resumo]:
    """Resumo das entregas por fornecedor (uma consulta para a lista toda)."""
    saida = {f: Resumo() for f in fornecedores}
    chave = "solicitacao__lote__contrato__fornecedor_id"
    linhas = (Entrega.objects.filter(**{f"{chave}__in": fornecedores}).values(chave)
              .annotate(total=Count("pk"), media=Avg("avaliacao"),
                        ocorr=Count("pk", filter=~Q(tipo="sem_ocorrencia"))).order_by())
    for linha in linhas:
        media = linha["media"]
        saida[linha[chave]] = Resumo(linha["total"], float(media) if media is not None else None,
                                     linha["ocorr"])
    return saida


def resumo_do_fornecedor(fornecedor_id: int) -> Resumo:
    r = resumos([fornecedor_id])[fornecedor_id]
    chave = "solicitacao__lote__contrato__fornecedor_id"
    r.por_tipo = dict(Entrega.objects.filter(**{chave: fornecedor_id})
                      .exclude(tipo="sem_ocorrencia").values_list("tipo")
                      .annotate(c=Count("pk")).order_by())
    return r
