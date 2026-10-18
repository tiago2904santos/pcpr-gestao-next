"""Agendar uma comunicação (na transação da mudança de negócio) e as ações humanas sobre ela.

`agendar` é o "evento transacional": a linha nasce junto com a mudança que a motivou e, se
a transação desfizer, a mensagem também some. Nada sai daqui para a rede — o worker
(`entrega.py`) reserva, revalida e envia depois, fora de transação.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.db import connection, transaction
from django.utils import timezone

from . import excecoes, ganchos, policies
from .models import Comunicacao, ContatoVerificado

S = Comunicacao.Situacao


class ComunicacaoInvalida(Exception):
    pass


def _notificar_worker() -> None:
    with connection.cursor() as cur:
        cur.execute("NOTIFY automacao")


def contato_vigente(servidor_id: int | None, canal: str) -> ContatoVerificado | None:
    if not servidor_id:
        return None
    return (ContatoVerificado.objects.filter(servidor_id=servidor_id, canal=canal,
                                             revogado_em__isnull=True)
            .order_by("-criado_em").first())


def agendar(*, tipo: str, servidor_id: int | None, recurso: str, chave: str,
            unidade_id: int | None = None, criada_por=None, contexto: dict | None = None,
            versao: str = "", canal: str = "whatsapp", agendada_para: datetime | None = None,
            em_resposta_a=None, contato: ContatoVerificado | None = None) -> Comunicacao:
    """Cria (ou devolve, se a chave já existe) a comunicação. Precisa de transação aberta."""
    if not connection.in_atomic_block:
        raise ComunicacaoInvalida("agendar() roda na transação da mudança de negócio.")
    definicao = ganchos.tipo(tipo)
    if definicao is None:
        raise ComunicacaoInvalida(f"Tipo de comunicação não registrado: {tipo}")
    agora = timezone.now()
    quando = agendada_para or agora
    # O modo do fluxo (sombra/assistido/automático) vale na hora do envio, não aqui: quem
    # muda o modo muda também o que já estava na fila.
    situacao = S.AGENDADA
    comunicacao, criada = Comunicacao.objects.get_or_create(chave=chave[:200], defaults={
        "tipo": tipo, "fluxo": definicao.fluxo, "canal": canal, "servidor_id": servidor_id,
        "contato": contato or contato_vigente(servidor_id, canal), "unidade_id": unidade_id,
        "recurso": recurso[:80], "versao": versao[:64], "contexto": contexto or {},
        "situacao": situacao, "agendada_para": quando, "proxima_tentativa_em": quando,
        "expira_em": quando + definicao.validade if definicao.validade else None,
        "aceita_resposta": definicao.aceita_resposta,
        "criada_por": criada_por if getattr(criada_por, "pk", None) else None,
        "em_resposta_a": em_resposta_a})
    if criada:
        transaction.on_commit(_notificar_worker)
        from . import contrato, eventos

        eventos.publicar("comunicacao.agendada",
                         {"tipo": "comunicacao", "id": comunicacao.pk, "versao": 1},
                         {"comunicacao_id": comunicacao.pk,
                          "fluxo": contrato.fluxo(comunicacao.fluxo),
                          "tipo_comunicacao": contrato.tipo(comunicacao.tipo),
                          "enviar_em": quando.isoformat(), "imediato": quando <= agora},
                         correlacao=f"com-{comunicacao.pk}")
    return comunicacao


def encerrar_relacionadas(recurso: str, tipos: tuple[str, ...], motivo: str) -> int:
    """O assunto se resolveu (ex.: o comprovante chegou): o que ainda não saiu fica
    obsoleto. O que já saiu fica como está — não se "desmanda" mensagem."""
    pendentes = Comunicacao.objects.select_for_update().filter(
        recurso=recurso, tipo__in=tipos,
        situacao__in=(S.AGUARDANDO_APROVACAO, S.AGENDADA, S.RESERVADA))
    total = 0
    for c in pendentes:
        # Também o já reservado pelo transporte: se o resultado chegar depois,
        # `registrar_resultado` não o reagenda e, se saiu, abre exceção (como no opt-out).
        c.situacao, c.motivo, c.reservada_ate = S.OBSOLETA, motivo[:255], None
        c.save(update_fields=["situacao", "motivo", "reservada_ate", "atualizada_em"])
        total += 1
    return total


# ------------------------------------------------------------------ ações humanas
def _travar(usuario, pk: int) -> Comunicacao:
    c = Comunicacao.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_operar_objeto(usuario, c),
                    "Você não pode mexer nesta comunicação.")
    return c


@transaction.atomic
def aprovar(usuario, pk: int) -> Comunicacao:
    """Modo assistido: uma pessoa autoriza este envio (revalidado de novo ao sair)."""
    c = _travar(usuario, pk)
    if c.situacao != S.AGUARDANDO_APROVACAO:
        raise ComunicacaoInvalida("Esta comunicação não está aguardando aprovação.")
    c.situacao, c.aprovada_por, c.aprovada_em = S.AGENDADA, usuario, timezone.now()
    c.revisao += 1
    c.proxima_tentativa_em = timezone.now()
    c.save()
    transaction.on_commit(_notificar_worker)
    return c


@transaction.atomic
def cancelar(usuario, pk: int, motivo: str = "") -> Comunicacao:
    c = _travar(usuario, pk)
    if c.situacao not in (S.AGUARDANDO_APROVACAO, S.AGENDADA, S.FALHOU, S.RECUSADA):
        raise ComunicacaoInvalida("Só dá para cancelar o que ainda não saiu.")
    c.situacao = S.CANCELADA
    c.revisao += 1
    c.motivo = (motivo or "Cancelada por uma pessoa.").strip()[:255]
    c.save()
    excecoes.encerrar_do_assunto(comunicacao=c, usuario=usuario,
                                 resolucao="Comunicação cancelada.")
    return c


@transaction.atomic
def tentar_de_novo(usuario, pk: int, *, confirmou_que_nao_chegou: bool = False
                   ) -> Comunicacao:
    """Decisão humana depois de falha ou resultado incerto. Para o incerto, a pessoa
    declara que conferiu com o destinatário que a mensagem NÃO chegou (senão, duplicaria)."""
    c = _travar(usuario, pk)
    if c.situacao not in (S.FALHOU, S.INCERTA, S.RECUSADA, S.EXPIRADA):
        raise ComunicacaoInvalida("Só dá para tentar de novo o que falhou ou não saiu.")
    if c.situacao == S.INCERTA and not confirmou_que_nao_chegou:
        raise ComunicacaoInvalida("Confirme com o destinatário que a mensagem NÃO chegou "
                                  "antes de tentar de novo (senão, ele recebe duas).")
    c.situacao, c.motivo = S.AGENDADA, f"Nova tentativa pedida por {usuario}."[:255]
    c.revisao += 1
    c.proxima_tentativa_em = timezone.now()
    if c.expira_em and c.expira_em <= timezone.now():
        c.expira_em = timezone.now() + timedelta(days=1)
    c.contato = contato_vigente(c.servidor_id, c.canal) or c.contato
    c.save()
    excecoes.encerrar_do_assunto(comunicacao=c, usuario=usuario,
                                 resolucao="Nova tentativa autorizada por uma pessoa.")
    transaction.on_commit(_notificar_worker)
    return c


@transaction.atomic
def confirmar_chegada(usuario, pk: int) -> Comunicacao:
    """Resultado incerto: a pessoa confirmou com o destinatário que a mensagem chegou."""
    c = _travar(usuario, pk)
    if c.situacao != S.INCERTA:
        raise ComunicacaoInvalida("Só se confirma a chegada de um resultado desconhecido.")
    c.situacao, c.motivo = S.ENVIADA, f"Chegada confirmada por {usuario}."[:255]
    c.enviada_em = c.enviada_em or timezone.now()
    c.save()
    excecoes.encerrar_do_assunto(comunicacao=c, usuario=usuario,
                                 resolucao="Chegada confirmada com o destinatário.")
    return c


@transaction.atomic
def registrar_envio_manual(usuario, pk: int) -> Comunicacao:
    """Contingência: a pessoa copiou o texto e mandou por fora; fica registrado como manual
    (não é trocado de canal em silêncio)."""
    c = _travar(usuario, pk)
    if c.situacao in (S.ENVIADA, S.MANUAL, S.RESERVADA):
        raise ComunicacaoInvalida("Esta comunicação já saiu ou está saindo.")
    c.situacao, c.origem_envio = S.MANUAL, "manual"
    c.revisao += 1
    c.motivo = f"Enviada à mão por {usuario}."[:255]
    c.enviada_em = timezone.now()
    c.save()
    excecoes.encerrar_do_assunto(comunicacao=c, usuario=usuario,
                                 resolucao="Enviada à mão (contingência).")
    return c


@transaction.atomic
def simular_proxima(usuario, pk: int, resultado: str) -> Comunicacao:
    """Simulador: a próxima ida ao canal simulado falha do jeito pedido (só no simulado)."""
    from gestao.integracoes.whatsapp import config as whatsapp

    c = _travar(usuario, pk)
    if whatsapp.carregar().real:
        raise ComunicacaoInvalida("O simulador não existe com a Cloud API ligada.")
    if resultado not in ("", "temporaria", "definitiva", "incerta"):
        raise ComunicacaoInvalida("Resultado simulado inválido.")
    c.simular = resultado
    c.save(update_fields=["simular", "atualizada_em"])
    return c
