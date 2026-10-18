"""Worker de envio: reserva com prazo (lease), revalidação, ida ao canal fora de transação e
registro idempotente do resultado.

Ciclo de uma comunicação (`processar_uma`):
1. `reservar()` — transação curta: pega a próxima agendada com `SKIP LOCKED`, revalida
   **tudo** (chaves, modo do fluxo, validade, assunto e versão, contato, opt-in, telefone do
   cadastro, lista de testadores, limite por hora, janela de 24 h/modelo) e só então grava a
   tentativa com chave única e passa a `reservada` com prazo. Qualquer recusa termina aqui,
   sem nenhuma chamada ao canal;
2. `enviar()` — sem transação aberta: uma chamada ao adaptador;
3. `registrar_resultado()` — transação curta e idempotente (repetir não duplica). Vale mesmo
   com as chaves desligadas: desligar impede efeitos novos, não apaga o que aconteceu.

Prazo vencido de uma reserva = não se sabe se saiu (o processo morreu no meio): vira
`incerta` e exceção — nunca reenvio automático.
"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from gestao.integracoes.whatsapp import config as whatsapp_config
from gestao.integracoes.whatsapp import erros as erros_canal
from gestao.integracoes.whatsapp import servico as whatsapp
from gestao.integracoes.whatsapp.porta import Envio, MensagemSaida, ModeloSaida

from . import chaves, dominio, excecoes, ganchos
from .models import (
    ChaveAutomacao,
    Comunicacao,
    ContatoVerificado,
    ConteudoComunicacao,
    DestinatarioAutorizado,
    ExcecaoAutomacao,
    StatusEntrega,
    TentativaEntrega,
)

log = logging.getLogger("gestao.automacao")
S = Comunicacao.Situacao
R = TentativaEntrega.Resultado
T = ExcecaoAutomacao.Tipo
PRAZO_DA_RESERVA = timedelta(minutes=2)
#: Os testes rodam dentro de uma transação; eles desligam esta trava (e um teste próprio
#: confere que ela existe). Em execução normal, nunca.
VERIFICAR_TRANSACAO = True


def retencao() -> timedelta:
    return timedelta(days=int(getattr(settings, "AUTOMACAO_RETENCAO_DIAS", 30)))


@dataclass(frozen=True)
class Reserva:
    comunicacao_id: int
    tentativa_id: int
    mensagem: MensagemSaida
    simular: str = ""


# ------------------------------------------------------------------ recusas
def _encerrar(c: Comunicacao, situacao: str, motivo: str, *, excecao: str = "",
              resumo: str = "") -> None:
    c.situacao, c.motivo = situacao, motivo[:255]
    c.reservada_ate = None
    c.save()
    if excecao:
        excecoes.abrir(excecao, f"{excecao}:com:{c.pk}", resumo or motivo, comunicacao=c,
                       unidade_id=c.unidade_id)


def _endereco_do_cadastro(c: Comunicacao) -> str:
    servidor = c.servidor if c.servidor_id else None
    return dominio.e164_do_brasil(getattr(servidor, "telefone", ""))


def _na_lista(endereco: str) -> bool:
    hoje = timezone.localdate()
    for d in DestinatarioAutorizado.objects.filter(endereco__in=dominio.variantes(endereco),
                                                   removido_em__isnull=True):
        if d.vigente(hoje):
            return True
    return False


def _fluxos_ligados(canal: str) -> set[str] | None:
    """None = geral ou canal desligado (não há o que reservar)."""
    estados = {c.nome: c for c in ChaveAutomacao.objects.filter(
        nome__in=[chaves.GERAL, chaves.nome_canal(canal)])}
    for nome in (chaves.GERAL, chaves.nome_canal(canal)):
        if getattr(estados.get(nome), "estado", "") != ChaveAutomacao.Estado.LIGADA:
            return None
    return {c.nome.removeprefix("fluxo:") for c in ChaveAutomacao.objects.filter(
        nome__startswith="fluxo:", estado=ChaveAutomacao.Estado.LIGADA)}


def _expirar_reservas(agora) -> int:
    """Reservas vencidas: o processo caiu no meio do envio. Resultado desconhecido."""
    total = 0
    vencidas = (Comunicacao.objects.select_for_update(skip_locked=True)
                .filter(situacao=S.RESERVADA, reservada_ate__lt=agora)[:20])
    for c in vencidas:
        TentativaEntrega.objects.filter(comunicacao=c, resultado=R.EM_CURSO).update(
            resultado=R.INCERTA, terminada_em=agora, codigo_erro="prazo",
            detalhe="O envio foi interrompido antes de registrar o resultado.")
        _encerrar(c, S.INCERTA, "O envio foi interrompido: não se sabe se a mensagem saiu.",
                  excecao=T.RESULTADO_INCERTO,
                  resumo=f"Comunicação #{c.pk}: o envio foi interrompido no meio. Confira "
                         "com o destinatário antes de tentar de novo.")
        total += 1
    return total


# ------------------------------------------------------------------ reserva
def reservar(canal: str = "whatsapp") -> Reserva | None:
    """A próxima comunicação que pode sair (as recusadas no caminho ficam registradas)."""
    for _ in range(50):
        tratou, reserva = _reservar_uma(canal)
        if reserva is not None or not tratou:
            return reserva
    return None


def transporte() -> str:
    """Quem leva as mensagens ao canal: o worker do PCPR (`interno`) ou o n8n pela API."""
    return "n8n" if getattr(settings, "AUTOMACAO_TRANSPORTE", "interno") == "n8n" else "interno"


@transaction.atomic
def _reservar_uma(canal: str = "whatsapp") -> tuple[bool, Reserva | None]:
    """(tratou alguma linha?, reserva pronta para enviar ou None)."""
    agora = timezone.now()
    _expirar_reservas(agora)
    if transporte() == "n8n":
        return False, None  # o n8n reserva pela API; aqui só se vencem os prazos
    ligados = _fluxos_ligados(canal)
    if not ligados:
        return False, None
    c = (Comunicacao.objects.select_for_update(skip_locked=True, of=("self",))
         .select_related("servidor", "contato")
         .filter(canal=canal, situacao=S.AGENDADA, proxima_tentativa_em__lte=agora,
                 fluxo__in=ligados)
         .order_by("proxima_tentativa_em", "id").first())
    if c is None:
        return False, None
    tratou, reserva, _ = _preparar(c, agora)
    return tratou, reserva


def _preparar(c: Comunicacao, agora, *, prazo: timedelta = PRAZO_DA_RESERVA,
              chave_execucao: str = "", token_hash: str = ""
              ) -> tuple[bool, Reserva | None, str]:
    """Revalida tudo e, se pode sair, grava a tentativa e reserva. Devolve (tratou, reserva,
    código da recusa no vocabulário do contrato). Chamar com a linha travada."""
    canal = c.canal
    configuracao = whatsapp_config.carregar()
    definicao = ganchos.tipo(c.tipo)
    if definicao is None:
        _encerrar(c, S.RECUSADA, "Tipo de comunicação desconhecido.",
                  excecao=T.FALHA_DEFINITIVA)
        return True, None, "regra_violada"
    if c.expira_em and c.expira_em <= agora:
        _encerrar(c, S.EXPIRADA, "Passou do prazo em que a mensagem fazia sentido.")
        return True, None, "obsoleta"
    modo = chaves.modo_do_fluxo(c.fluxo)
    if modo == ChaveAutomacao.Modo.ASSISTIDO and not c.aprovada_em:
        c.situacao, c.motivo = S.AGUARDANDO_APROVACAO, "O fluxo está no modo assistido."
        c.save()
        return True, None, "regra_violada"
    try:
        preparo = definicao.preparar({**(c.contexto or {}), "_comunicacao": c.pk})
    except Exception:
        log.exception("preparar() falhou para a comunicação %s", c.pk)
        _encerrar(c, S.RECUSADA, "Não foi possível reler o assunto da mensagem.",
                  excecao=T.FALHA_DEFINITIVA)
        return True, None, "regra_violada"
    if not preparo.valida:
        _encerrar(c, S.OBSOLETA, preparo.motivo or "O assunto mudou.")
        return True, None, "obsoleta"
    if c.versao and preparo.versao and preparo.versao != c.versao:
        _encerrar(c, S.OBSOLETA, "O assunto mudou depois do agendamento (outra versão).")
        return True, None, "obsoleta"
    _gravar_conteudo(c, preparo.texto, "", preparo.parametros, agora)
    if modo == ChaveAutomacao.Modo.SOMBRA:
        _encerrar(c, S.SOMBRA, "Fluxo em sombra: preparada e registrada, sem envio.")
        return True, None, "obsoleta"
    exige_optin = getattr(definicao, "exige_optin", True)
    contato = c.contato
    if contato is None or (contato.revogado_em and exige_optin):
        from .comunicacoes import contato_vigente

        contato = contato_vigente(c.servidor_id, canal)
    if contato is None:
        _encerrar(c, S.RECUSADA, "O servidor não tem WhatsApp verificado.",
                  excecao=T.CONTATO,
                  resumo=f"{c.servidor or 'Destinatário'} sem WhatsApp verificado: avise "
                         "por outro meio ou cadastre o contato.")
        return True, None, "regra_violada"
    if not contato.verificado_em or (exige_optin and not contato.ativo):
        _encerrar(c, S.RECUSADA, "Contato sem verificação ou sem opt-in vigente.",
                  excecao=T.CONTATO,
                  resumo=f"{c.servidor or 'Destinatário'}: contato sem verificação ou sem "
                         "opt-in; nada foi enviado.")
        return True, None, "regra_violada"
    if configuracao.real and ContatoVerificado.Metodo.SIMULADO in (
            contato.metodo, contato.optin_origem):
        _encerrar(c, S.RECUSADA, "Verificação ou opt-in feitos no simulador não valem no canal "
                  "real: confirme de novo com a pessoa.", excecao=T.CONTATO)
        return True, None, "regra_violada"
    if c.servidor_id and not dominio.mesmo_numero(contato.endereco, _endereco_do_cadastro(c)):
        _encerrar(c, S.RECUSADA, "O telefone do cadastro mudou: verifique o contato de novo.",
                  excecao=T.CONTATO)
        return True, None, "regra_violada"
    if configuracao.lista_fechada and not _na_lista(contato.endereco):
        _encerrar(c, S.RECUSADA, "Número fora da lista de testadores autorizados.",
                  excecao=T.CONTATO,
                  resumo=f"{c.servidor or 'Destinatário'}: número fora da lista de "
                         "testadores; nada foi enviado.")
        return True, None, "regra_violada"
    hora = agora - timedelta(hours=1)
    # Conta e cria a tentativa sob a mesma trava por canal (até o fim desta transação): duas
    # reservas simultâneas perto do limite não passam juntas.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [_trava(f"limite-hora:{canal}")])
    ultimas = TentativaEntrega.objects.filter(comunicacao__canal=canal, iniciada_em__gte=hora)
    if ultimas.count() >= configuracao.limite_por_hora:
        c.proxima_tentativa_em = agora + timedelta(minutes=5)
        c.motivo = "Limite de envios por hora atingido; nova tentativa em 5 minutos."
        c.save()
        return False, None, "ainda_nao_devida"
    modelo = None
    if not dominio.janela_aberta(contato.ultima_mensagem_em, agora):
        definido = configuracao.modelo_de(c.tipo)
        if definido is None and (configuracao.real or transporte() == "n8n"):
            _encerrar(c, S.FALHOU, "Fora da janela de 24 h e sem modelo aprovado configurado.",
                      excecao=T.FALHA_DEFINITIVA,
                      resumo=f"Comunicação #{c.pk}: fora da janela de 24 h e sem modelo "
                             "aprovado (WHATSAPP_MODELOS); nada foi enviado.")
            return True, None, "regra_violada"
        nome = definido.nome if definido else f"simulado_{c.tipo.replace('.', '_')}"
        idioma = definido.idioma if definido else "pt_BR"
        modelo = ModeloSaida(nome=nome, idioma=idioma, parametros=preparo.parametros)
        _gravar_conteudo(c, preparo.texto, f"{nome}:{idioma}", preparo.parametros, agora)
    texto, parametros = _com_link(preparo, c, contato, agora, revogar_anteriores=True)
    c.tentativas += 1
    chave = chave_execucao or (
        f"reserva:{c.pk}:v{c.versao or preparo.versao or '0'}:exec{c.tentativas}")
    adaptador = "n8n" if chave_execucao else ("cloud_api" if configuracao.real else "simulado")
    tentativa = TentativaEntrega.objects.create(
        comunicacao=c, numero=c.tentativas, iniciada_em=agora, reserva_token_hash=token_hash,
        chave=chave[:200], adaptador=adaptador)
    c.situacao, c.contato, c.reservada_ate = S.RESERVADA, contato, agora + prazo
    c.motivo = ""
    c.save()
    if modelo is not None:
        modelo = ModeloSaida(nome=modelo.nome, idioma=modelo.idioma, parametros=parametros)
    resposta = (c.em_resposta_a.mensagem_id
                if c.em_resposta_a_id and c.em_resposta_a is not None else "")
    mensagem = MensagemSaida(
        para=contato.endereco, texto=_rodape(texto, configuracao.remetente),
        referencia=f"com:{c.pk}:t{tentativa.numero}", modelo=modelo, responder_a=resposta,
        para_usuario=contato.usuario_canal)
    return True, Reserva(c.pk, tentativa.pk, mensagem, c.simular), ""


def _com_link(preparo, c: Comunicacao, contato, agora, *, revogar_anteriores: bool
              ) -> tuple[str, tuple[str, ...]]:
    """O texto e os parâmetros com o link pessoal, criado AGORA (depois de todas as
    recusas). Sem pedido de link, devolve como veio."""
    if preparo.link is None:
        return preparo.texto, tuple(preparo.parametros)
    from . import links

    pedido = preparo.link
    _, token = links.criar(
        escopo=pedido.escopo, recurso=pedido.recurso, servidor_id=pedido.servidor_id,
        validade=max(pedido.valido_ate - agora, timedelta(hours=1)), contato_id=contato.pk,
        comunicacao_id=c.pk, revogar_anteriores=revogar_anteriores)
    url = links.url_publica(token)
    return (preparo.texto.replace(ganchos.PLACEHOLDER_LINK, url),
            tuple(str(p).replace(ganchos.PLACEHOLDER_LINK, url) for p in preparo.parametros))


# ------------------------------------------------------------------ reserva pela API (n8n)
PRAZO_DA_RESERVA_N8N = timedelta(minutes=10)


@dataclass
class ResultadoReserva:
    reserva: Reserva | None = None
    token: str = ""
    recusa: str = ""
    motivo: str = ""
    estado_atual: str = ""
    disponivel_em: datetime | None = None


def _trava(texto: str) -> int:
    """Chave de advisory lock (bigint) estável para um texto."""
    return int.from_bytes(hashlib.sha256(texto.encode()).digest()[:8], "big", signed=True)


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


@transaction.atomic
def reservar_pela_api(pk: int, *, versao_esperada: int | None, execucao: str
                      ) -> ResultadoReserva:
    """`POST /comunicacoes/{id}/reservar`: as mesmas revalidações do worker interno, com os
    códigos de recusa do contrato. Duas reservas simultâneas: só uma ganha (a linha trava)."""
    agora = timezone.now()
    _expirar_reservas(agora)
    c = (Comunicacao.objects.select_for_update(of=("self",))
         .select_related("servidor", "contato").filter(pk=pk).first())
    if c is None:
        return ResultadoReserva(recusa="inexistente", motivo="Comunicação inexistente.")
    estado = c.situacao
    canal = ChaveAutomacao.objects.filter(nome=chaves.nome_canal(c.canal)).first()
    if canal is not None and canal.estado == ChaveAutomacao.Estado.BLOQUEADA:
        return ResultadoReserva(recusa="canal_bloqueado", estado_atual=estado,
                                motivo="O canal está bloqueado: nada sai até alguém olhar.")
    permissao = chaves.permissao_de_efeito(c.canal, c.fluxo)
    if not permissao.permitido:
        return ResultadoReserva(recusa="desligada", motivo=permissao.motivo, estado_atual=estado)
    if versao_esperada is not None and versao_esperada != c.revisao:
        return ResultadoReserva(recusa="conflito_de_versao", estado_atual=estado,
                                motivo=f"A comunicação está na versão {c.revisao}.")
    if estado in (S.CANCELADA, S.OBSOLETA, S.EXPIRADA, S.SOMBRA):
        return ResultadoReserva(recusa="obsoleta", estado_atual=estado,
                                motivo=c.motivo or "A comunicação não vale mais.")
    if estado != S.AGENDADA:
        return ResultadoReserva(recusa="ja_processada", estado_atual=estado,
                                motivo="A comunicação já foi reservada, enviada ou encerrada.")
    if c.proxima_tentativa_em > agora:
        return ResultadoReserva(recusa="ainda_nao_devida", estado_atual=estado,
                                disponivel_em=c.proxima_tentativa_em,
                                motivo="Ainda não é hora de enviar.")
    token = secrets.token_urlsafe(24)
    _, reserva, codigo = _preparar(c, agora, prazo=PRAZO_DA_RESERVA_N8N,
                                   chave_execucao=f"api:{execucao}", token_hash=_hash(token))
    if reserva is None:
        c.refresh_from_db()
        return ResultadoReserva(recusa=codigo or "regra_violada", estado_atual=c.situacao,
                                motivo=c.motivo or "A comunicação não pode sair agora.",
                                disponivel_em=c.proxima_tentativa_em
                                if codigo == "ainda_nao_devida" else None)
    return ResultadoReserva(reserva=reserva, token=token)


@transaction.atomic
def repetir_reserva(tentativa_id: int) -> ResultadoReserva:
    """Repetição da MESMA chave de reserva (o n8n não recebeu a resposta): a mesma
    tentativa, com token de reserva novo e a mensagem montada de novo. Nada de segredo fica
    guardado para a repetição (o link pessoal e o token só existem na resposta)."""
    agora = timezone.now()
    t = TentativaEntrega.objects.select_for_update().get(pk=tentativa_id)
    c = (Comunicacao.objects.select_for_update(of=("self",)).select_related("contato")
         .get(pk=t.comunicacao_id))
    if (t.resultado != R.EM_CURSO or c.situacao != S.RESERVADA or c.contato is None
            or not c.reservada_ate or c.reservada_ate <= agora):
        return ResultadoReserva(recusa="ja_processada", estado_atual=c.situacao,
                                motivo="A reserva desta chave já terminou.")
    definicao = ganchos.tipo(c.tipo)
    preparo = definicao.preparar({**(c.contexto or {}), "_comunicacao": c.pk}) \
        if definicao else None
    if preparo is None or not preparo.valida:
        return ResultadoReserva(recusa="obsoleta", estado_atual=c.situacao,
                                motivo="O assunto mudou desde a reserva.")
    configuracao = whatsapp_config.carregar()
    conteudo = ConteudoComunicacao.objects.filter(comunicacao=c).first()
    # Um link a mais para a mesma pessoa, sem revogar o da primeira resposta (que o n8n pode
    # ter usado); e o token da primeira reserva continua aceito no resultado.
    texto, parametros = _com_link(preparo, c, c.contato, agora, revogar_anteriores=False)
    modelo = None
    if conteudo and conteudo.modelo:
        nome, _, idioma = conteudo.modelo.partition(":")
        modelo = ModeloSaida(nome=nome, idioma=idioma or "pt_BR", parametros=parametros)
    token = secrets.token_urlsafe(24)
    t.reservas_anteriores = [*(t.reservas_anteriores or []), t.reserva_token_hash][-5:]
    t.reserva_token_hash = _hash(token)
    t.save(update_fields=["reserva_token_hash", "reservas_anteriores"])
    resposta = (c.em_resposta_a.mensagem_id
                if c.em_resposta_a_id and c.em_resposta_a is not None else "")
    mensagem = MensagemSaida(
        para=c.contato.endereco, texto=_rodape(texto, configuracao.remetente),
        referencia=f"com:{c.pk}:t{t.numero}", modelo=modelo, responder_a=resposta,
        para_usuario=c.contato.usuario_canal)
    return ResultadoReserva(reserva=Reserva(c.pk, t.pk, mensagem, c.simular), token=token)


def tentativa_da_reserva(pk: int, token: str) -> TentativaEntrega | None:
    if not token or len(token) > 100:
        return None
    h = _hash(token)
    return (TentativaEntrega.objects.filter(comunicacao_id=pk)
            .filter(Q(reserva_token_hash=h) | Q(reservas_anteriores__contains=[h]))
            .exclude(reserva_token_hash="").first())  # nosec B106 — vazio = sem reserva


def _rodape(texto: str, remetente: str) -> str:
    """Toda mensagem diz de onde vem e que é teste (regra de produto, ADR 0046)."""
    marca = f"— {remetente}"
    return texto if marca in texto else f"{texto}\n\n{marca}"


_LINK_PESSOAL = re.compile(r"/p/[A-Za-z0-9_-]{32,128}")


def sem_credencial(texto: str) -> str:
    """O link pessoal é credencial: a cópia guardada da mensagem nunca leva o token."""
    return _LINK_PESSOAL.sub("/p/[link-pessoal]", texto or "")


def _gravar_conteudo(c: Comunicacao, texto: str, modelo: str, parametros, agora) -> None:
    ConteudoComunicacao.objects.update_or_create(comunicacao=c, defaults={
        "texto": sem_credencial(texto)[:4096], "modelo": modelo,
        "parametros": [sem_credencial(str(p)) for p in (parametros or ())],
        "expira_em": agora + retencao()})


# ------------------------------------------------------------------ envio
def enviar(reserva: Reserva, porta=None) -> None:
    """A única chamada externa. Nunca dentro de transação."""
    from django.db import connection

    if VERIFICAR_TRANSACAO and connection.in_atomic_block:
        raise RuntimeError("O envio ao canal não pode acontecer com transação aberta.")
    porta = porta or whatsapp.adaptador()
    inicio = time.monotonic()
    envio: Envio | None = None
    erro: Exception | None = None
    try:
        envio = porta.enviar(reserva.mensagem, simular=reserva.simular)
    except erros_canal.ErroWhatsapp as e:
        erro = e
    except Exception as e:
        log.exception("Erro inesperado no envio da comunicação %s", reserva.comunicacao_id)
        erro = erros_canal.ResultadoIncerto("Erro inesperado durante o envio.", "interno")
        erro.__cause__ = e
    registrar_resultado(reserva.tentativa_id, envio=envio, erro=erro,
                        duracao_ms=int((time.monotonic() - inicio) * 1000),
                        origem=getattr(porta, "origem", ""))


@transaction.atomic
def registrar_resultado(tentativa_id: int, *, envio: Envio | None = None,
                        erro: Exception | None = None, duracao_ms: int | None = None,
                        origem: str = "") -> TentativaEntrega:
    t = TentativaEntrega.objects.select_for_update().get(pk=tentativa_id)
    if t.resultado and t.resultado != R.INCERTA:
        return t  # já registrado: repetir não muda nada
    c = Comunicacao.objects.select_for_update(of=("self",)).select_related("contato").get(
        pk=t.comunicacao_id)
    agora = timezone.now()
    t.terminada_em, t.duracao_ms = agora, duracao_ms
    cancelada = c.situacao == S.CANCELADA  # opt-out (ou cancelamento) com o envio já reservado
    if envio is not None:
        t.resultado = R.ACEITA
        t.save()
        mais_nova = (TentativaEntrega.objects.filter(comunicacao=c, numero__gt=t.numero,
                                                     resultado=R.ACEITA)
                     .exclude(pk=t.pk).exists())
        if mais_nova:
            # A pessoa já tinha tentado de novo e a nova saiu: a velha também saiu (resultado
            # tardio). Não troca o id do provedor da comunicação; avisa do provável duplicado.
            excecoes.abrir(T.RESULTADO_INCERTO, f"duplicado:{c.pk}:t{t.numero}",
                           f"Comunicação #{c.pk}: a tentativa {t.numero}, dada como incerta, "
                           "também saiu — a pessoa pode ter recebido a mensagem duas vezes.",
                           comunicacao=c)
            return t
        _aceita(c, envio, origem, agora)
        if cancelada:  # saiu mesmo assim: o registro diz a verdade e uma pessoa confere
            excecoes.abrir(T.CONTATO, f"depois-do-cancelamento:{c.pk}",
                           f"Comunicação #{c.pk} saiu depois de cancelada (o transporte já "
                           "tinha reservado o envio quando o contato saiu). Confira com a "
                           "pessoa e registre o pedido de desculpas se for o caso.",
                           comunicacao=c)
        return t
    codigo = getattr(erro, "codigo", "") or ""
    t.codigo_erro, t.detalhe = codigo[:40], sem_credencial(str(erro or ""))[:255]
    if erro is not None:
        erro.args = (sem_credencial(str(erro)),)
    if t.resultado == R.INCERTA:  # o prazo já tinha vencido e agora veio uma falha: fica
        t.save()
        return t
    if cancelada:  # não saiu e foi cancelada no meio: continua cancelada, nunca reagenda
        t.resultado = (R.INCERTA if not isinstance(
            erro, (erros_canal.FalhaTemporaria, erros_canal.FalhaDefinitiva,
                   erros_canal.CanalBloqueado)) else R.DEFINITIVA)
        t.save()
        if t.resultado == R.INCERTA:
            excecoes.abrir(T.RESULTADO_INCERTO, f"incerta-cancelada:{c.pk}",
                           f"Comunicação #{c.pk} foi cancelada com o envio em curso e não se "
                           "sabe se saiu. Confira com a pessoa; não reenvie.", comunicacao=c)
        return t
    if isinstance(erro, erros_canal.CanalBloqueado):
        t.resultado = R.DEFINITIVA
        t.save()
        chaves.bloquear_canal(c.canal, f"Bloqueado pelo erro {codigo} da Cloud API.")
        c.situacao, c.reservada_ate = S.AGENDADA, None  # não saiu: espera o desbloqueio
        c.motivo = "O canal foi bloqueado por um problema da conta; a mensagem não saiu."
        c.save()
        excecoes.abrir(T.CANAL, f"canal:{c.canal}:{codigo}",
                       f"Canal WhatsApp bloqueado (erro {codigo}): confira token, conta e "
                       "pagamento antes de religar.", comunicacao=c, unidade_id=None)
    elif isinstance(erro, erros_canal.FalhaTemporaria):
        t.resultado = R.TEMPORARIA
        t.save()
        if c.tentativas >= dominio.MAX_RODADAS:
            _encerrar(c, S.FALHOU, f"Falhou {c.tentativas} vezes: {erro}"[:255],
                      excecao=T.FALHA_DEFINITIVA)
        else:
            c.situacao, c.reservada_ate = S.AGENDADA, None
            c.proxima_tentativa_em = agora + dominio.espera(
                c.tentativas, getattr(erro, "espera_segundos", None))
            c.motivo = f"Falha temporária ({codigo}); nova tentativa agendada."[:255]
            c.save()
    elif isinstance(erro, erros_canal.FalhaDefinitiva):
        t.resultado = R.DEFINITIVA
        t.save()
        _encerrar(c, S.FALHOU, str(erro), excecao=T.FALHA_DEFINITIVA,
                  resumo=f"Comunicação #{c.pk} não saiu: {erro}")
    else:
        t.resultado = R.INCERTA
        t.save()
        _encerrar(c, S.INCERTA, "Não se sabe se a mensagem saiu.",
                  excecao=T.RESULTADO_INCERTO,
                  resumo=f"Comunicação #{c.pk}: não se sabe se saiu ({erro}). Confira com "
                         "o destinatário antes de tentar de novo.")
    c.simular = ""
    c.save(update_fields=["simular"])
    return t


def _aceita(c: Comunicacao, envio: Envio, origem: str, agora) -> None:
    era_incerta = c.situacao == S.INCERTA
    c.situacao, c.reservada_ate, c.motivo, c.simular = S.ENVIADA, None, "", ""
    c.mensagem_id, c.origem_envio = envio.mensagem_id, str(origem or envio.origem)
    c.enviada_em = c.enviada_em or agora
    if not c.entrega:
        c.entrega = Comunicacao.Entrega.ACEITA
    if c.aceita_resposta:
        definicao = ganchos.tipo(c.tipo)
        c.resposta_ate = agora + (definicao.janela_resposta if definicao else timedelta(days=15))
    c.save()
    if c.contato_id and (envio.wa_id or envio.usuario_id) and c.contato is not None:
        ContatoVerificado.objects.filter(pk=c.contato_id).update(
            wa_id=envio.wa_id or c.contato.wa_id,
            usuario_canal=envio.usuario_id or c.contato.usuario_canal)
    if era_incerta:
        excecoes.encerrar_do_assunto(comunicacao=c, resolucao="O resultado chegou: enviada.")
    # Status que chegaram antes de sabermos o id (corrida webhook × resposta do envio).
    from .entrada import aplicar_status

    for s in StatusEntrega.objects.filter(canal=c.canal, mensagem_id=envio.mensagem_id,
                                          comunicacao__isnull=True):
        s.comunicacao = c
        s.save(update_fields=["comunicacao"])
        aplicar_status(c, s)


def processar_uma(canal: str = "whatsapp", porta=None) -> bool:
    """Uma comunicação do começo ao fim. True se havia alguma para tratar."""
    from gestao.plataforma import auditoria

    try:
        with auditoria.contexto(None, None, "automacao:envio"):
            tratou, reserva = _reservar_uma(canal)
        if reserva is not None:
            enviar(reserva, porta)
        return tratou
    finally:
        auditoria.limpar_contexto()


def pendentes_agora(canal: str = "whatsapp") -> int:
    return Comunicacao.objects.filter(canal=canal, situacao=S.AGENDADA,
                                      proxima_tentativa_em__lte=timezone.now()).count()
