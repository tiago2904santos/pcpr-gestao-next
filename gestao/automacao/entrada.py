"""Entrada pelo canal: webhook gravado antes do 200, status de entrega e mensagens recebidas.

1. `registrar_entrada(corpo)` — na requisição do webhook, só grava o corpo bruto
   (deduplicado pelo sha256; a Meta reentrega por até 7 dias) e devolve. Rápido.
2. `processar_entrada(pk)` — no worker, numa transação: lê o payload, aplica os status (sem
   regredir e reconciliando o "resultado desconhecido" pela referência que mandamos) e cria
   os recebimentos (um por mensagem, deduplicados), identificando o remetente.
3. `recebimentos.py` baixa a mídia (fora de transação) e associa ao registro certo.

Desligar as chaves não impede nada disto: são fatos que já aconteceram. Só os efeitos
novos (responder, associar automaticamente) consultam as chaves.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from gestao.integracoes.whatsapp import webhook
from gestao.integracoes.whatsapp.erros import BLOQUEIO_DE_CONTA, PayloadInvalido
from gestao.integracoes.whatsapp.porta import MensagemRecebida, StatusRecebido

from . import chaves, dominio, excecoes
from .models import (
    CANAL_WHATSAPP,
    Comunicacao,
    ContatoVerificado,
    ConteudoRecebimento,
    EntradaWebhook,
    EventoContato,
    ExcecaoAutomacao,
    Recebimento,
    StatusEntrega,
    registrar_evento_contato,
)

log = logging.getLogger("gestao.automacao")
S = Comunicacao.Situacao
T = ExcecaoAutomacao.Tipo
RS = Recebimento.Situacao
PRAZO_DA_ENTRADA = timedelta(minutes=5)
MAX_TENTATIVAS_ENTRADA = 5
TIPOS = {"text": Recebimento.Tipo.TEXTO, "document": Recebimento.Tipo.DOCUMENTO,
         "image": Recebimento.Tipo.IMAGEM, "interactive": Recebimento.Tipo.BOTAO,
         "button": Recebimento.Tipo.BOTAO}


def retencao() -> timedelta:
    return timedelta(days=int(getattr(settings, "AUTOMACAO_RETENCAO_DIAS", 30)))


def hash_do_remetente(endereco: str) -> str:
    """Identifica o mesmo remetente desconhecido sem guardar o número (com a SECRET_KEY)."""
    digitos = dominio.somente_digitos(endereco)
    return hashlib.sha256(f"{settings.SECRET_KEY}:remetente:{digitos}".encode()).hexdigest()


def _notificar_worker() -> None:
    with connection.cursor() as cur:
        cur.execute("NOTIFY automacao")


# ------------------------------------------------------------------ 1. gravar
@transaction.atomic
def registrar_entrada(corpo: bytes, origem: str = "meta",
                      canal: str = CANAL_WHATSAPP) -> tuple[EntradaWebhook, bool]:
    sha = hashlib.sha256(corpo).hexdigest()
    entrada, criada = EntradaWebhook.objects.get_or_create(
        canal=canal, sha256=sha, defaults={"corpo": corpo, "origem": origem[:12]})
    if criada:
        transaction.on_commit(_notificar_worker)
    return entrada, criada


# ------------------------------------------------------------------ 2. processar
@transaction.atomic
def reservar_entrada() -> int | None:
    agora = timezone.now()
    elegiveis = Q(situacao=EntradaWebhook.Situacao.PENDENTE) | Q(
        situacao=EntradaWebhook.Situacao.PROCESSANDO, iniciada_em__lt=agora - PRAZO_DA_ENTRADA)
    for esgotada in EntradaWebhook.objects.select_for_update(skip_locked=True).filter(
            elegiveis, tentativas__gte=MAX_TENTATIVAS_ENTRADA):
        esgotada.situacao = EntradaWebhook.Situacao.ERRO
        esgotada.erro = "O processamento foi interrompido várias vezes."
        esgotada.save(update_fields=["situacao", "erro"])
    entrada = (EntradaWebhook.objects.select_for_update(skip_locked=True)
               .filter(elegiveis, tentativas__lt=MAX_TENTATIVAS_ENTRADA)
               .order_by("recebida_em", "id").first())
    if entrada is None:
        return None
    entrada.situacao, entrada.iniciada_em = EntradaWebhook.Situacao.PROCESSANDO, agora
    entrada.tentativas += 1
    entrada.save(update_fields=["situacao", "iniciada_em", "tentativas"])
    return entrada.pk


def processar_entrada(pk: int) -> EntradaWebhook:
    entrada = EntradaWebhook.objects.get(pk=pk)
    from gestao.integracoes.whatsapp import config as whatsapp_config

    configuracao = whatsapp_config.carregar()
    esperado = configuracao.phone_number_id if (configuracao.real and
                                                entrada.origem == "meta") else ""
    try:
        lote = webhook.ler(bytes(entrada.corpo), numero_esperado=esperado)
    except PayloadInvalido as erro:
        entrada.situacao, entrada.erro = EntradaWebhook.Situacao.ERRO, str(erro)[:255]
        entrada.processada_em = timezone.now()
        entrada.save(update_fields=["situacao", "erro", "processada_em"])
        return entrada
    with transaction.atomic():
        for s in lote.status:
            registrar_status(s, entrada.canal)
        novos = [registrar_mensagem(m, entrada, origem=entrada.origem)
                 for m in lote.mensagens]
        for codigo in lote.erros:
            if codigo in BLOQUEIO_DE_CONTA:
                excecoes.abrir(T.CANAL, f"canal:{entrada.canal}:{codigo}",
                               f"A Meta avisou um problema da conta (erro {codigo}).")
        entrada.situacao = EntradaWebhook.Situacao.PROCESSADA
        entrada.processada_em = timezone.now()
        entrada.erro = ""
        entrada.resumo = (f"{len(lote.status)} status, {len(lote.mensagens)} mensagem(ns)"
                          + (f", {lote.ignorados} ignorado(s)" if lote.ignorados else ""))[:120]
        entrada.save()
    if any(r is not None and r.midia_id for r in novos):
        transaction.on_commit(_notificar_worker)
    return entrada


# ------------------------------------------------------------------ status
def _da_referencia(referencia: str) -> int | None:
    """`com:<id>:t<n>` (o biz_opaque_callback_data que mandamos) → id da comunicação."""
    partes = (referencia or "").split(":")
    if len(partes) == 3 and partes[0] == "com" and partes[1].isdigit():
        return int(partes[1])
    return None


def registrar_status(s: StatusRecebido, canal: str = CANAL_WHATSAPP) -> StatusEntrega | None:
    status = dominio.DA_META.get(s.status)
    if status is None:
        return None
    comunicacao = (Comunicacao.objects.select_for_update()
                   .filter(canal=canal, mensagem_id=s.mensagem_id).first())
    if comunicacao is None and (pk := _da_referencia(s.referencia)):
        comunicacao = Comunicacao.objects.select_for_update().filter(
            pk=pk, canal=canal).filter(Q(mensagem_id="") | Q(mensagem_id=s.mensagem_id)).first()
    preco = s.preco
    registro, criado = StatusEntrega.objects.get_or_create(
        canal=canal, mensagem_id=s.mensagem_id, status=status, defaults={
            "comunicacao": comunicacao, "ocorrido_em": s.ocorrido_em,
            "codigo_erro": s.erro_codigo[:40], "detalhe": s.erro_detalhe[:255],
            "categoria_preco": preco.categoria if preco else "",
            "tipo_preco": preco.tipo if preco else "",
            "cobravel": preco.cobravel if preco else None})
    if comunicacao is not None and (criado or registro.comunicacao_id is None):
        # Também o órfão que chegou antes do resultado e escapou da varredura de `_aceita`
        # (corrida): a reentrega da Meta, agora com a comunicação conhecida, religa e aplica.
        if not criado:
            registro.comunicacao = comunicacao
            registro.save(update_fields=["comunicacao"])
        aplicar_status(comunicacao, registro)
    return registro


def aplicar_status(c: Comunicacao, s: StatusEntrega) -> None:
    """O status muda a entrega sem regredir; `failed` depois de `entregue` não desfaz nada."""
    quando = s.ocorrido_em or timezone.now()
    if not c.mensagem_id and c.situacao in (S.INCERTA, S.RESERVADA, S.AGENDADA):
        # A Meta confirma pela nossa referência que a mensagem saiu: o desconhecido se
        # resolve sem ninguém reenviar.
        c.mensagem_id, c.situacao, c.reservada_ate = s.mensagem_id, S.ENVIADA, None
        c.enviada_em = c.enviada_em or quando
        c.motivo = "Envio confirmado pela Meta depois do resultado desconhecido."
        excecoes.encerrar_do_assunto(comunicacao=c, resolucao="A Meta confirmou o envio.")
    nova = dominio.proxima_entrega(c.entrega or "", s.status)
    if s.status == "entregue" and not c.entregue_em:
        c.entregue_em = quando
    if s.status == "lida":
        c.lida_em = c.lida_em or quando
        c.entregue_em = c.entregue_em or quando
    if nova == "falhou" and c.situacao == S.ENVIADA:
        c.situacao = S.FALHOU
        c.motivo = f"A entrega falhou (erro {s.codigo_erro or '?'})."[:255]
        excecoes.abrir(T.FALHA_DEFINITIVA, f"{T.FALHA_DEFINITIVA}:com:{c.pk}",
                       f"Comunicação #{c.pk}: a entrega falhou ({s.codigo_erro or 'sem código'}"
                       f"{': ' + s.detalhe if s.detalhe else ''}).", comunicacao=c,
                       unidade_id=c.unidade_id)
    elif nova in ("entregue", "lida") and c.situacao == S.FALHOU and c.mensagem_id:
        c.situacao, c.motivo = S.ENVIADA, ""
        excecoes.encerrar_do_assunto(comunicacao=c,
                                     resolucao="Chegou depois: a Meta confirmou a entrega.")
    c.entrega = nova
    c.save()


# ------------------------------------------------------------------ mensagens
def identificar(m: MensagemRecebida) -> ContatoVerificado | None:
    vigentes = ContatoVerificado.objects.select_for_update().filter(
        canal=CANAL_WHATSAPP, revogado_em__isnull=True).select_related("servidor")
    if m.remetente_usuario:
        contato = vigentes.filter(usuario_canal=m.remetente_usuario).first()
        if contato:
            return contato
    if m.remetente:
        formas = dominio.variantes(m.remetente)
        return vigentes.filter(Q(endereco__in=formas) | Q(wa_id__in=formas)).first()
    return None


def _comunicacao_respondida(m: MensagemRecebida, contato: ContatoVerificado | None):
    if m.em_resposta_a:
        c = Comunicacao.objects.filter(canal=CANAL_WHATSAPP, mensagem_id=m.em_resposta_a).first()
        if c and (contato is None or c.contato_id == contato.pk):
            return c
    if contato is None:
        return None
    return (Comunicacao.objects.filter(contato=contato, situacao__in=(S.ENVIADA, S.MANUAL))
            .exclude(aceita_resposta="").filter(resposta_ate__gt=timezone.now())
            .order_by("-enviada_em", "-id").first())


def registrar_mensagem(m: MensagemRecebida, entrada: EntradaWebhook | None = None, *,
                       origem: str = "meta", indice: int = 0) -> Recebimento | None:
    """`origem`: `meta` (webhook assinado — a mensagem prova o número), `simulador` (vale só
    para simulação: verificação e opt-in ficam marcados como simulados e não valem no canal
    real) ou `api` (o n8n diz quem mandou: nada é verificado nem associado sozinho)."""
    chave = dominio.chave_recebimento(CANAL_WHATSAPP, m.mensagem_id, indice)
    if Recebimento.objects.filter(chave=chave).exists():
        return None  # a Meta reentregou: já registrado
    agora = timezone.now()
    contato = identificar(m)
    respondida = _comunicacao_respondida(m, contato)
    tipo = TIPOS.get(m.tipo, Recebimento.Tipo.OUTRO)
    intencao = dominio.intencao(m.texto) if tipo in (Recebimento.Tipo.TEXTO,
                                                    Recebimento.Tipo.BOTAO) else ""
    endereco = m.remetente or m.remetente_usuario
    r = Recebimento.objects.create(
        canal=CANAL_WHATSAPP, mensagem_id=m.mensagem_id, indice=indice, chave=chave,
        entrada=entrada,
        remetente_hash=hash_do_remetente(endereco), remetente_final=dominio.somente_digitos(
            m.remetente)[-4:], contato=contato, servidor_id=getattr(contato, "servidor_id", None),
        unidade_id=(respondida.unidade_id if respondida else
                    getattr(getattr(contato, "servidor", None), "unidade_id", None)),
        comunicacao=respondida, tipo=tipo, intencao=intencao,
        midia_id=m.anexo.midia_id if m.anexo else "", mime=m.anexo.mime[:100] if m.anexo else "",
        sha256=(m.anexo.sha256 or "")[:64] if m.anexo else "",
        nome_arquivo="",  # o nome escolhido por quem mandou fica no conteúdo (retenção)
        em_resposta_a=m.em_resposta_a[:300], recebido_em=m.recebida_em or agora)
    ConteudoRecebimento.objects.create(recebimento=r, texto=m.texto[:4096],
                                       nome_perfil=m.nome_perfil[:120],
                                       nome_original=(m.anexo.nome if m.anexo else "")[:255],
                                       expira_em=agora + retencao())
    if contato is None:
        _quarentena(r, "Mensagem de um número sem contato verificado.")
        return r
    _atualizar_contato(contato, r, agora, origem)
    r.situacao, r.identificado_em = RS.IDENTIFICADO, agora
    r.save(update_fields=["situacao", "identificado_em"])
    if tipo in (Recebimento.Tipo.DOCUMENTO, Recebimento.Tipo.IMAGEM):
        return r  # o worker baixa e associa (recebimentos.py)
    if intencao and origem == "api":
        _encaminhar(r, "Palavra-chave recebida por um canal sem assinatura do provedor.")
    elif intencao:
        _atender_intencao(r, contato, intencao, simulado=origem == "simulador")
    elif tipo == Recebimento.Tipo.OUTRO:
        r.situacao, r.motivo = RS.ENCAMINHADO, "Tipo de mensagem que a automação não trata."
        r.save(update_fields=["situacao", "motivo"])
        _encaminhar(r, "Mensagem de um tipo que a automação não trata (áudio, vídeo…).")
    elif chaves.permissao_de_efeito(CANAL_WHATSAPP, "assistente_whatsapp").permitido:
        _atender_com_assistente(r, contato)
    else:
        r.situacao = RS.ENCAMINHADO
        r.save(update_fields=["situacao"])
        _encaminhar(r, f"{contato.servidor} mandou uma mensagem para a equipe.")
    return r


def _atender_com_assistente(r: Recebimento, contato: ContatoVerificado) -> None:
    """Dúvida em texto livre: o assistente determinístico responde (fluxo
    `assistente_whatsapp` ligado); sem resposta segura, a pessoa da equipe também recebe."""
    from .tipos import responder_com_assistente

    _, precisa_de_pessoa = responder_com_assistente(r)
    _responder(r, "automacao.assistente", f"assistente:{r.pk}")
    if precisa_de_pessoa:
        r.situacao = RS.ENCAMINHADO
        r.save(update_fields=["situacao"])
        excecoes.abrir(T.ATENDIMENTO, f"atendimento:receb:{r.pk}",
                       f"{contato.servidor} perguntou algo que o assistente não resolve.",
                       recebimento=r, unidade_id=r.unidade_id)
    else:
        r.situacao = RS.RESPONDIDO
        r.save(update_fields=["situacao"])


def _atualizar_contato(contato: ContatoVerificado, r: Recebimento, agora,
                       origem: str = "meta") -> None:
    campos = []
    quando = r.recebido_em or agora
    if not contato.ultima_mensagem_em or quando > contato.ultima_mensagem_em:
        contato.ultima_mensagem_em = quando
        campos.append("ultima_mensagem_em")
    if not contato.verificado_em and origem != "api":
        # A pessoa escreveu deste número: o número é dela (no simulador, só para simulação).
        contato.verificado_em = agora
        contato.metodo = (ContatoVerificado.Metodo.SIMULADO if origem == "simulador"
                          else ContatoVerificado.Metodo.MENSAGEM)
        campos += ["verificado_em", "metodo"]
    if campos:
        contato.save(update_fields=campos)
    if "verificado_em" in campos:
        registrar_evento_contato(EventoContato.Acao.VERIFICADO, contato=contato, origem=origem)


def _quarentena(r: Recebimento, motivo: str) -> None:
    r.situacao, r.motivo = RS.QUARENTENA, motivo[:255]
    r.save(update_fields=["situacao", "motivo"])
    dia = timezone.localdate().isoformat()
    excecoes.abrir(T.REMETENTE_DESCONHECIDO, f"desconhecido:{r.remetente_hash[:32]}:{dia}",
                   f"Mensagem de número desconhecido (final {r.remetente_final or '?'}). Nada "
                   "foi baixado nem respondido.", recebimento=r)


def _encaminhar(r: Recebimento, resumo: str) -> None:
    excecoes.abrir(T.ATENDIMENTO, f"atendimento:receb:{r.pk}", resumo, recebimento=r,
                   unidade_id=r.unidade_id)
    _responder(r, "automacao.encaminhada", f"ack:{r.contato_id}:{timezone.localdate()}")


def _responder(r: Recebimento, tipo: str, chave: str,
               contato: ContatoVerificado | None = None) -> Comunicacao | None:
    """Resposta automática à pessoa (só sai se as chaves e o fluxo permitirem — o worker
    revalida; aqui só agenda)."""
    from .comunicacoes import agendar

    if not r.contato_id:
        return None
    return agendar(tipo=tipo, servidor_id=r.servidor_id, recurso=f"automacao.recebimento:{r.pk}",
                   chave=chave, unidade_id=r.unidade_id, contexto={"recebimento": r.pk},
                   em_resposta_a=r, contato=contato)


def _atender_intencao(r: Recebimento, contato: ContatoVerificado, intencao: str, *,
                      simulado: bool = False) -> None:
    agora = timezone.now()
    if intencao == "sair":
        contato.revogado_em, contato.revogado_motivo = agora, "Pediu para sair pelo WhatsApp."
        contato.save(update_fields=["revogado_em", "revogado_motivo"])
        registrar_evento_contato(EventoContato.Acao.REVOGADO, contato=contato,
                                 origem="simulador" if simulado else "mensagem")
        from .contatos import cancelar_do_contato

        cancelar_do_contato(contato, "A pessoa pediu para não receber mais mensagens.")
        _responder(r, "automacao.descadastro", f"descadastro:{r.pk}", contato=contato)
    elif intencao == "aceito":
        if not contato.optin_em:
            contato.optin_em = agora
            contato.optin_origem = (ContatoVerificado.OrigemOptin.SIMULADO if simulado
                                    else ContatoVerificado.OrigemOptin.MENSAGEM)
            contato.optin_versao = getattr(settings, "AUTOMACAO_TERMO_VERSAO", "2026-10")
            contato.save(update_fields=["optin_em", "optin_origem", "optin_versao"])
            registrar_evento_contato(EventoContato.Acao.OPTIN, contato=contato,
                                     origem=contato.optin_origem)
        _responder(r, "automacao.boas_vindas",
                   f"boas_vindas:{contato.pk}:{contato.optin_em:%Y%m%d}")
    else:
        _responder(r, "automacao.ajuda", f"ajuda:{contato.pk}:{timezone.localdate()}")
    r.situacao = RS.RESPONDIDO
    r.save(update_fields=["situacao"])


def processar_uma_entrada() -> bool:
    from gestao.plataforma import auditoria

    try:
        with auditoria.contexto(None, None, "automacao:entrada"):
            pk = reservar_entrada()
            if pk is None:
                return False
            try:
                processar_entrada(pk)
            except Exception:
                log.exception("Falha ao processar a entrada de webhook %s", pk)
        return True
    finally:
        auditoria.limpar_contexto()


def efeito_permitido(fluxo: str) -> chaves.Permissao:
    return chaves.permissao_de_efeito(CANAL_WHATSAPP, fluxo)
