"""Arquivos recebidos: baixar (fora de transação), conferir e associar ao registro certo.

- Só se baixa arquivo de **remetente identificado**; o de número desconhecido fica em
  quarentena sem download.
- O arquivo é conferido pelo tamanho, pelos bytes (PDF/JPG/PNG de verdade) e pelo sha256
  informado pela Meta; o que não passa é recusado, e a pessoa recebe o motivo.
- Associar é efeito novo: só com a chave do fluxo `recebimento_automatico` ligada. Quem age
  é a pessoa que originou a comunicação respondida — as policies do contexto valem para ela
  (perdeu a permissão → exceção). Sem comunicação aberta, ou com o fluxo desligado, uma
  pessoa escolhe o destino na fila de exceções (e aí quem age é ela).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from gestao.integracoes.whatsapp import config as whatsapp_config
from gestao.integracoes.whatsapp import erros as erros_canal
from gestao.integracoes.whatsapp import servico as whatsapp
from gestao.integracoes.whatsapp.porta import Anexo
from gestao.plataforma import auditoria

from . import chaves, dominio, excecoes, ganchos, policies
from .models import CANAL_WHATSAPP, Comunicacao, ExcecaoAutomacao, Recebimento

log = logging.getLogger("gestao.automacao")
RS = Recebimento.Situacao
T = ExcecaoAutomacao.Tipo
FLUXO = "recebimento_automatico"
PRAZO = timedelta(minutes=5)
MAX_TENTATIVAS = 4
EXTENSOES = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}
TIPO_ANEXO: dict[str, str] = {Recebimento.Tipo.DOCUMENTO: "document",
                              Recebimento.Tipo.IMAGEM: "image"}


class RecebimentoInvalido(Exception):
    pass


# ------------------------------------------------------------------ download
@transaction.atomic
def reservar() -> int | None:
    agora = timezone.now()
    base = (Recebimento.objects.select_for_update(skip_locked=True)
            .filter(situacao=RS.IDENTIFICADO, arquivo="").exclude(midia_id="")
            .filter(Q(reservado_ate__isnull=True) | Q(reservado_ate__lt=agora)))
    for esgotado in base.filter(tentativas__gte=MAX_TENTATIVAS):
        esgotado.situacao, esgotado.reservado_ate = RS.RECUSADO, None
        esgotado.motivo = "Não foi possível baixar o arquivo da Meta."
        esgotado.save(update_fields=["situacao", "motivo", "reservado_ate"])
        excecoes.abrir(T.ARQUIVO_RECUSADO, f"arquivo:receb:{esgotado.pk}",
                       f"O arquivo de {esgotado.servidor or 'um contato'} não pôde ser baixado.",
                       recebimento=esgotado, unidade_id=esgotado.unidade_id)
    r = base.filter(tentativas__lt=MAX_TENTATIVAS).order_by("registrado_em", "id").first()
    if r is None:
        return None
    r.tentativas += 1
    r.reservado_ate = agora + PRAZO
    r.save(update_fields=["tentativas", "reservado_ate"])
    return r.pk


def baixar(pk: int, porta=None) -> Recebimento:
    from .entrega import VERIFICAR_TRANSACAO  # a mesma trava do envio

    if VERIFICAR_TRANSACAO and connection.in_atomic_block:
        raise RuntimeError("O download da mídia não pode acontecer com transação aberta.")
    r = Recebimento.objects.get(pk=pk)
    configuracao = whatsapp_config.carregar()
    porta = porta or whatsapp.adaptador(configuracao)
    anexo = Anexo(midia_id=r.midia_id, tipo=TIPO_ANEXO.get(r.tipo, "document"), mime=r.mime,
                  sha256=r.sha256)
    try:
        midia = porta.baixar_midia(anexo, configuracao.tamanho_maximo_midia)
    except erros_canal.MidiaInvalida as erro:
        _recusar(r.pk, str(erro))
        return Recebimento.objects.get(pk=pk)
    except erros_canal.ErroWhatsapp as erro:
        log.info("download da mídia do recebimento %s falhou (%s); o lease permite repetir",
                 pk, erro.codigo)
        Recebimento.objects.filter(pk=pk).update(reservado_ate=None, motivo=str(erro)[:255])
        return Recebimento.objects.get(pk=pk)
    with transaction.atomic():
        r = Recebimento.objects.select_for_update().get(pk=pk)
        if r.arquivo:
            return r  # outro worker já gravou
        extensao = EXTENSOES[midia.mime]
        r.arquivo.save(f"receb-{r.pk}{extensao}", ContentFile(midia.conteudo), save=False)
        r.mime, r.tamanho, r.sha256 = midia.mime, len(midia.conteudo), midia.sha256_hex
        r.nome_arquivo = f"recebido-{r.pk}{extensao}"
        r.reservado_ate, r.motivo = None, ""
        r.save()
        tentar_associar(r)
    return r


@transaction.atomic
def _recusar(pk: int, motivo: str) -> None:
    r = Recebimento.objects.select_for_update().get(pk=pk)
    r.situacao, r.motivo, r.reservado_ate = RS.RECUSADO, motivo[:255], None
    r.save(update_fields=["situacao", "motivo", "reservado_ate"])
    excecoes.abrir(T.ARQUIVO_RECUSADO, f"arquivo:receb:{r.pk}",
                   f"Arquivo de {r.servidor or 'um contato'} recusado: {motivo}",
                   recebimento=r, unidade_id=r.unidade_id)
    from .comunicacoes import agendar

    if r.contato_id:
        agendar(tipo="automacao.arquivo_recusado", servidor_id=r.servidor_id,
                recurso=f"automacao.recebimento:{r.pk}", chave=f"recusado:{r.pk}",
                unidade_id=r.unidade_id, contexto={"recebimento": r.pk}, em_resposta_a=r)


# ------------------------------------------------------------------ associação
def _comunicacao(r: Recebimento) -> Comunicacao | None:
    # A comunicação citada (resposta a uma mensagem nossa) vale só dentro do prazo de resposta
    # dela, contado da chegada do arquivo — como a busca abaixo. Fora do prazo, vai para uma
    # pessoa decidir o destino (nada entra sozinho num assunto velho).
    quando = r.recebido_em or timezone.now()
    citada = r.comunicacao if r.comunicacao_id else None
    if (citada is not None and citada.aceita_resposta and citada.resposta_ate
            and citada.resposta_ate > quando):
        return citada
    if citada is not None and citada.aceita_resposta:
        return None  # citou um pedido de arquivo vencido: uma pessoa decide
    if not r.contato_id:
        return None
    return (Comunicacao.objects.filter(contato_id=r.contato_id,
                                       situacao__in=(Comunicacao.Situacao.ENVIADA,
                                                     Comunicacao.Situacao.MANUAL))
            .exclude(aceita_resposta="").filter(resposta_ate__gt=quando)
            .order_by("-enviada_em", "-id").first())


def candidatos(r: Recebimento) -> list[tuple[ganchos.DestinoRecebimento, ganchos.Candidato]]:
    """Onde este arquivo poderia entrar, em todos os destinos registrados."""
    if not r.servidor_id:
        return []
    saida = []
    for d in ganchos.destinos():
        if r.mime and r.mime not in d.tipos_aceitos:
            continue
        saida += [(d, c) for c in d.candidatos(r.servidor_id)]
    return saida


def tentar_associar(r: Recebimento) -> bool:
    """Dentro da transação do download. True se associou."""
    c = _comunicacao(r)
    if c is None:
        _pedir_destino(r, "Arquivo sem comunicação aberta: escolha onde ele entra.")
        return False
    destino = ganchos.destino(c.aceita_resposta)
    if destino is None:
        _pedir_destino(r, "O destino desta resposta não está disponível.")
        return False
    permissao = chaves.permissao_de_efeito(CANAL_WHATSAPP, FLUXO)
    if not permissao.permitido:
        _pedir_destino(r, f"Associação automática desligada ({permissao.motivo}) — uma pessoa "
                          "confere e escolhe o destino.", comunicacao=c)
        return False
    autor = c.criada_por
    if autor is None or not autor.is_active:
        _pedir_destino(r, "Quem originou a comunicação não está mais ativo: uma pessoa "
                          "escolhe o destino.", tipo=T.PERMISSAO, comunicacao=c)
        return False
    if permissao.modo != "automatico":
        _pedir_destino(r, "O fluxo de recebimento está no modo assistido: confira e confirme "
                          "o destino.", comunicacao=c)
        return False
    return _associar(r, destino, c.recurso, dict(c.contexto or {}), autor, comunicacao=c)


def _pedir_destino(r: Recebimento, motivo: str, *, tipo: str = T.ASSOCIACAO,
                   comunicacao: Comunicacao | None = None) -> None:
    r.motivo = motivo[:255]
    if comunicacao is not None:
        r.comunicacao = comunicacao
        r.unidade_id = r.unidade_id or comunicacao.unidade_id
    r.save()
    excecoes.abrir(tipo, f"associacao:receb:{r.pk}",
                   f"Arquivo de {r.servidor or 'um contato'}: {motivo}", recebimento=r,
                   unidade_id=r.unidade_id)


def _associar(r: Recebimento, destino: ganchos.DestinoRecebimento, recurso: str, contexto: dict,
              usuario, *, comunicacao: Comunicacao | None = None) -> bool:
    if r.mime not in destino.tipos_aceitos:
        _pedir_destino(r, f"{destino.rotulo} não aceita este tipo de arquivo.")
        return False
    r.arquivo.open("rb")
    try:
        conteudo = r.arquivo.read()
    finally:
        r.arquivo.close()
    pedido = ganchos.PedidoDeAssociacao(usuario=usuario, recurso=recurso, contexto=contexto,
                                        nome=r.nome_arquivo, conteudo=conteudo, mime=r.mime,
                                        sha256=r.sha256)
    try:
        with transaction.atomic(), auditoria.contexto(usuario.pk, None, f"recebimento:{r.pk}"):
            referencia = destino.associar(pedido)
    except PermissionDenied:
        _pedir_destino(r, f"{usuario} não pode mais alterar este registro.", tipo=T.PERMISSAO,
                       comunicacao=comunicacao)
        return False
    except ganchos.ErroDeAssociacao as erro:
        _pedir_destino(r, str(erro), comunicacao=comunicacao)
        return False
    agora = timezone.now()
    r.situacao, r.destino, r.referencia = RS.ASSOCIADO, destino.chave, referencia[:80]
    r.associado_em, r.associado_por, r.motivo = agora, usuario, ""
    if comunicacao is not None:
        r.comunicacao = comunicacao
        r.unidade_id = r.unidade_id or comunicacao.unidade_id
    r.save()
    excecoes.encerrar_do_assunto(recebimento=r, usuario=usuario,
                                 resolucao=f"Associado: {destino.rotulo}.")
    from .comunicacoes import agendar

    agendar(tipo="automacao.confirmacao", servidor_id=r.servidor_id,
            recurso=f"automacao.recebimento:{r.pk}", chave=f"confirmacao:{r.pk}",
            unidade_id=r.unidade_id, contexto={"recebimento": r.pk}, em_resposta_a=r,
            criada_por=usuario)
    return True


# ------------------------------------------------------------------ ações humanas
def _travar(usuario, pk: int) -> Recebimento:
    r = Recebimento.objects.select_for_update(of=("self",)).select_related("servidor").get(pk=pk)
    policies.exigir(policies.pode_operar_objeto(usuario, r),
                    "Você não pode tratar este recebimento.")
    return r


@transaction.atomic
def associar_manual(usuario, pk: int, destino_chave: str, recurso: str) -> Recebimento:
    """Uma pessoa escolhe o destino entre os candidatos (quem age é ela)."""
    r = _travar(usuario, pk)
    if r.situacao not in (RS.IDENTIFICADO, RS.QUARENTENA) or not r.arquivo:
        raise RecebimentoInvalido("Este recebimento não tem arquivo à espera de destino.")
    escolhido = next(((d, c) for d, c in candidatos(r)
                      if d.chave == destino_chave and c.recurso == recurso), None)
    if escolhido is None:
        raise RecebimentoInvalido("Destino fora dos candidatos deste remetente.")
    d, c = escolhido
    if not _associar(r, d, c.recurso, dict(c.contexto), usuario, comunicacao=r.comunicacao):
        r.refresh_from_db()
        raise RecebimentoInvalido(r.motivo or "Não foi possível associar.")
    return r


@transaction.atomic
def conferir(usuario, pk: int) -> Recebimento:
    """Uma pessoa olhou o arquivo associado e confirma (≠ prestação finalizada)."""
    r = _travar(usuario, pk)
    if r.situacao != RS.ASSOCIADO:
        raise RecebimentoInvalido("Só se confere o que já foi associado.")
    r.situacao, r.conferido_em, r.conferido_por = RS.CONFERIDO, timezone.now(), usuario
    r.save(update_fields=["situacao", "conferido_em", "conferido_por"])
    return r


@transaction.atomic
def descartar(usuario, pk: int, motivo: str) -> Recebimento:
    r = _travar(usuario, pk)
    if r.situacao in (RS.ASSOCIADO, RS.CONFERIDO):
        raise RecebimentoInvalido("O arquivo já entrou no registro: remova por lá.")
    r.situacao, r.motivo = RS.DESCARTADO, (motivo or "Descartado por uma pessoa.")[:255]
    r.save(update_fields=["situacao", "motivo"])
    excecoes.encerrar_do_assunto(recebimento=r, usuario=usuario, resolucao="Descartado.")
    return r


def processar_um(porta=None) -> bool:
    try:
        with auditoria.contexto(None, None, "automacao:recebimento"):
            pk = reservar()
        if pk is None:
            return False
        try:
            with auditoria.contexto(None, None, f"automacao:recebimento:{pk}"):
                baixar(pk, porta)
        except Exception:
            log.exception("Falha ao baixar/associar o recebimento %s", pk)
        return True
    finally:
        auditoria.limpar_contexto()


# ------------------------------------------------------------------ entrada pela API (V1)
class ConflitoDeArquivo(Exception):
    """Mesma chave de recebimento com outro arquivo (o canal mudou o anexo)."""


def receber_arquivo(*, mensagem_id: str, indice: int, remetente: str, conteudo: bytes,
                    nome: str, recebido_em, em_resposta_a: str = "",
                    sha256_informado: str = "") -> tuple[Recebimento, bool]:
    """Variante V1: o n8n já baixou a mídia e a entrega aqui. O caminho depois é o mesmo da
    V2 — identificação, quarentena de desconhecido, conferência dos bytes, associação."""
    import hashlib

    from gestao.integracoes.whatsapp.adaptadores import _validar_midia
    from gestao.integracoes.whatsapp.porta import Anexo as AnexoCanal
    from gestao.integracoes.whatsapp.porta import MensagemRecebida

    from . import entrada as entrada_canal

    chave = dominio.chave_recebimento(CANAL_WHATSAPP, mensagem_id, indice)
    sha = hashlib.sha256(conteudo).hexdigest()
    existente = Recebimento.objects.filter(chave=chave).first()
    if existente is not None:
        if existente.sha256 and existente.sha256 != sha:
            raise ConflitoDeArquivo("Mesma mensagem e anexo com outro conteúdo.")
        return existente, False
    with transaction.atomic():
        m = MensagemRecebida(mensagem_id=mensagem_id, tipo="document", recebida_em=recebido_em,
                             remetente=dominio.somente_digitos(remetente),
                             em_resposta_a=em_resposta_a,
                             anexo=AnexoCanal(midia_id="api", tipo="document",
                                              sha256=sha256_informado, nome=nome))
        r = entrada_canal.registrar_mensagem(m, None, origem="api", indice=indice)
        if r is None:
            return Recebimento.objects.get(chave=chave), False
        if r.situacao != RS.IDENTIFICADO:
            return r, True  # quarentena: o arquivo de desconhecido nem é guardado
        configuracao = whatsapp_config.carregar()
        try:
            midia = _validar_midia(conteudo, configuracao.tamanho_maximo_midia, sha)
        except erros_canal.MidiaInvalida as erro:
            r.midia_id = ""
            r.save(update_fields=["midia_id"])
            motivo, pk = str(erro), r.pk
            transaction.on_commit(lambda: _recusar(pk, motivo))
            return r, True
        extensao = EXTENSOES[midia.mime]
        r.arquivo.save(f"receb-{r.pk}{extensao}", ContentFile(midia.conteudo), save=False)
        r.mime, r.tamanho, r.sha256 = midia.mime, len(midia.conteudo), midia.sha256_hex
        r.nome_arquivo = f"recebido-{r.pk}{extensao}"
        r.midia_id = ""
        r.save()
        # Sem a assinatura do provedor, o remetente é só o que o n8n disse: uma pessoa confere.
        _pedir_destino(r, "Arquivo entregue pela API (sem assinatura do provedor): confira o "
                          "remetente e escolha o destino.")
    return r, True


@transaction.atomic
def registrar_sem_arquivo(*, mensagem_id: str, indice: int, remetente: str, motivo: str,
                          recebido_em) -> Recebimento:
    """Anexo acima do limite, sem anexo ou não baixado: registra e orienta a pessoa."""
    from gestao.integracoes.whatsapp.porta import MensagemRecebida

    from . import entrada as entrada_canal

    chave = dominio.chave_recebimento(CANAL_WHATSAPP, mensagem_id, indice)
    existente = Recebimento.objects.filter(chave=chave).first()
    if existente is not None:
        return existente
    # Como documento (sem mídia: o worker não tenta baixar): "outro" abriria o encaminhamento
    # de tipo não tratado e mandaria uma 2ª resposta além da orientação do arquivo recusado.
    m = MensagemRecebida(mensagem_id=mensagem_id, tipo="document", recebida_em=recebido_em,
                         remetente=dominio.somente_digitos(remetente))
    r = entrada_canal.registrar_mensagem(m, None, origem="api", indice=indice) or \
        Recebimento.objects.get(chave=chave)
    textos = {"acima_do_limite": "Arquivo acima do limite de 10 MB.",
              "sem_anexo": "A mensagem chegou sem o anexo.",
              "nao_baixado": "Não foi possível baixar o anexo."}
    r.tipo, r.situacao, r.motivo = Recebimento.Tipo.DOCUMENTO, RS.RECUSADO, textos[motivo]
    r.save(update_fields=["tipo", "situacao", "motivo"])
    if r.contato_id:
        from .comunicacoes import agendar

        agendar(tipo="automacao.arquivo_recusado", servidor_id=r.servidor_id,
                recurso=f"automacao.recebimento:{r.pk}", chave=f"recusado:{r.pk}",
                unidade_id=r.unidade_id, contexto={"recebimento": r.pk}, em_resposta_a=r)
    return r
