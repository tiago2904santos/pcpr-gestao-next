"""Assinantes da outbox do módulo Viagens (executados pelo worker, fora da requisição)."""

from __future__ import annotations

import logging

from django.core.files.base import ContentFile
from django.utils import timezone

from gestao.plataforma.outbox import assinante

log = logging.getLogger(__name__)


def _registrar_falha(payload: dict, erro: Exception) -> None:
    """Executado pela outbox depois de reverter a geração que falhou."""
    from .models import Documento

    Documento.objects.filter(pk=payload["documento_id"]).exclude(
        situacao=Documento.Situacao.PRONTO).update(
            situacao=Documento.Situacao.FALHOU, erro=f"{type(erro).__name__}: {erro}"[:2000])


@assinante("viagens.documento.gerar", ao_falhar=_registrar_falha)
def gerar_documento(payload: dict) -> None:
    """Gera o PDF/A-2a de uma versão de documento. Idempotente: versão pronta não é refeita."""
    from .documentos.pdf import gerar_pdf
    from .models import Documento, Historico

    doc = Documento.objects.select_for_update().select_related("oficio").get(
        pk=payload["documento_id"])
    if doc.situacao == Documento.Situacao.PRONTO:
        return
    conteudo, sha = gerar_pdf(doc.tipo, doc.dados)
    doc.arquivo.save(doc.nome_arquivo, ContentFile(conteudo), save=False)
    doc.sha256, doc.tamanho = sha, len(conteudo)
    doc.situacao, doc.erro, doc.gerado_em = Documento.Situacao.PRONTO, "", timezone.now()
    doc.save(update_fields=["arquivo", "sha256", "tamanho", "situacao", "erro", "gerado_em"])
    Historico.objects.create(
        oficio=doc.oficio, acao=Historico.Acao.DOCUMENTO,
        descricao=f"{doc.get_tipo_display()} versão {doc.versao} gerado (PDF/A-2a).",
        dados={"sha256": sha, "tamanho": len(conteudo)},
    )


@assinante("viagens.oficio.emitido")
def notificar_emissao(payload: dict) -> None:
    """Ponto de extensão: notificações e eProtocolo (docs/product/integrations.md)."""
    log.info("Ofício %s emitido", payload.get("oficio_id"))
