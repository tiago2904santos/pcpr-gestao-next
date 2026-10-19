"""Serviços da assistência por IA: pedir, processar (worker), aceitar, descartar.

Regras que valem para todos os usos:
- **a IA só roda no worker** (`processar_ia`), fora da requisição web e fora de transação:
  reservar o orçamento e gravar o resultado são transações curtas; a chamada HTTP fica entre
  elas (`_fora_de_transacao` confere);
- **toda sugestão tem alternativa sem IA**: no modo REGRA, ou quando a IA falha, estoura o
  orçamento, está desligada ou devolve algo que o validador reprova, vale o determinístico do
  uso — e a sugestão diz que caiu nele e por quê;
- **minimização**: só os fatos de `campos_permitidos` saem; texto livre vai mascarado;
- **nada se aplica sem a pessoa**: aceitar é um POST com sessão e política; a versão da fonte
  é conferida de novo, com o registro travado; texto escrito por pessoa só é substituído com
  confirmação explícita; fonte mudou → a sugestão fica obsoleta e não se aplica.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import re
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from gestao.integracoes.ia import esquema as esq
from gestao.integracoes.ia import servico as servico_ia
from gestao.integracoes.ia.porta import BlocoDeDados, PedidoIA, PortaIA
from gestao.integracoes.ia.protecao import dados_pessoais_em, mascarar

from . import configuracao, ganchos, orcamento, policies
from .dominio.textos import INSTRUCOES_COMUNS, codigos, serializar_fatos
from .models import (
    ConfiguracaoUso,
    ConteudoPedido,
    ConteudoSugestao,
    PedidoSugestao,
    Sugestao,
)

log = logging.getLogger("gestao.assistencia")

LEASE = timedelta(minutes=2)
MAX_TENTATIVAS_PEDIDO = 3
E = PedidoSugestao.Estado
S = Sugestao.Estado


class PedidoRecusado(Exception):
    """Uso desligado, limite do dia… — mensagem para a pessoa, dizendo como seguir."""


class ForaDeTransacao(RuntimeError):
    """A chamada à IA não pode acontecer dentro de uma transação aberta por este código."""


def retencao() -> timedelta:
    return timedelta(days=int(getattr(settings, "ASSISTENCIA_RETENCAO_DIAS", 30)))


def _uso(chave: str) -> ganchos.UsoIA:
    uso = ganchos.uso(chave)
    if uso is None:
        raise ganchos.RecursoInexistente(chave)
    return uso


def _inicio_do_dia(agora: datetime | None = None) -> datetime:
    local = timezone.localtime(agora or timezone.now())
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def opcoes_limpas(uso: ganchos.UsoIA, opcoes: dict | None) -> dict[str, str]:
    """Só os campos declarados pelo uso, com tamanho limitado e mascarados (CPF, telefone,
    e-mail, link) — antes de qualquer gravação."""
    bruto = opcoes or {}
    limpo = {}
    for o in uso.opcoes:
        linhas = [" ".join(x.split()) for x in str(bruto.get(o.nome) or "").splitlines()]
        valor = "\n".join(x for x in linhas if x)[: o.max_caracteres]
        if o.obrigatorio and not valor:
            raise PedidoRecusado(f"Preencha “{o.rotulo}”.")
        if valor:
            limpo[o.nome] = mascarar(valor)
    return limpo


# ------------------------------------------------------------------ pedir
def _trava(texto: str) -> int:
    """Chave de advisory lock (bigint) estável para um texto."""
    return int.from_bytes(hashlib.sha256(texto.encode()).digest()[:8], "big", signed=True)


def pedir(usuario, uso_chave: str, recurso_id: str, opcoes: dict | None = None
          ) -> PedidoSugestao:
    """Cria o pedido (ou devolve o que já está na fila para a mesma versão). No modo REGRA a
    sugestão sai na hora (é local, sem IA); no modo IA vai para o worker."""
    uso = _uso(uso_chave)
    recurso_id = str(recurso_id)
    policies.exigir(policies.pode_pedir(usuario, uso, recurso_id),
                    "Você não pode pedir sugestões para este registro.")
    config = configuracao.de(uso.chave)
    if not config.ligado:
        raise PedidoRecusado("Este uso está desligado. Escreva o texto à mão ou use os "
                             "textos prontos; quem administra liga em Assistência › Usos.")
    opcoes = opcoes_limpas(uso, opcoes)
    ctx = uso.montar(usuario, recurso_id, opcoes)  # leitura com a política de quem pede
    base = hashlib.sha256(json.dumps(
        [uso.chave, recurso_id, ctx.versao, uso.versao_prompt, config.modo, opcoes],
        ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    with transaction.atomic():
        # A trava (pessoa + uso) vem ANTES de procurar pedidos iguais: dois pedidos idênticos
        # simultâneos não acham, os dois, a fila vazia (o 2º daria IntegrityError na chave). Ela
        # também serializa a cota por pessoa e dia, contada e incrementada abaixo.
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)",
                           [_trava(f"ia-cota:{usuario.pk}:{uso.chave}")])
        anteriores = list(PedidoSugestao.objects.select_for_update()
                          .filter(chave__startswith=base).order_by("-id"))
        for p in anteriores:
            if p.estado in (E.PENDENTE, E.PROCESSANDO):
                return p
            if (p.estado == E.CONCLUIDO
                    and Sugestao.objects.filter(pedido=p, estado=S.PRONTA).exists()):
                return p
        hoje = PedidoSugestao.objects.filter(uso=uso.chave, usuario=usuario,
                                             criado_em__gte=_inicio_do_dia()).count()
        if hoje >= config.max_pedidos_pessoa_dia:
            raise PedidoRecusado(f"Você já fez {hoje} pedidos deste tipo hoje (limite do uso). "
                                 "Siga com o texto à mão; o limite volta amanhã.")
        pedido = PedidoSugestao.objects.create(
            uso=uso.chave, recurso_id=recurso_id, usuario=usuario, modo=config.modo,
            versao_fonte=ctx.versao, versao_prompt=uso.versao_prompt,
            chave=f"{base}:{len(anteriores)}")
        ConteudoPedido.objects.create(pedido=pedido, opcoes=opcoes,
                                      expira_em=timezone.now() + retencao())
        if config.modo == ConfiguracaoUso.Modo.REGRA:
            pedido.estado = E.PROCESSANDO
            _registrar(pedido, uso, ctx, uso.deterministico(ctx), origem=Sugestao.Origem.REGRA)
        else:
            transaction.on_commit(_avisar_worker)
    return pedido


def _avisar_worker() -> None:
    try:
        with connection.cursor() as cur:
            cur.execute("NOTIFY assistencia")
    except Exception:  # o worker também varre a fila sozinho
        log.warning("NOTIFY assistencia falhou", exc_info=True)


# ------------------------------------------------------------------ worker
def reservar_proximo(agora: datetime | None = None) -> int | None:
    """Transação curta: pega o próximo pedido (skip_locked) e marca o prazo (lease)."""
    agora = agora or timezone.now()
    with transaction.atomic():
        while True:
            pedido = (PedidoSugestao.objects.select_for_update(skip_locked=True)
                      .filter(Q(estado=E.PENDENTE)
                              | Q(estado=E.PROCESSANDO, reservado_ate__lt=agora))
                      .order_by("criado_em", "id").first())
            if pedido is None:
                return None
            if pedido.estado != E.PROCESSANDO or not (pedido.reserva_usd
                                                      or pedido.tentativas_admitidas):
                break
            # Lease vencido COM chamada admitida: o worker morreu e a chamada pode ter sido
            # feita (e cobrada). Não refaz às cegas: a reserva vira gasto, as vagas do dia
            # continuam contadas e o pedido encerra (quem pediu pede de novo).
            orcamento.cobrar_reserva_presa(pedido)
            pedido.chamadas_sem_registro += pedido.tentativas_admitidas
            pedido.tentativas_admitidas = 0
            pedido.estado, pedido.reservado_ate = E.FALHOU, None
            pedido.motivo = "chamada_incerta"
            pedido.save(update_fields=["estado", "reservado_ate", "motivo",
                                       "chamadas_sem_registro", "tentativas_admitidas",
                                       "atualizado_em"])
        pedido.estado = E.PROCESSANDO
        pedido.tentativas += 1
        pedido.reservado_ate = agora + LEASE
        pedido.save(update_fields=["estado", "tentativas", "reservado_ate", "atualizado_em"])
        return pedido.pk


def _fora_de_transacao(profundidade: int) -> None:
    if len(connection.atomic_blocks) > profundidade:
        raise ForaDeTransacao("Chamada à IA dentro de transação: não pode.")


CONECTIVOS = {"da", "de", "do", "das", "dos", "e"}


def _sem_nomes(texto: str, nomes) -> str:
    """Tira os nomes conhecidos da equipe ANTES de mandar ao provedor (o validador da saída é
    a 2ª barreira, não a 1ª): o nome inteiro e cada parte de 4+ letras viram "[pessoa]"."""
    partes: set[str] = set()
    for nome in nomes or ():
        nome = " ".join(str(nome or "").split())
        if not nome:
            continue
        partes.add(nome)
        partes.update(p for p in nome.split() if len(p) >= 4 and p.lower() not in CONECTIVOS)
    for parte in sorted(partes, key=len, reverse=True):  # o nome inteiro antes das partes
        texto = re.sub(rf"(?<!\w){re.escape(parte)}(?!\w)", "[pessoa]", texto,
                       flags=re.IGNORECASE)
    return texto


def _pedido_ia(uso: ganchos.UsoIA, ctx: ganchos.Contexto, deterministico: dict,
               config: ConfiguracaoUso, simular: str = "") -> PedidoIA:
    nomes = ctx.extras.get("nomes", ())

    def limpo(texto: str) -> str:  # valores E rótulos/origens dos blocos (ex.: título livre)
        return mascarar(_sem_nomes(texto, nomes))

    # Todo valor vai pela mesma barreira (nomes + CPF/telefone/e-mail/URL/CNPJ): fatos de
    # campos editáveis (ex.: o título da viagem) podem trazer um identificador. O validador
    # compara a saída com o contexto original; um valor mascarado só pode levar ao
    # determinístico, nunca deixar passar o identificador.
    fatos = [dataclasses.replace(f, valor=limpo(f.valor)) for f in ctx.fatos]
    blocos = [BlocoDeDados("fatos", serializar_fatos(f for f in fatos if not f.do_pedido),
                           limpo(ctx.recurso_rotulo))]
    for f in fatos:
        if f.do_pedido:
            blocos.append(BlocoDeDados(f.chave, f.valor, limpo(f.rotulo)))
    blocos.append(BlocoDeDados("lacunas_permitidas", ", ".join(uso.lacunas_conhecidas) or "—",
                               "lista fechada"))
    return PedidoIA(uso=uso.chave, instrucoes=INSTRUCOES_COMUNS + "\n\n" + uso.instrucoes,
                    versao_prompt=uso.versao_prompt, dados=tuple(blocos), esquema=uso.esquema,
                    max_tokens_saida=config.max_tokens_saida,
                    tempo_limite_s=float(config.tempo_limite_s),
                    contem_documento=ctx.contem_documento or uso.envolve_documento,
                    resposta_simulada=deterministico, simular=simular)


def conferir_minimizacao(uso: ganchos.UsoIA, ctx: ganchos.Contexto) -> None:
    fora = [f.chave for f in ctx.fatos if f.chave not in uso.campos_permitidos]
    if fora:
        raise ValueError(f"Fatos fora dos campos permitidos de {uso.chave}: {fora}")


def _sem_dado_pessoal(dados: Any) -> list[str]:
    erros: list[str] = []

    def varrer(v):
        if isinstance(v, str):
            erros.extend(f"dado_pessoal:{a}" for a in dados_pessoais_em(v))
        elif isinstance(v, dict):
            for x in v.values():
                varrer(x)
        elif isinstance(v, list):
            for x in v:
                varrer(x)

    varrer(dados)
    return erros


def _admitir(pedido: PedidoSugestao, uso: str, config) -> int:
    """Quantas tentativas este pedido pode fazer, sob trava por uso: o teto diário menos as
    chamadas já feitas hoje e as vagas tomadas por pedidos AINDA em voo (lease vivo). As vagas
    ficam anotadas no pedido até ele concluir ou ser encerrado. Cada tentativa é uma chamada."""
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [_trava(f"ia-dia:{uso}")])
        em_voo = (PedidoSugestao.objects
                  .filter(uso=uso, estado=E.PROCESSANDO, tentativas_admitidas__gt=0,
                          reservado_ate__gt=timezone.now())
                  .exclude(pk=pedido.pk)
                  .aggregate(n=Sum("tentativas_admitidas"))["n"] or 0)
        restantes = config.max_chamadas_dia - chamadas_hoje(uso) - em_voo
        tentativas = max(0, min(config.max_tentativas, restantes))
        PedidoSugestao.objects.filter(pk=pedido.pk).update(tentativas_admitidas=tentativas)
    return tentativas


def chamadas_hoje(uso: str) -> int:
    """Chamadas de hoje: as das sugestões e as que podem ter sido feitas sem registro (worker
    que morreu no meio da chamada)."""
    feitas = (Sugestao.objects.filter(uso=uso, criada_em__gte=_inicio_do_dia())
              .aggregate(n=Sum("tentativas_ia"))["n"] or 0)
    perdidas = (PedidoSugestao.objects.filter(uso=uso, atualizado_em__gte=_inicio_do_dia())
                .aggregate(n=Sum("chamadas_sem_registro"))["n"] or 0)
    return feitas + perdidas


def chamadas_hoje_por_uso() -> dict[str, int]:
    """As chamadas de IA de hoje de todos os usos (tela de usos), contadas como em
    `chamadas_hoje`: as das sugestões e as que podem ter sido feitas sem registro."""
    totais: dict[str, int] = {}
    for consulta in (Sugestao.objects.filter(criada_em__gte=_inicio_do_dia())
                     .values("uso").annotate(n=Sum("tentativas_ia")),
                     PedidoSugestao.objects.filter(atualizado_em__gte=_inicio_do_dia(),
                                                   chamadas_sem_registro__gt=0)
                     .values("uso").annotate(n=Sum("chamadas_sem_registro"))):
        for linha in consulta:
            totais[linha["uso"]] = totais.get(linha["uso"], 0) + (linha["n"] or 0)
    return totais


def processar(pk: int, porta: PortaIA | None = None, *, simular: str = "") -> Sugestao | None:
    """Um pedido reservado: monta o contexto (leitura), reserva o orçamento, chama a porta
    FORA de transação, valida e grava. Qualquer falha cai no determinístico."""
    profundidade = len(connection.atomic_blocks)
    pedido = PedidoSugestao.objects.select_related("usuario").filter(pk=pk).first()
    if pedido is None or pedido.estado != E.PROCESSANDO:
        return None
    uso = ganchos.uso(pedido.uso)
    if uso is None:
        _encerrar(pedido, E.CANCELADO, "uso_desconhecido")
        return None
    conteudo = ConteudoPedido.objects.filter(pedido=pedido).first()
    opcoes = conteudo.opcoes if conteudo else {}
    try:
        ctx = uso.montar(pedido.usuario, pedido.recurso_id, opcoes)
    except (ganchos.RecursoInexistente, PermissionDenied):
        # Quem pediu perdeu o acesso (ou o registro sumiu) enquanto o pedido esperava.
        _encerrar(pedido, E.CANCELADO, "sem_acesso")
        return None
    determ = uso.deterministico(ctx)
    config = configuracao.de(uso.chave)

    def regra(motivo: str, **extra) -> Sugestao | None:
        return _registrar(pedido, uso, ctx, determ, origem=Sugestao.Origem.REGRA,
                          fallback=True, motivo=motivo, **extra)

    if not config.ligado or config.modo != ConfiguracaoUso.Modo.IA:
        return regra("modo_regra")
    try:
        conferir_minimizacao(uso, ctx)
    except ValueError:
        log.error("Minimização reprovada no uso %s", uso.chave)
        return regra("minimizacao")
    porta = porta or servico_ia.adaptador()
    pedido_ia = _pedido_ia(uso, ctx, determ, config, simular)
    if pedido_ia.contem_documento and not porta.aceita_documentos:
        return regra("documento")  # ADR 0041: nem chega a reservar
    tentativas = _admitir(pedido, uso.chave, config)
    if tentativas <= 0:
        return regra("limite_diario")
    maximo = servico_ia.custo_maximo(pedido_ia, porta) * tentativas
    # O lease passa a cobrir a chamada inteira (todas as tentativas): ninguém retoma o pedido
    # enquanto ela pode estar em curso, e a reserva fica anotada nele.
    prazo = timedelta(seconds=config.tempo_limite_s * tentativas + 60)
    reserva = orcamento.reservar(uso.chave, maximo, pedido_pk=pedido.pk, prazo=prazo)
    if reserva is None:
        return regra("orcamento")
    _fora_de_transacao(profundidade)
    execucao = servico_ia.executar(pedido_ia, porta, servico_ia.Limites(
        max_entrada_caracteres=config.max_entrada_caracteres,
        max_tokens_saida=config.max_tokens_saida,
        tempo_limite_s=float(config.tempo_limite_s), max_tentativas=tentativas))
    orcamento.liquidar(reserva, execucao.custo_estimado, execucao.tokens_entrada,
                       execucao.tokens_saida)
    if not execucao.ok:
        return regra(execucao.erro_codigo or "falha", execucao=execucao)
    erros = list(uso.validar(execucao.dados or {}, ctx)) + _sem_dado_pessoal(execucao.dados)
    if erros:
        return regra("validacao", erros=erros, execucao=execucao)
    return _registrar(pedido, uso, ctx, execucao.dados or {}, origem=execucao.origem,
                      execucao=execucao)


def _encerrar(pedido: PedidoSugestao, estado: str, motivo: str) -> None:
    """Encerra o pedido e DEVOLVE a reserva de orçamento que ainda estiver nele (erro
    inesperado entre reservar e liquidar). Sem isso, com `reservado_ate` nulo, nem a varredura
    de reservas presas a acharia e o teto mensal se esgotaria aos poucos."""
    with transaction.atomic():
        atual = PedidoSugestao.objects.select_for_update().filter(pk=pedido.pk).first()
        if atual is None:
            return
        orcamento.liberar_do_pedido(atual)
        atual.estado, atual.motivo, atual.reservado_ate = estado, motivo[:255], None
        atual.tentativas_admitidas = 0
        atual.save(update_fields=["estado", "motivo", "reservado_ate", "tentativas_admitidas",
                                  "atualizado_em"])


def _registrar(pedido: PedidoSugestao, uso: ganchos.UsoIA, ctx: ganchos.Contexto,
               dados: dict, *, origem: str, fallback: bool = False, motivo: str = "",
               erros: list[str] | None = None, execucao=None) -> Sugestao | None:
    erros = erros or []
    if esq.validar(dados, uso.esquema):  # o determinístico também precisa caber no esquema
        log.error("Determinístico fora do esquema no uso %s", uso.chave)
    itens = uso.itens(dados, ctx)
    lacunas = [c for c in dict.fromkeys([*ctx.lacunas, *dados.get("lacunas", [])])
               if c in uso.lacunas_conhecidas]
    fontes = sorted({r for i in itens for r in i.fontes})
    with transaction.atomic():
        atual = PedidoSugestao.objects.select_for_update().get(pk=pedido.pk)
        if atual.estado not in (E.PENDENTE, E.PROCESSANDO):
            return Sugestao.objects.filter(pedido=atual).first()
        # Uma sugestão nova substitui a anterior ainda não decidida do mesmo registro.
        Sugestao.objects.filter(uso=uso.chave, recurso_id=pedido.recurso_id,
                                estado=S.PRONTA).update(estado=S.OBSOLETA,
                                                        atualizada_em=timezone.now())
        s = Sugestao.objects.create(
            pedido=atual, uso=uso.chave, recurso_id=pedido.recurso_id, origem=origem,
            fallback=fallback, motivo_fallback=motivo[:40], versao_prompt=uso.versao_prompt,
            versao_fonte=ctx.versao, fontes=fontes, lacunas=lacunas,
            erros_validacao=codigos(erros)[:20],
            modelo=execucao.modelo if execucao else "",
            hash_contexto=execucao.hash_contexto if execucao else "",
            tokens_entrada=execucao.tokens_entrada if execucao else 0,
            tokens_saida=execucao.tokens_saida if execucao else 0,
            tokens_estimados=bool(execucao and execucao.resposta
                                  and execucao.resposta.tokens_estimados),
            custo_estimado_usd=execucao.custo_estimado if execucao else 0,
            duracao_ms=(execucao.resposta.duracao_ms if execucao and execucao.resposta else 0),
            tentativas_ia=execucao.tentativas if execucao else 0)
        ConteudoSugestao.objects.create(sugestao=s, itens=[asdict(i) for i in itens],
                                        avisos=erros[:20],
                                        expira_em=timezone.now() + retencao())
        atual.estado, atual.reservado_ate = E.CONCLUIDO, None
        atual.versao_fonte, atual.motivo = ctx.versao, motivo[:255]
        atual.tentativas_admitidas = 0  # as chamadas feitas agora contam pela sugestão
        atual.save(update_fields=["estado", "reservado_ate", "versao_fonte", "motivo",
                                  "tentativas_admitidas", "atualizado_em"])
    return s


def processar_fila(limite: int = 20, porta: PortaIA | None = None) -> int:
    """Uma passada pela fila (o comando e o botão do simulador usam). Pedido que passou de
    `MAX_TENTATIVAS_PEDIDO` (worker caído no meio) sai pelo determinístico."""
    feitos = 0
    for _ in range(limite):
        pk = reservar_proximo()
        if pk is None:
            break
        pedido = PedidoSugestao.objects.get(pk=pk)
        try:
            if pedido.tentativas > MAX_TENTATIVAS_PEDIDO:
                uso = ganchos.uso(pedido.uso)
                conteudo = ConteudoPedido.objects.filter(pedido=pedido).first()
                if uso is None:
                    _encerrar(pedido, E.FALHOU, "uso_desconhecido")
                else:
                    ctx = uso.montar(pedido.usuario, pedido.recurso_id,
                                     conteudo.opcoes if conteudo else {})
                    _registrar(pedido, uso, ctx, uso.deterministico(ctx),
                               origem=Sugestao.Origem.REGRA, fallback=True,
                               motivo="tentativas")
            else:
                processar(pk, porta)
        except Exception:
            log.exception("Pedido de IA %s falhou", pk)
            _encerrar(pedido, E.FALHOU, "erro_interno")
        feitos += 1
    return feitos


# ------------------------------------------------------------------ decisão humana
def obsoleta(s: Sugestao) -> bool:
    """A fonte mudou desde a sugestão? (sem gravar)"""
    if s.estado != S.PRONTA:
        return s.estado == S.OBSOLETA
    uso = ganchos.uso(s.uso)
    if uso is None or uso.versao_atual is None:
        return False
    try:
        atual = uso.versao_atual(s.recurso_id)
    except ganchos.RecursoInexistente:
        return True
    return atual is not None and atual != s.versao_fonte


@transaction.atomic
def marcar_obsoleta_se_mudou(s: Sugestao) -> bool:
    if s.estado == S.PRONTA and obsoleta(s):
        Sugestao.objects.filter(pk=s.pk, estado=S.PRONTA).update(
            estado=S.OBSOLETA, atualizada_em=timezone.now())
        s.estado = S.OBSOLETA
        return True
    return False


def _travar_pronta(usuario, pk: int) -> tuple[Sugestao, ganchos.UsoIA]:
    s = Sugestao.objects.select_for_update().get(pk=pk)
    uso = _uso(s.uso)
    policies.exigir(policies.pode_decidir(usuario, uso, s.recurso_id),
                    "Você não pode decidir esta sugestão.")
    if s.estado != S.PRONTA:
        raise ganchos.AplicacaoRecusada(
            f"Esta sugestão já está “{s.get_estado_display().lower()}”: peça outra se precisar.")
    return s, uso


def aceitar(usuario, pk: int, editados: dict[str, str] | None = None, *,
            substituir: bool = False) -> Sugestao:
    """Aceitar (ou editar e aceitar). Devolve a sugestão; se a fonte mudou, ela volta
    `obsoleta` e nada é gravado no registro."""
    with transaction.atomic():
        s, uso = _travar_pronta(usuario, pk)
        conteudo = ConteudoSugestao.objects.filter(sugestao=s).first()
        if conteudo is None:
            raise ganchos.AplicacaoRecusada("O texto desta sugestão já saiu da retenção: "
                                            "peça outra.")
        textos = {i["campo"]: i["valor"] for i in conteudo.itens if i.get("aplicavel")}
        editada = False
        for campo, texto in (editados or {}).items():
            novo = (texto or "").strip()[:4000]
            if campo in textos and novo and novo != textos[campo].strip():
                textos[campo], editada = novo, True
        if uso.versao_atual is not None:
            try:
                atual = uso.versao_atual(s.recurso_id)
            except ganchos.RecursoInexistente:
                atual = None
            if atual != s.versao_fonte:
                s.estado = S.OBSOLETA
                s.save(update_fields=["estado", "atualizada_em"])
                return s
        if uso.aplicar is not None and textos:
            try:
                with transaction.atomic():
                    uso.aplicar(usuario, s.recurso_id, textos, s.versao_fonte, substituir)
            except ganchos.Obsoleta:
                s.estado = S.OBSOLETA
                s.save(update_fields=["estado", "atualizada_em"])
                return s
            s.aplicada = True
        s.estado = S.EDITADA if editada else S.ACEITA
        s.decidida_por, s.decidida_em = usuario, timezone.now()
        s.save(update_fields=["estado", "decidida_por", "decidida_em", "aplicada",
                              "atualizada_em"])
        conteudo.texto_aplicado = textos if s.aplicada else {}
        conteudo.save(update_fields=["texto_aplicado"])
    return s


@transaction.atomic
def descartar(usuario, pk: int, motivo: str = "") -> Sugestao:
    s, _ = _travar_pronta(usuario, pk)
    s.estado = S.DESCARTADA
    s.motivo_descarte = motivo if motivo in Sugestao.MotivoDescarte.values else "outro"
    s.decidida_por, s.decidida_em = usuario, timezone.now()
    s.save(update_fields=["estado", "motivo_descarte", "decidida_por", "decidida_em",
                          "atualizada_em"])
    return s


# ------------------------------------------------------------------ leitura para as telas
def ultima(uso: str, recurso_id: str) -> tuple[PedidoSugestao | None, Sugestao | None]:
    pedido = (PedidoSugestao.objects.filter(uso=uso, recurso_id=str(recurso_id))
              .order_by("-id").first())
    if pedido is None:
        return None, None
    return pedido, Sugestao.objects.filter(pedido=pedido).first()


def textos_atuais(usuario, s: Sugestao) -> dict[str, str]:
    """O texto que os campos-alvo têm AGORA no registro (para a revisão mostrar "Atual" ao
    lado de "Sugerido"). Leitura com a política de quem revisa; sem acesso, nada."""
    uso = ganchos.uso(s.uso)
    if uso is None:
        return {}
    conteudo = ConteudoPedido.objects.filter(pedido_id=s.pedido_id).first()
    try:
        ctx = uso.montar(usuario, s.recurso_id, conteudo.opcoes if conteudo else {})
    except (ganchos.RecursoInexistente, PermissionDenied):
        return {}
    return {campo: (texto or "") for campo, texto in ctx.textos_atuais.items()}
