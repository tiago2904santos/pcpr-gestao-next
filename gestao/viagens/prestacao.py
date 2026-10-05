"""Prestação de contas (módulo 9a, paridade com `viagens_prestacoes` da referência; ficha em
docs/migration/prestacao.md).

A prestação nasce quando o ofício é emitido (uma por ofício, uma linha por servidor da
equipe) e acompanha a equipe a cada nova emissão: quem entra ganha linha; quem sai some —
apagado se nada foi lançado, só marcado como removido se já tinha dados.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.utils import timezone

from . import policies
from .dominio import prestacao as dominio
from .models import Oficio, PrestacaoContas, PrestacaoServidor


class PrestacaoInvalida(Exception):
    pass


def ativos(qs=None) -> QuerySet[PrestacaoServidor]:
    """As linhas de quem está na equipe (as removidas ficam guardadas, fora das listas)."""
    return (qs if qs is not None else PrestacaoServidor.objects).filter(removida_em__isnull=True)


# ---------------------------------------------------------------- nascimento
def _tem_dados(ps: PrestacaoServidor) -> bool:
    return bool(ps.numero_solicitacao or ps.data_liberacao_diarias or ps.prazo_limite_saque
                or ps.finalizada_em or ps.enviada_em or ps.diaria_valor_override)


@transaction.atomic
def sincronizar(oficio: Oficio) -> PrestacaoContas | None:
    """Cria a prestação do ofício emitido e acerta as linhas pela equipe atual."""
    if oficio.situacao == Oficio.Situacao.CANCELADO:
        return None
    prestacao, _ = PrestacaoContas.objects.get_or_create(oficio=oficio)
    equipe = set(oficio.viajantes.values_list("servidor_id", flat=True))
    linhas = {ps.servidor_id: ps for ps in PrestacaoServidor.objects.filter(prestacao=prestacao)}
    for servidor_id in equipe:
        ps = linhas.get(servidor_id)
        if ps is None:
            PrestacaoServidor.objects.create(prestacao=prestacao, servidor_id=servidor_id)
        elif ps.removida_em is not None:
            PrestacaoServidor.objects.filter(pk=ps.pk).update(removida_em=None)
    for servidor_id, ps in linhas.items():
        if servidor_id in equipe or ps.removida_em is not None:
            continue
        if _tem_dados(ps):
            PrestacaoServidor.objects.filter(pk=ps.pk).update(removida_em=timezone.now())
        else:
            ps.delete()
    return prestacao


# ---------------------------------------------------------------- abas dos outros módulos
def contas_prestadas(**ligacao):
    """Expressão "contas prestadas" para as abas Finalizados/Contas prestadas das outras
    listas (referência: `*/abas.py`): existe prestação de servidor ligada e nenhuma em
    aberto; arquivar não conta; ofício cancelado e quem saiu da equipe ficam de fora.
    `ligacao` liga a linha da prestação ao registro da lista, com OuterRef — ex.:
    `prestacao__oficio__roteiro=OuterRef("pk")`."""
    ligadas = ativos(PrestacaoServidor.objects.filter(**ligacao)).exclude(
        prestacao__oficio__situacao=Oficio.Situacao.CANCELADO)
    return Exists(ligadas) & ~Exists(ligadas.filter(finalizada_em__isnull=True))


LIGACOES = {
    "roteiro": {"prestacao__oficio__roteiro": OuterRef("pk")},
    "oficio": {"prestacao__oficio": OuterRef("pk")},
    "termo": {"prestacao__oficio": OuterRef("oficio_id")},  # avulso (sem ofício) nunca
    "ordem": {"prestacao__oficio__ordens": OuterRef("pk")},
    "plano": {"prestacao__oficio__viagem": OuterRef("viagem_id")},  # pela viagem (referência)
    "viagem": {"prestacao__oficio__viagem": OuterRef("pk")},
}


def prestadas(tipo: str):
    return contas_prestadas(**LIGACOES[tipo])


# ---------------------------------------------------------------- leitura
def diaria_liberada(ps: PrestacaoServidor, equipe: int | None = None) -> Decimal | None:
    """Quanto foi liberado para o servidor — o teto do que ele pode ter recebido
    (referência: `valor_diaria_liberado`): o "por servidor" do cálculo do ofício; sem ele,
    o total ÷ a equipe (`equipe` = tamanho já contado, para a lista não contar de novo).
    A diária recebida (override, quando o saque difere) entra com o relatório técnico."""
    from . import realizado
    if (valor := realizado.por_servidor(ps.prestacao)) is not None:
        return valor  # a viagem foi ajustada: vale o realizado (referência: roteiro efetivo)
    oficio = ps.prestacao.oficio
    por_servidor = (oficio.diarias_calculo or {}).get("por_servidor")
    if por_servidor and Decimal(por_servidor) > 0:
        return Decimal(por_servidor).quantize(Decimal("0.01"), ROUND_HALF_UP)
    n = oficio.viajantes.count() if equipe is None else equipe
    if not n or not oficio.diarias_total:
        return None
    return (Decimal(oficio.diarias_total) / n).quantize(Decimal("0.01"), ROUND_HALF_UP)


def pendencias(ps: PrestacaoServidor, situacao=None) -> list[str]:
    """O que falta para finalizar, na ordem e com os textos da referência
    (`pendencias_para_finalizar`): nº da solicitação, despacho, comprovante, diário (ou o
    assinado), RT (ou o assinado), o número carimbado no ofício assinado e a soma dos
    comprovantes igual à diária. `situacao` (anexos.Situacao) vem pronta da lista; sem ela,
    é calculada para esta prestação."""
    from . import anexos, diario, relatorio
    s = situacao if situacao is not None else anexos.situacao([ps.prestacao_id])
    p = ps.prestacao_id
    falta = []
    if not ps.numero_solicitacao.strip():
        falta.append("Informe o número da solicitação deste servidor.")
    if p not in s.despachos:
        falta.append("Anexe o despacho assinado do ofício.")
    valores = s.comprovantes.get(ps.pk, [])
    if not valores:
        falta.append("Anexe o comprovante de saque/transferência deste servidor.")
    if p not in s.diarios and p not in s.db_assinados:
        falta.append(diario.PENDENCIA)
    if p not in s.relatorios and ps.pk not in s.rt_assinados:
        falta.append(relatorio.PENDENCIA)
    if p in s.vias and ps.numero_solicitacao.strip() and ps.pk not in s.carimbados:
        from .carimbo import PENDENCIA as SEM_CARIMBO
        falta.append(SEM_CARIMBO)
    if (d := anexos.divergencia(ps, valores, diaria_liberada(
            ps, getattr(ps.prestacao, "equipe", None)))):
        from .dominio.relatorio import moeda
        falta.append(f"Os comprovantes somam {moeda(d[0])}, e a diária deste servidor é "
                     f"{moeda(d[1])}.")
    return falta


ABAS = [
    ("nao_liberadas", "Não liberadas"), ("liberadas", "Liberadas"),
    ("devolvidas", "Devolvidas"), ("arquivados", "Arquivados"),
    ("finalizados", "Finalizados"), ("saque_vencendo", "Saque vencendo"),
    ("prestacao_vencida", "Prestação vencida"),
    ("sem_solicitacao", "Sem nº de solicitação"), ("finalizadas_mes", "Finalizadas no mês"),
]


def _pendente_na_prestacao():
    return Exists(PrestacaoServidor.objects.filter(
        prestacao_id=OuterRef("prestacao_id"), removida_em__isnull=True,
        finalizada_em__isnull=True))


def filtrar(qs: QuerySet[PrestacaoServidor], aba: str, hoje: date | None = None):
    hoje = hoje or timezone.localdate()
    aberto = Q(finalizada_em__isnull=True, arquivada_em__isnull=True)
    if aba == "nao_liberadas":
        return qs.filter(aberto, data_liberacao_diarias__isnull=True).exclude(
            situacao=PrestacaoServidor.Situacao.DEVOLVIDA)
    if aba == "liberadas":
        return qs.filter(aberto, data_liberacao_diarias__isnull=False).exclude(
            situacao=PrestacaoServidor.Situacao.DEVOLVIDA)
    if aba == "devolvidas":
        return qs.filter(situacao=PrestacaoServidor.Situacao.DEVOLVIDA,
                         finalizada_em__isnull=True)
    if aba == "arquivados":
        return qs.filter(arquivada_em__isnull=False, finalizada_em__isnull=True)
    if aba == "finalizados":  # ninguém da prestação ainda em aberto (referência)
        return qs.annotate(_pendente=_pendente_na_prestacao()).filter(_pendente=False)
    if aba == "saque_vencendo":
        return qs.filter(aberto, prazo_limite_saque__isnull=False,
                         prazo_limite_saque__lte=hoje + _dias(dominio.DIAS_AVISO_SAQUE))
    if aba == "prestacao_vencida":
        ids = [ps.pk for ps in qs.filter(aberto, prazo_limite_saque__isnull=False)
               .select_related(None).only("pk", "prazo_limite_saque")
               if (dominio.prazo_para_prestar(ps.prazo_limite_saque) or hoje) < hoje]
        return qs.filter(pk__in=ids)
    if aba == "sem_solicitacao":
        return qs.filter(aberto, numero_solicitacao="")
    if aba == "finalizadas_mes":
        return qs.filter(finalizada_em__year=hoje.year, finalizada_em__month=hoje.month)
    return qs


def _dias(n: int):
    from datetime import timedelta
    return timedelta(days=n)


def selos(ps: PrestacaoServidor, hoje: date | None = None,
          tem_comprovante: bool = False) -> list[dominio.Selo]:
    hoje = hoje or timezone.localdate()
    saida = []
    if (s := dominio.selo_do_saque(ps.prazo_limite_saque, finalizada=ps.finalizada,
                                   tem_comprovante=tem_comprovante, hoje=hoje)):
        saida.append(s)
    if (s := dominio.selo_da_prestacao(ps.prazo_limite_saque, finalizada=ps.finalizada,
                                       hoje=hoje)):
        saida.append(s)
    return saida


# ---------------------------------------------------------------- escrita
def _travar(usuario, ps_pk: int, *, editar_finalizada: bool = False) -> PrestacaoServidor:
    ps = (PrestacaoServidor.objects.select_for_update()
          .select_related("prestacao__oficio", "servidor").get(pk=ps_pk))
    policies.exigir(policies.pode_editar_prestacao(usuario, ps),
                    "Você não pode alterar esta prestação.")
    if ps.finalizada and not editar_finalizada:
        raise PrestacaoInvalida("Prestação finalizada — reabra para editar.")
    return ps


def _validar_datas(liberacao: date | None, prazo: date | None) -> None:
    if liberacao and prazo and prazo < liberacao:
        raise PrestacaoInvalida("O prazo limite de saque não pode ser anterior à liberação.")


@transaction.atomic
def salvar_solicitacao(usuario, ps_pk: int, *, numero: str, liberacao: date | None,
                       prazo: date | None) -> PrestacaoServidor:
    ps = _travar(usuario, ps_pk)
    _validar_datas(liberacao, prazo)
    numero = (numero or "").strip()[:60]
    if (ps.numero_solicitacao, ps.data_liberacao_diarias, ps.prazo_limite_saque) == (
            numero, liberacao, prazo):
        return ps  # nada mudou: sem gravação nem evento na trilha
    liberou_agora = ps.data_liberacao_diarias is None and liberacao is not None
    ps.numero_solicitacao = numero
    ps.data_liberacao_diarias, ps.prazo_limite_saque = liberacao, prazo
    if ps.situacao == PrestacaoServidor.Situacao.PENDENTE:
        ps.situacao = PrestacaoServidor.Situacao.PREENCHIMENTO
    ps.save()
    if liberou_agora:
        _avisar_diarias_liberadas(ps, usuario)
    return ps


@transaction.atomic
def arquivar(usuario, ps_pk: int, arquivar: bool = True) -> PrestacaoServidor:
    ps = _travar(usuario, ps_pk, editar_finalizada=True)
    if ps.arquivada == arquivar:
        estado = "arquivada" if arquivar else "desarquivada"
        raise PrestacaoInvalida(f"A prestação de {ps.servidor} já estava {estado}.")
    ps.arquivada_em = timezone.now() if arquivar else None
    ps.save(update_fields=["arquivada_em", "atualizado_em"])
    return ps


@transaction.atomic
def finalizar(usuario, ps_pk: int, justificativa: str = "") -> PrestacaoServidor:
    """Com pendência, só com justificativa (fica registrada, como na referência)."""
    ps = _travar(usuario, ps_pk, editar_finalizada=True)
    if ps.finalizada:
        raise PrestacaoInvalida(f"A prestação de {ps.servidor} já estava finalizada.")
    falta = pendencias(ps)
    justificativa = (justificativa or "").strip()
    if falta and not justificativa:
        raise PrestacaoInvalida(f"A prestação de {ps.servidor} tem pendências: "
                                f"{' '.join(falta)} Para finalizar mesmo assim, escreva a "
                                "justificativa.")
    ps.finalizada_em = timezone.now()
    ps.justificativa_finalizacao = justificativa if falta else ""
    ps.save(update_fields=["finalizada_em", "justificativa_finalizacao", "atualizado_em"])
    return ps


@transaction.atomic
def reabrir(usuario, ps_pk: int) -> PrestacaoServidor:
    ps = _travar(usuario, ps_pk, editar_finalizada=True)
    if not ps.finalizada:
        raise PrestacaoInvalida(f"A prestação de {ps.servidor} já estava aberta.")
    if ps.situacao in (PrestacaoServidor.Situacao.ENVIADA, PrestacaoServidor.Situacao.APROVADA):
        # Reabrir não desfaz o envio nem a aprovação por baixo (decisão do agente): para
        # corrigir o que já foi ao financeiro, devolve-se, com motivo.
        raise PrestacaoInvalida(f"A prestação de {ps.servidor} já foi enviada ao financeiro — "
                                "para corrigir, devolva com o motivo.")
    ps.finalizada_em, ps.justificativa_finalizacao = None, ""
    ps.save(update_fields=["finalizada_em", "justificativa_finalizacao", "atualizado_em"])
    return ps


@dataclass
class ResultadoEquipe:
    feitos: int = 0
    pulados: list[str] = field(default_factory=list)


@transaction.atomic
def acao_da_equipe(usuario, prestacao_pk: int, acao: str) -> ResultadoEquipe:
    """finalizar | reabrir | arquivar | desarquivar para a equipe toda; ao finalizar, quem
    tem pendência fica de fora (referência)."""
    policies.exigir(policies.pode_editar_equipe_prestacao(
        usuario, PrestacaoContas.objects.select_related("oficio").get(pk=prestacao_pk)),
        "Você não pode alterar esta prestação.")
    r = ResultadoEquipe()
    for ps in ativos(PrestacaoServidor.objects.filter(prestacao_id=prestacao_pk)
                     .select_related("servidor")):
        try:
            if acao == "finalizar" and not ps.finalizada:
                if pendencias(ps):
                    r.pulados.append(ps.servidor.nome)
                    continue
                finalizar(usuario, ps.pk)
            elif acao == "reabrir" and ps.finalizada:
                reabrir(usuario, ps.pk)
            elif acao == "arquivar" and not ps.arquivada:
                arquivar(usuario, ps.pk, True)
            elif acao == "desarquivar" and ps.arquivada:
                arquivar(usuario, ps.pk, False)
            else:
                continue
        except PrestacaoInvalida:
            continue
        r.feitos += 1
    return r


@transaction.atomic
def enviar(usuario, ps_pk: int, *, enviada_em: date | None, protocolo: str,
           equipe: bool = False) -> int:
    """Só quem está finalizado; a aprovada não volta a "enviada" (decisão do agente — a
    referência reenviava por cima). Pela equipe: as finalizadas ainda não enviadas."""
    ps = _travar(usuario, ps_pk, editar_finalizada=True)
    if equipe:
        alvos = [x for x in ativos(PrestacaoServidor.objects.filter(prestacao_id=ps.prestacao_id))
                 if x.finalizada and x.situacao not in (PrestacaoServidor.Situacao.ENVIADA,
                                                        PrestacaoServidor.Situacao.APROVADA)]
        if not alvos:
            raise PrestacaoInvalida("Ninguém da equipe está finalizado e por enviar.")
    else:
        if not ps.finalizada:
            raise PrestacaoInvalida("Finalize a prestação antes de registrar o envio.")
        if ps.situacao == PrestacaoServidor.Situacao.APROVADA:
            raise PrestacaoInvalida(f"A prestação de {ps.servidor} já foi aprovada.")
        alvos = [ps]
    for x in alvos:
        PrestacaoServidor.objects.filter(pk=x.pk).update(
            situacao=PrestacaoServidor.Situacao.ENVIADA,
            enviada_em=enviada_em or timezone.localdate(), decidida_em=None,
            protocolo_envio=(protocolo or "").strip()[:120], atualizado_em=timezone.now())
    return len(alvos)


@transaction.atomic
def aprovar(usuario, ps_pk: int) -> PrestacaoServidor:
    ps = _travar(usuario, ps_pk, editar_finalizada=True)
    if ps.situacao != PrestacaoServidor.Situacao.ENVIADA:
        raise PrestacaoInvalida("Só a prestação enviada pode ser aprovada.")
    ps.situacao, ps.decidida_em = PrestacaoServidor.Situacao.APROVADA, timezone.now()
    ps.motivo_devolucao = ""
    ps.save(update_fields=["situacao", "decidida_em", "motivo_devolucao", "atualizado_em"])
    return ps


@transaction.atomic
def devolver(usuario, ps_pk: int, motivo: str) -> PrestacaoServidor:
    """Devolve e reabre para correção; avisa a equipe de viagens (menos quem devolveu)."""
    ps = _travar(usuario, ps_pk, editar_finalizada=True)
    if ps.situacao not in (PrestacaoServidor.Situacao.ENVIADA,
                           PrestacaoServidor.Situacao.APROVADA):
        raise PrestacaoInvalida("Só a prestação enviada pode ser devolvida.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise PrestacaoInvalida("Escreva o motivo da devolução.")
    ps.situacao, ps.decidida_em = PrestacaoServidor.Situacao.DEVOLVIDA, timezone.now()
    ps.motivo_devolucao, ps.finalizada_em = motivo, None
    ps.save(update_fields=["situacao", "decidida_em", "motivo_devolucao", "finalizada_em",
                           "atualizado_em"])
    _avisar(ps, f"Prestação devolvida: {ps.servidor.nome} ({ps.prestacao.oficio})", motivo,
            usuario)
    return ps


# ---------------------------------------------------------------- avisos (sino)
def _avisar(ps: PrestacaoServidor, titulo: str, mensagem: str, autor) -> None:
    """A equipe de viagens da unidade do ofício (decisão do agente: quem é de outra unidade
    nem vê esta prestação), menos quem fez a ação."""
    from django.urls import reverse

    from gestao.plataforma.notificacoes import notificar, usuarios_do_grupo
    oficio = ps.prestacao.oficio
    notificar(usuarios_do_grupo("OPERADOR_VIAGENS").filter(lotacao__unidade=oficio.unidade_id),
              titulo, mensagem, reverse("viagens:prestacoes") + f"?q={oficio.numero_formatado}",
              exceto=autor)


def _avisar_diarias_liberadas(ps: PrestacaoServidor, autor) -> None:
    quem = f"{ps.servidor.nome} ({ps.prestacao.oficio})"
    mensagem = "Avise o servidor da liberação."
    if ps.prazo_limite_saque:
        mensagem += f" Prazo para saque: {ps.prazo_limite_saque:%d/%m/%Y}."
    _avisar(ps, f"Diárias liberadas: {quem} em {ps.data_liberacao_diarias:%d/%m}", mensagem,
            autor)
