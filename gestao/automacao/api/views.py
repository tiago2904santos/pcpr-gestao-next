"""Rotas da API de automação v1 (contrato `docs/automacao/contratos/api-automacao.v1.yaml`).

O n8n (transporte) reserva comunicações, devolve resultados e status, entrega arquivos e
abre exceções; clientes de IA executam ferramentas com delegação; o token pessoal age como o
dono. Toda escrita passa pelos serviços da automação, com as mesmas regras da tela e do
worker interno — a API não tem atalho.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from gestao.integracoes.whatsapp import config as whatsapp_config
from gestao.integracoes.whatsapp import erros as erros_canal
from gestao.integracoes.whatsapp.porta import Envio, Origem, StatusRecebido
from gestao.plataforma import ambiente

from .. import (
    chaves,
    contrato,
    dominio,
    entrada,
    entrega,
    excecoes,
    ferramentas,
    ganchos,
    recebimentos,
)
from ..models import CANAL_WHATSAPP, ChaveAutomacao, Comunicacao, ExcecaoAutomacao, Recebimento
from ..models_api import CredencialIntegracao, RegistroIdempotencia
from . import delegacoes
from .base import EM_ANDAMENTO, Chamada, ErroApi, erro, mascarar, rota

S = Comunicacao.Situacao
ESTADOS: dict[str, str] = {
    S.AGUARDANDO_APROVACAO: "agendada", S.AGENDADA: "agendada", S.RESERVADA: "enviando",
    S.ENVIADA: "enviada", S.MANUAL: "feita_a_mao", S.FALHOU: "falhou",
    S.INCERTA: "desconhecido", S.RECUSADA: "sem_contato", S.CANCELADA: "cancelada",
    S.OBSOLETA: "cancelada", S.EXPIRADA: "cancelada", S.SOMBRA: "cancelada"}
AMBIENTES = {"production": "producao", "staging": "treinamento", "preview": "preview",
             "lab": "teste", "dev": "teste", "test": "teste"}


class RespostaReserva(JsonResponse):
    """JsonResponse que leva a marca guardada no registro de idempotência (lida em `base`)."""

    corpo_guardado: dict | None = None


def _tipo(c: Comunicacao) -> str:
    return contrato.tipo(c.tipo)


def _recusa_do_canal_de_entrada(canal: str) -> JsonResponse | None:
    """`/estado.canais_entrada`: bloqueado → 409 `canal_bloqueado` (permanente: vira exceção
    no n8n); desligado → 423 (temporário: o canal reentrega depois)."""
    chave = ChaveAutomacao.objects.filter(nome=chaves.nome_canal(canal)).first()
    estado = chave.estado if chave else ChaveAutomacao.Estado.DESLIGADA
    if estado == ChaveAutomacao.Estado.BLOQUEADA:
        return erro(409, "canal_bloqueado", "O canal de entrada está bloqueado: nada foi "
                    "registrado.")
    if estado != ChaveAutomacao.Estado.LIGADA:
        return erro(423, "desligada", "O canal de entrada está desligado: nada foi registrado; "
                    "reentregue depois.")
    return None


def _chave_do_recebimento(d: dict) -> str:
    """A chave de negócio do recebimento pedido (a que o contrato manda no cabeçalho)."""
    indice = str(d.get("anexo_indice") or "0")
    return dominio.chave_recebimento(str(d.get("canal") or ""),
                                     str(d.get("mensagem_id_canal") or ""),
                                     int(indice) if indice.isdigit() else -1)


def _identificacao_invalida(d: dict) -> JsonResponse | None:
    """`mensagem_id_canal` obrigatório (1 a 300) e `anexo_indice` inteiro ≥ 0 (contrato): sem
    isso, entradas malformadas dividiriam a mesma chave `receb:whatsapp::N` ou dariam 500 no
    banco (índice negativo) — e a retentativa do transporte repetiria o 500."""
    mensagem_id = str(d.get("mensagem_id_canal") or "").strip()
    if not 1 <= len(mensagem_id) <= 300:
        return erro(422, "entrada_invalida", "Informe mensagem_id_canal (1 a 300 caracteres).")
    indice = str(d.get("anexo_indice") if d.get("anexo_indice") is not None else "")
    if not indice.isdigit() or int(indice) > 999:
        return erro(422, "entrada_invalida", "anexo_indice é um inteiro de 0 a 999.")
    if _data(d.get("recebido_em")) is None:  # contrato: obrigatório (a hora real da chegada)
        return erro(422, "entrada_invalida", "recebido_em (data e hora ISO 8601) é obrigatório.")
    total = str(d.get("total_anexos") if d.get("total_anexos") is not None else "")
    if not total.isdigit() or not 1 <= int(total) <= 1000 or int(indice) >= int(total):
        return erro(422, "entrada_invalida",
                    "total_anexos é um inteiro ≥ 1 e anexo_indice fica entre 0 e total_anexos − 1.")
    return None


def _comunicacao(pk: int) -> Comunicacao:
    c = Comunicacao.objects.filter(pk=pk).first()
    if c is None:
        raise ErroApi(404, "entrada_invalida", "Comunicação inexistente.")
    return c


def _data(valor) -> datetime | None:
    if not valor:
        return None
    try:
        quando = parse_datetime(str(valor))
    except ValueError:
        quando = None
    if quando is None:
        raise ErroApi(422, "entrada_invalida", "Data em formato ISO 8601, por favor.")
    return quando if timezone.is_aware(quando) else timezone.make_aware(quando)


# ------------------------------------------------------------------ estado
@rota("estado:ler")
def estado(ch: Chamada) -> JsonResponse:
    nomes = {c.nome: c for c in chaves.ChaveAutomacao.objects.all()}
    geral = nomes.get(chaves.GERAL)
    canal = nomes.get(chaves.nome_canal("whatsapp"))
    situacao_canal = {"ligada": "ligado", "bloqueada": "bloqueado"}.get(
        getattr(canal, "estado", ""), "desligado")
    fluxos = {n.removeprefix("fluxo:"): c.estado == "ligada" for n, c in nomes.items()
              if n.startswith("fluxo:")}
    for chave, _ in ganchos.fluxos():
        fluxos.setdefault(chave, False)
    from gestao.integracoes.eprotocolo import config as eprotocolo

    ep = eprotocolo.carregar()
    return JsonResponse({
        "ligada": bool(geral and geral.estado == "ligada"),
        "motivo": getattr(geral, "motivo", "") or "",
        "ambiente": AMBIENTES.get(ambiente.atual(), "teste"),
        "fluxos": fluxos,
        "canais": {"portal": "ligado", "email": "desligado", "whatsapp": situacao_canal},
        "canais_entrada": {"email": "desligado", "whatsapp": situacao_canal},
        "autorizacoes": {n.removeprefix("fluxo:"): {"modo": c.modo} for n, c in nomes.items()
                         if n.startswith("fluxo:")},
        "integracoes": {
            "eprotocolo": {"ambiente": ep.ambiente if ep.real else "simulado",
                           "consulta": ep.real, "mutacoes_permitidas": []},
            "central_viagens": {"disponivel": False}},
    })


# ------------------------------------------------------------------ comunicações
@rota("comunicacoes:ler")
def por_mensagem(ch: Chamada) -> JsonResponse:
    mensagem_id = (ch.request.GET.get("provedor_mensagem_id") or "").strip()
    if not 1 <= len(mensagem_id) <= 300:
        return erro(422, "entrada_invalida", "Informe provedor_mensagem_id.")
    c = Comunicacao.objects.filter(canal=CANAL_WHATSAPP,
                                   mensagem_id=mensagem_id).first()
    return JsonResponse({"itens": [{"id": c.pk, "versao": c.revisao}] if c else []})


@rota("comunicacoes:ler")
def devidas(ch: Chamada) -> JsonResponse:
    try:
        limite = max(1, min(100, int(ch.request.GET.get("limite") or 50)))
    except ValueError:
        return erro(422, "entrada_invalida", "limite precisa ser um número de 1 a 100.")
    qs = Comunicacao.objects.filter(situacao=S.AGENDADA,
                                    proxima_tentativa_em__lte=timezone.now())
    tipos = ch.request.GET.getlist("tipo")
    if tipos:
        nossos = [k for k, v in contrato.TIPOS_CONTRATO.items() if v in tipos] + tipos
        qs = qs.filter(tipo__in=nossos)
    if fluxo := ch.request.GET.get("fluxo"):
        qs = qs.filter(fluxo=fluxo.replace("-", "_"))
    return JsonResponse({"itens": [
        {"id": c.pk, "tipo": _tipo(c), "fluxo": c.fluxo, "versao": c.revisao,
         "enviar_em": c.proxima_tentativa_em.isoformat(), "correlacao_id": f"com-{c.pk}"}
        for c in qs.order_by("proxima_tentativa_em", "id")[:limite]]})


@rota("comunicacoes:ler")
def situacao(ch: Chamada, pk: int) -> JsonResponse:
    c = _comunicacao(pk)
    ultima = c.tentativas_entrega.order_by("-numero").first()
    resultados = {"aceita": "enviada", "temporaria": "falha_temporaria",
                  "definitiva": "falha_definitiva", "incerta": "resultado_desconhecido"}
    return JsonResponse({
        "id": c.pk, "tipo": _tipo(c), "estado": ESTADOS.get(c.situacao, "agendada"),
        "versao": c.revisao, "enviada_em": c.enviada_em.isoformat() if c.enviada_em else None,
        "provedor_mensagem_id": c.mensagem_id or None,
        "resultado": resultados.get(getattr(ultima, "resultado", "")),
        "correlacao_id": f"com-{c.pk}"})


@rota("comunicacoes:reservar", metodo="POST", desligamento="recusa")
def reservar(ch: Chamada, pk: int) -> JsonResponse:
    esperada = ch.request.headers.get("X-PCPR-Versao-Esperada")
    if esperada is not None and not esperada.isdigit():
        return erro(422, "entrada_invalida", "X-PCPR-Versao-Esperada é um inteiro.")
    resultado = entrega.reservar_pela_api(
        pk, versao_esperada=int(esperada) if esperada else None,
        execucao=ch.request.headers.get("Idempotency-Key", ""))
    if resultado.recusa:
        extra = {"disponivel_em": resultado.disponivel_em.isoformat()} \
            if resultado.disponivel_em else {}
        status = 404 if resultado.recusa == "inexistente" else 409
        if resultado.recusa == "desligada":
            return erro(423, "desligada", resultado.motivo)
        return erro(status, resultado.recusa if status == 409 else "entrada_invalida",
                    resultado.motivo, estado_atual=resultado.estado_atual, **extra)
    return _resposta_da_reserva(resultado)


def _resposta_da_reserva(resultado: entrega.ResultadoReserva) -> JsonResponse:
    r = resultado.reserva
    if r is None:  # só se chega aqui sem recusa, e sem recusa a reserva sempre vem
        raise RuntimeError("Resultado de reserva sem reserva.")
    c = Comunicacao.objects.get(pk=r.comunicacao_id)
    if c.reservada_ate is None:  # a reserva acabou de gravar o prazo
        raise RuntimeError("Comunicação reservada sem prazo da reserva.")
    resposta = RespostaReserva({
        "id": c.pk, "tipo": _tipo(c), "versao": c.revisao, "correlacao_id": f"com-{c.pk}",
        "canal": c.canal, "destino": f"+{r.mensagem.para}",
        "mensagem": {"modelo": r.mensagem.modelo.nome if r.mensagem.modelo else "",
                     "texto": r.mensagem.texto,
                     "variaveis": {f"p{i + 1}": v for i, v in enumerate(
                         r.mensagem.modelo.parametros if r.mensagem.modelo else ())}},
        "conteudo_sensivel": "/p/" in r.mensagem.texto,
        "reserva": {"token": resultado.token, "expira_em": c.reservada_ate.isoformat()},
        "idempotencia_canal": r.mensagem.referencia,
        "responder_a": r.mensagem.responder_a or None,
    })
    # O registro de idempotência guarda só os ids: destino, texto (com o link pessoal) e o
    # token da reserva nunca ficam no banco. A repetição remonta a resposta (base.py).
    resposta.corpo_guardado = {"_repetir": "reserva", "tentativa": r.tentativa_id}
    return resposta


def repetir(corpo: dict) -> JsonResponse | None:
    """Chamado por `base` na repetição de uma chave cujo corpo guardado é só uma marca."""
    if corpo.get("_repetir") != "reserva":
        return None
    resultado = entrega.repetir_reserva(int(corpo["tentativa"]))
    if resultado.recusa == "desligada":
        return erro(423, "desligada", resultado.motivo)
    if resultado.recusa:
        return erro(409, resultado.recusa, resultado.motivo, estado_atual=resultado.estado_atual)
    return _resposta_da_reserva(resultado)


@rota("comunicacoes:resultado", metodo="POST", desligamento="aceita")
def resultado(ch: Chamada, pk: int) -> JsonResponse:
    d = ch.dados
    token, res = str(d.get("reserva_token") or ""), d.get("resultado")
    if res not in ("enviada", "falha_temporaria", "falha_definitiva", "resultado_desconhecido"):
        return erro(422, "entrada_invalida", "resultado inválido.")
    tentativa = entrega.tentativa_da_reserva(pk, token)
    if tentativa is None:
        return erro(409, "ja_processada", "Reserva de outra execução ou já encerrada.")
    detalhe = mascarar(d.get("erro") or "")
    envio: Envio | None = None
    erro_canal: erros_canal.ErroWhatsapp | None = None
    if res == "enviada":
        mensagem_id = str(d.get("provedor_mensagem_id") or "")
        if not 1 <= len(mensagem_id) <= 300:  # nunca cortar: dois ids longos virariam um só
            return erro(422, "entrada_invalida", "Informe provedor_mensagem_id (até 300).")
        # O registro grava origem="n8n" (abaixo); Envio.origem só conhece as origens da porta.
        provedor = str(d.get("provedor") or "")
        origem = (Origem(provedor) if provedor in {o.value for o in Origem}
                  else Origem.CLOUD_API)
        envio = Envio(mensagem_id=mensagem_id, origem=origem)
    elif res == "falha_temporaria":
        erro_canal = erros_canal.FalhaTemporaria(detalhe or "Falha temporária (n8n).", "n8n")
    elif res == "falha_definitiva":
        erro_canal = erros_canal.FalhaDefinitiva(detalhe or "Falha definitiva (n8n).", "n8n")
    else:
        erro_canal = erros_canal.ResultadoIncerto(detalhe or "Resultado desconhecido (n8n).",
                                                  "n8n")
    t = entrega.registrar_resultado(tentativa.pk, envio=envio, erro=erro_canal,
                                    origem="n8n")
    c = Comunicacao.objects.get(pk=pk)
    return JsonResponse({"id": c.pk, "estado": ESTADOS.get(c.situacao), "tentativa": t.numero})


@rota("comunicacoes:entrega", metodo="POST", desligamento="aceita",
      impressao_sem=("ocorrido_em",))
def entrega_status(ch: Chamada, pk: int) -> JsonResponse:
    d = ch.dados
    status_api: dict[Any, str] = {"entregue": "delivered", "lida": "read", "falhou": "failed"}
    status = status_api.get(d.get("status"))
    mensagem_id = str(d.get("provedor_mensagem_id") or "")
    if status is None or not 1 <= len(mensagem_id) <= 300:
        return erro(422, "entrada_invalida", "status (entregue|lida|falhou) e "
                    "provedor_mensagem_id (até 300) são obrigatórios.")
    ocorrido_em = _data(d.get("ocorrido_em"))
    if ocorrido_em is None:  # contrato: obrigatório; sem ele o status ganharia a hora errada
        return erro(422, "entrada_invalida", "ocorrido_em (data e hora ISO 8601) é obrigatório.")
    tentativa = d.get("tentativa")
    if tentativa is not None and not (isinstance(tentativa, int)
                                      and not isinstance(tentativa, bool) and tentativa >= 1):
        return erro(422, "entrada_invalida", "tentativa é um inteiro ≥ 1 (o t<n> do callback).")
    c = _comunicacao(pk)
    if c.mensagem_id and c.mensagem_id != mensagem_id:
        return erro(409, "conflito_de_versao", "Esta comunicação tem outro id no provedor.")
    with transaction.atomic():
        entrada.registrar_status(StatusRecebido(
            mensagem_id=mensagem_id, status=status, ocorrido_em=ocorrido_em,
            # A tentativa informada pelo n8n (o t<n> do callback) é conferida em
            # registrar_status: status de tentativa anterior não confirma a atual.
            referencia=f"com:{c.pk}:t{tentativa or c.tentativas}",
            erro_detalhe=mascarar(d.get("erro") or ""),
            erro_codigo="n8n" if status == "failed" else ""), c.canal)
    c.refresh_from_db()
    return JsonResponse({"id": c.pk, "entrega": c.entrega})


# ------------------------------------------------------------------ recebimentos
@rota("recebimentos:criar", metodo="POST", desligamento="recusa",
      reuso_pelo_servico=lambda d: _chave_do_recebimento(d))
def criar_recebimento(ch: Chamada) -> JsonResponse:
    """Variante V1 (o n8n baixou a mídia). A V2, preferida, é o webhook direto no PCPR."""
    d, arquivo = ch.dados, ch.request.FILES.get("arquivo")
    if d.get("canal") != "whatsapp":
        return erro(501, "integracao_inexistente", "Só o canal whatsapp está implementado.")
    if (recusa := _recusa_do_canal_de_entrada("whatsapp")) is not None:
        return recusa
    if arquivo is None:
        return erro(422, "entrada_invalida", "Envie o arquivo (ou use /recebimentos/sem-arquivo).")
    limite = whatsapp_config.carregar().tamanho_maximo_midia
    conteudo = arquivo.read(limite + 1)
    if len(conteudo) > limite:
        return erro(413, "entrada_invalida", "Arquivo acima do limite.")
    if (problema := _identificacao_invalida(d)) is not None:
        return problema
    sha = hashlib.sha256(conteudo).hexdigest()
    if (d.get("sha256") or "").lower() != sha:
        return erro(422, "entrada_invalida", "O SHA-256 informado não confere com o arquivo.")
    try:
        r, novo = recebimentos.receber_arquivo(
            mensagem_id=str(d.get("mensagem_id_canal") or "")[:300],
            indice=int(d.get("anexo_indice") or 0), remetente=str(d.get("remetente") or ""),
            conteudo=conteudo, nome=str(d.get("nome_arquivo") or arquivo.name or ""),
            recebido_em=_data(d.get("recebido_em")),
            em_resposta_a=str(d.get("em_resposta_a_mensagem_canal") or "")[:300],
            sha256_informado=sha)  # hex: o formato que o modelo compara
    except recebimentos.ConflitoDeArquivo as e:
        return erro(409, "conflito_de_versao", str(e))
    except ValueError:
        return erro(422, "entrada_invalida", "anexo_indice é um inteiro.")
    return JsonResponse(_recebimento(r, duplicado=not novo), status=202)


@rota("recebimentos:criar", metodo="POST", desligamento="recusa",
      reuso_pelo_servico=lambda d: _chave_do_recebimento(d))
def recebimento_sem_arquivo(ch: Chamada) -> JsonResponse:
    d = ch.dados
    if d.get("canal") != "whatsapp":
        return erro(501, "integracao_inexistente", "Só o canal whatsapp está implementado.")
    if (recusa := _recusa_do_canal_de_entrada("whatsapp")) is not None:
        return recusa
    motivo = d.get("motivo")
    if motivo not in ("acima_do_limite", "sem_anexo", "nao_baixado"):
        return erro(422, "entrada_invalida", "motivo inválido.")
    if (problema := _identificacao_invalida(d)) is not None:
        return problema
    indice = str(d.get("anexo_indice"))
    r = recebimentos.registrar_sem_arquivo(
        mensagem_id=str(d.get("mensagem_id_canal") or "")[:300],
        indice=int(indice), remetente=str(d.get("remetente") or ""),
        motivo=motivo, recebido_em=_data(d.get("recebido_em")))
    return JsonResponse(_recebimento(r), status=202)


ESTADOS_RECEB: dict[str, str] = {
    Recebimento.Situacao.RECEBIDO: "recebido", Recebimento.Situacao.IDENTIFICADO: "identificado",
    Recebimento.Situacao.ASSOCIADO: "associado", Recebimento.Situacao.CONFERIDO: "associado",
    Recebimento.Situacao.QUARENTENA: "quarentena_remetente",
    Recebimento.Situacao.RECUSADO: "rejeitado", Recebimento.Situacao.DESCARTADO: "descartado",
    Recebimento.Situacao.ENCAMINHADO: "revisao_necessaria",
    Recebimento.Situacao.RESPONDIDO: "identificado"}


def _recebimento(r: Recebimento, duplicado: bool = False) -> dict:
    return {"id": r.pk, "estado": "duplicado" if duplicado else ESTADOS_RECEB.get(
        r.situacao, "recebido"), "motivo_codigo": None,
        "assinatura": "nao_verificada", "destino": r.destino or ""}


@rota("recebimentos:ler")
def obter_recebimento(ch: Chamada, pk: int) -> JsonResponse:
    r = Recebimento.objects.filter(pk=pk).first()
    if r is None:
        return erro(404, "entrada_invalida", "Recebimento inexistente.")
    return JsonResponse(_recebimento(r))


@rota("entradas:criar", metodo="POST", desligamento="recusa")
def criar_entrada(ch: Chamada) -> JsonResponse:
    return erro(501, "integracao_inexistente", "A caixa de entrada de e-mail não faz parte do "
                "piloto WhatsApp (e-mail é opcional).")


@rota("assistente:mensagens", metodo="POST", desligamento="recusa")
def mensagem_assistente(ch: Chamada) -> JsonResponse:
    return erro(501, "integracao_inexistente", "O assistente por e-mail não faz parte do piloto; "
                "pelo WhatsApp ele responde direto, sem o n8n.")


# ------------------------------------------------------------------ exceções
MOTIVOS = {"canal_indisponivel": ExcecaoAutomacao.Tipo.CANAL,
           "resultado_desconhecido": ExcecaoAutomacao.Tipo.RESULTADO_INCERTO,
           "destinatario_sem_contato": ExcecaoAutomacao.Tipo.CONTATO,
           "contato_nao_verificado": ExcecaoAutomacao.Tipo.CONTATO,
           "limite_tentativas": ExcecaoAutomacao.Tipo.FALHA_DEFINITIVA,
           "arquivo_nao_baixado": ExcecaoAutomacao.Tipo.ARQUIVO_RECUSADO,
           "documento_nao_identificado": ExcecaoAutomacao.Tipo.ASSOCIACAO,
           "orcamento_atingido": ExcecaoAutomacao.Tipo.CANAL,
           "fila_parada": ExcecaoAutomacao.Tipo.CANAL, "outro": ExcecaoAutomacao.Tipo.ATENDIMENTO}


@rota("excecoes:criar", metodo="POST", desligamento="aceita")
def abrir_excecao(ch: Chamada) -> JsonResponse:
    d = ch.dados
    motivo = d.get("motivo")
    if motivo not in MOTIVOS or not d.get("fluxo") or not d.get("correlacao_id"):
        return erro(422, "entrada_invalida", "fluxo, correlacao_id e um motivo aceito são "
                    "obrigatórios.")
    bruto = d.get("recurso")
    recurso: dict = bruto if isinstance(bruto, dict) else {}
    recurso_id = recurso.get("id")
    if recurso and not isinstance(recurso_id, int):
        return erro(422, "entrada_invalida", "recurso.id é um inteiro.")
    comunicacao = recebimento = None
    # Com recurso, o id já é inteiro (acima); sem recurso, nenhum dos tipos casa.
    if recurso.get("tipo") == "comunicacao" and isinstance(recurso_id, int):
        comunicacao = Comunicacao.objects.filter(pk=recurso_id).first()
    elif recurso.get("tipo") == "recebimento" and isinstance(recurso_id, int):
        recebimento = Recebimento.objects.filter(pk=recurso_id).first()
    unidade = getattr(comunicacao or recebimento, "unidade_id", None)
    with transaction.atomic():
        e = excecoes.abrir(
            MOTIVOS[motivo], f"api:{d['fluxo']}:{d['correlacao_id']}:{motivo}"[:200],
            f"Automação externa ({mascarar(d['fluxo'], 40)}): {motivo.replace('_', ' ')}. "
            f"{mascarar(d.get('detalhe') or '', 180)}", comunicacao=comunicacao,
            recebimento=recebimento, unidade_id=unidade)
    return JsonResponse({"id": e.pk, "situacao": e.situacao}, status=201)


# ------------------------------------------------------------------ ferramentas
def _permitidas(c: CredencialIntegracao) -> list[ferramentas.Ferramenta]:
    if c.tipo == CredencialIntegracao.Tipo.PESSOAL:
        return ferramentas.todas()
    return [f for f in ferramentas.todas() if f.nome in (c.ferramentas or [])]


@rota("ferramentas:executar")
def listar_ferramentas(ch: Chamada) -> JsonResponse:
    return JsonResponse({"itens": [f.descrever() for f in _permitidas(ch.credencial)]})


@rota("ferramentas:executar", metodo="POST", desligamento="aceita")
def executar_ferramenta(ch: Chamada, nome: str) -> JsonResponse:
    c = ch.credencial
    f = ferramentas.obter(nome)
    if f is None or f not in _permitidas(c):
        return erro(403, "negado", "Ferramenta fora da lista desta credencial.")
    cabecalho = ch.request.headers.get("X-PCPR-Delegacao")
    delegacao = None
    if c.tipo == CredencialIntegracao.Tipo.PESSOAL:
        if cabecalho:
            return erro(403, "negado", "Token pessoal não aceita delegação.")
        usuario = c.usuario
    else:
        try:
            dados = ferramentas.validar(f, ch.dados)
        except ferramentas.FerramentaInvalida as e:
            return erro(422, "entrada_invalida", str(e))
        try:
            ferramentas.conferir_portao(f)  # 423 sem consumir a delegação de uso único
        except ferramentas.AutomacaoDesligada as e:
            return erro(423, "desligada", str(e))
        try:
            with transaction.atomic():
                delegacao = delegacoes.consumir(cabecalho, c, nome, f.recurso(dados))
        except delegacoes.DelegacaoNegada as e:
            return erro(403, "negado", str(e))
        usuario = delegacao.usuario
    chave = (ch.request.headers.get("Idempotency-Key") or "").strip()

    def guardar_resposta(r: ferramentas.Resultado) -> None:
        # Na transação do efeito: se o processo cair antes de responder, a repetição da chave
        # devolve esta resposta em vez de executar (ou pedir aprovação) de novo.
        corpo, status = _corpo_da_ferramenta(r)
        RegistroIdempotencia.objects.filter(credencial=c, chave=chave,
                                            status=EM_ANDAMENTO).update(status=status,
                                                                        corpo=corpo)

    try:
        r = ferramentas.executar(nome, ch.dados, usuario=usuario, credencial=c,
                                 delegacao=delegacao, origem="api", correlacao=ch.correlacao,
                                 ao_concluir=guardar_resposta if chave else None)
    except ferramentas.FerramentaInvalida as e:
        return erro(422, "entrada_invalida", str(e))
    except ferramentas.FerramentaRecusada as e:
        return erro(409, "regra_violada", str(e))
    except ferramentas.AutomacaoDesligada as e:
        return erro(423, "desligada", str(e))
    except PermissionDenied as e:
        return erro(403, "negado", str(e) or "Policy negada.")
    corpo, status = _corpo_da_ferramenta(r)
    return JsonResponse(corpo, status=status)


def _corpo_da_ferramenta(r: ferramentas.Resultado) -> tuple[dict, int]:
    if r.aprovacao is not None:
        return ({"codigo": "aprovacao_pendente", "pedido": r.aprovacao.pk,
                 "mensagem": "Ação irreversível: uma pessoa precisa aprovar na tela."}, 202)
    return ({"execucao": r.execucao.pk, "resultado": r.execucao.resultado,
             "saida": r.saida}, 200)
