"""Eventos PCPR → n8n (envelope `docs/automacao/contratos/evento-integracao.schema.json`).

O evento nasce na transação da mudança (`publicar`) e um worker com lease o entrega ao
webhook do n8n pela rede interna, fora de transação, assinado:
`X-PCPR-Assinatura: t=<unix>,v1=<hex HMAC-SHA256(segredo, t + "." + corpo_bruto)>`.

- 2xx: entregue; 401: o destino recusou a assinatura/ambiente → configuração, sem repetir,
  vira exceção; outro status ou rede: repete com espera crescente até 8 vezes.
- Sem `N8N_EVENTOS_URL`, nada é publicado: o transporte interno não precisa do n8n, e a
  reconciliação (`GET /comunicacoes/devidas`) cobre o que um evento perdido deixaria de fora.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from gestao.plataforma import ambiente, recursos

from . import excecoes
from .models import ExcecaoAutomacao
from .models_api import EventoIntegracao

log = logging.getLogger("gestao.automacao")
MAX_TENTATIVAS = 8
PRAZO = timedelta(minutes=2)
AMBIENTES = {"production": "producao", "staging": "treinamento", "preview": "preview"}


def ligado() -> bool:
    return bool(recursos.ligado(recursos.AUTOMACAO) and
                getattr(settings, "N8N_EVENTOS_URL", "") and
                getattr(settings, "N8N_EVENTOS_SEGREDO", ""))


def publicar(tipo: str, recurso: dict, dados: dict, correlacao: str) -> EventoIntegracao | None:
    """Na transação da mudança. Dados mínimos: ids e datas, nunca destino, texto ou link."""
    if not ligado():
        return None
    if not connection.in_atomic_block:
        raise RuntimeError("publicar() roda na transação da mudança de negócio.")
    identificador = uuid.uuid4()
    corpo = {"id": str(identificador), "tipo": tipo, "versao_contrato": 1,
             "ocorrido_em": timezone.now().astimezone(UTC).isoformat().replace(
                 "+00:00", "Z"),
             "ambiente": AMBIENTES.get(ambiente.atual(), "teste"), "recurso": recurso,
             "correlacao_id": correlacao[:120], "dados": dados}
    return EventoIntegracao.objects.create(uuid=identificador, tipo=tipo, corpo=corpo,
                                           disponivel_em=timezone.now())


def assinar(corpo: bytes, segredo: str, agora: int | None = None) -> str:
    t = str(int(agora if agora is not None else time.time()))
    v1 = hmac.new(segredo.encode(), t.encode() + b"." + corpo, hashlib.sha256).hexdigest()
    return f"t={t},v1={v1}"


@transaction.atomic
def reservar() -> EventoIntegracao | None:
    agora = timezone.now()
    e = (EventoIntegracao.objects.select_for_update(skip_locked=True)
         .filter(situacao__in=(EventoIntegracao.Situacao.PENDENTE,
                               EventoIntegracao.Situacao.ENTREGANDO),
                 disponivel_em__lte=agora)
         .exclude(situacao=EventoIntegracao.Situacao.ENTREGANDO, reservado_ate__gt=agora)
         .order_by("disponivel_em", "id").first())
    if e is None:
        return None
    e.situacao, e.reservado_ate = EventoIntegracao.Situacao.ENTREGANDO, agora + PRAZO
    e.tentativas += 1
    e.save(update_fields=["situacao", "reservado_ate", "tentativas"])
    return e


class _SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _postar(url: str, corpo: bytes, cabecalhos: dict[str, str]) -> int:
    partes = urllib.parse.urlsplit(url)
    if partes.scheme not in ("http", "https"):
        raise ValueError("URL do n8n inválida.")
    pedido = urllib.request.Request(url, data=corpo, headers=cabecalhos, method="POST")  # noqa: S310
    abridor = urllib.request.build_opener(_SemRedirecionar())  # a assinatura não segue 3xx
    try:
        with abridor.open(pedido, timeout=10) as r:  # nosec B310 — rede interna, sem 3xx
            return r.status
    except urllib.error.HTTPError as erro:
        return erro.code


def entregar(e: EventoIntegracao, postar=_postar) -> str:
    """Fora de transação. Devolve a situação final desta tentativa."""
    corpo = json.dumps(e.corpo, ensure_ascii=False, separators=(",", ":")).encode()
    cabecalhos = {"Content-Type": "application/json", "X-PCPR-Evento-Id": str(e.uuid),
                  "X-PCPR-Assinatura": assinar(corpo, settings.N8N_EVENTOS_SEGREDO)}
    try:
        status = postar(settings.N8N_EVENTOS_URL, corpo, cabecalhos)
        erro = "" if 200 <= status < 300 else f"HTTP {status}"
    except (OSError, ValueError) as exc:
        status, erro = 0, type(exc).__name__
    with transaction.atomic():
        e = EventoIntegracao.objects.select_for_update().get(pk=e.pk)
        e.reservado_ate = None
        if not erro:
            e.situacao, e.entregue_em, e.ultimo_erro = (EventoIntegracao.Situacao.ENTREGUE,
                                                        timezone.now(), "")
        elif status == 401:
            e.situacao, e.ultimo_erro = EventoIntegracao.Situacao.CONFIGURACAO, erro
            excecoes.abrir(ExcecaoAutomacao.Tipo.CANAL, f"eventos-n8n:{status}",
                           "O n8n recusou a assinatura dos eventos: confira o segredo e o "
                           "ambiente (N8N_EVENTOS_SEGREDO).")
        elif e.tentativas >= MAX_TENTATIVAS:
            e.situacao, e.ultimo_erro = EventoIntegracao.Situacao.FALHOU, erro
            excecoes.abrir(ExcecaoAutomacao.Tipo.CANAL, f"eventos-n8n:falhou:{e.pk}",
                           f"Evento {e.tipo} não chegou ao n8n depois de {e.tentativas} "
                           "tentativas. A reconciliação cobre comunicações devidas.",
                           avisar=False)
        else:
            e.situacao, e.ultimo_erro = EventoIntegracao.Situacao.PENDENTE, erro
            e.disponivel_em = timezone.now() + timedelta(seconds=min(30 * 4 ** e.tentativas,
                                                                     6 * 3600))
        e.save()
    return e.situacao


def processar_um(postar=_postar) -> bool:
    if not ligado():
        return False
    e = reservar()
    if e is None:
        return False
    try:
        entregar(e, postar)
    except Exception:
        log.exception("Falha ao entregar o evento %s", e.pk)
    return True
