"""Viagens na automação (ADR 0047): o aviso de diárias liberadas e o lembrete de comprovante
vão ao servidor pelo WhatsApp, e o comprovante que ele devolve por lá entra na prestação.

A automação não conhece Viagens: aqui se registram os ganchos (`registrar()`, no `ready`).
`preparar` relê a prestação no momento do envio — se o comprovante já chegou, a prestação
foi finalizada ou as datas mudaram, a mensagem não sai (obsoleta). A versão é o hash das
datas e do número da solicitação: mudou a liberação, a mensagem antiga perde a validade e
uma nova é agendada (o número da solicitação não entra: corrigi-lo não reavisa ninguém).

Tudo é simulação: o texto diz que os dados são fictícios.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from gestao.automacao import comunicacoes as automacao
from gestao.automacao import ganchos

from .models import AnexoPrestacao, Oficio, PrestacaoServidor

AVISO = "viagens.diarias_liberadas"
LEMBRETE = "viagens.lembrete_comprovante"
COMPROVANTE = "viagens.comprovante"
RECURSO = "viagens.prestacaoservidor"


def _recurso(ps_pk: int) -> str:
    return f"{RECURSO}:{ps_pk}"


def _pk(recurso_ou_contexto) -> int | None:
    if isinstance(recurso_ou_contexto, dict):
        pk = recurso_ou_contexto.get("ps")
        return pk if isinstance(pk, int) else None
    _, _, pk = str(recurso_ou_contexto).partition(":")
    return int(pk) if pk.isdigit() else None


def versao(ps: PrestacaoServidor) -> str:
    base = f"{ps.data_liberacao_diarias}|{ps.prazo_limite_saque}"
    return hashlib.sha256(base.encode()).hexdigest()[:16]


def _ps(pk: int | None) -> PrestacaoServidor | None:
    if pk is None:
        return None
    return (PrestacaoServidor.objects.select_related("servidor", "prestacao__oficio")
            .filter(pk=pk, removida_em__isnull=True).first())


def _tem_comprovante(ps: PrestacaoServidor) -> bool:
    from .anexos import ativos

    return ativos(AnexoPrestacao.objects.filter(
        servidor=ps, tipo=AnexoPrestacao.Tipo.COMPROVANTE)).exists()


def _aberta(ps: PrestacaoServidor | None) -> str:
    """Vazio se a prestação ainda pede o comprovante; senão, o motivo."""
    if ps is None:
        return "A prestação não existe mais."
    if ps.prestacao.oficio.situacao != Oficio.Situacao.EMITIDO:
        return "O ofício não está emitido."
    if ps.finalizada or ps.arquivada:
        return "A prestação foi finalizada ou arquivada."
    if not ps.data_liberacao_diarias:
        return "A liberação das diárias foi desfeita."
    if _tem_comprovante(ps):
        return "O comprovante já está na prestação."
    return ""


def _primeiro_nome(ps: PrestacaoServidor) -> str:
    return (ps.servidor.nome or "").split(" ")[0].title()


def _preparar_aviso(contexto: dict) -> ganchos.Preparo:
    ps = _ps(_pk(contexto))
    if motivo := _aberta(ps):
        return ganchos.Preparo(False, motivo)
    if ps is None:  # _aberta já devolveu o motivo; aqui só por segurança
        return ganchos.Preparo(False, "A prestação não existe mais.")
    oficio = ps.prestacao.oficio
    prazo = (f" O prazo para sacar ou transferir é {ps.prazo_limite_saque:%d/%m/%Y}."
             if ps.prazo_limite_saque else "")
    texto = (f"[TESTE — dados fictícios] Olá, {_primeiro_nome(ps)}. As diárias simuladas da "
             f"viagem do Ofício {oficio.numero_formatado} foram liberadas em "
             f"{ps.data_liberacao_diarias:%d/%m/%Y}.{prazo}\n\nQuando sacar ou transferir, "
             "responda esta mensagem com a foto ou o PDF do comprovante — ele entra direto na "
             "prestação de contas. Nenhum valor é real.")
    return ganchos.Preparo(True, versao=versao(ps), texto=texto, parametros=(
        _primeiro_nome(ps), oficio.numero_formatado, f"{ps.data_liberacao_diarias:%d/%m/%Y}",
        f"{ps.prazo_limite_saque:%d/%m/%Y}" if ps.prazo_limite_saque else "-"))


def _preparar_lembrete(contexto: dict) -> ganchos.Preparo:
    ps = _ps(_pk(contexto))
    if motivo := _aberta(ps):
        return ganchos.Preparo(False, motivo)
    if ps is None:  # _aberta já devolveu o motivo; aqui só por segurança
        return ganchos.Preparo(False, "A prestação não existe mais.")
    if not ps.prazo_limite_saque:
        return ganchos.Preparo(False, "A prestação não tem mais prazo de saque.")
    faltam = (ps.prazo_limite_saque - timezone.localdate()).days
    quando = ("vence hoje" if faltam == 0 else f"vence em {faltam} dia{'s' if faltam > 1 else ''}"
              if faltam > 0 else "já venceu")
    oficio = ps.prestacao.oficio
    texto = (f"[TESTE — dados fictícios] Lembrete: o prazo de saque das diárias simuladas do "
             f"Ofício {oficio.numero_formatado} {quando} ({ps.prazo_limite_saque:%d/%m/%Y}). "
             "Responda com a foto ou o PDF do comprovante.")
    return ganchos.Preparo(True, versao=versao(ps), texto=texto, parametros=(
        _primeiro_nome(ps), oficio.numero_formatado, f"{ps.prazo_limite_saque:%d/%m/%Y}"))


def _assunto(recurso: str) -> ganchos.Assunto | None:
    ps = _ps(_pk(recurso))
    if ps is None:
        return None
    oficio = ps.prestacao.oficio
    return ganchos.Assunto(f"Prestação de {ps.servidor} — Ofício {oficio.numero_formatado}",
                           reverse("viagens:prestacoes") + f"?q={oficio.numero_formatado}")


# ------------------------------------------------------------------ agendamento
def _agendar(tipo: str, ps: PrestacaoServidor, autor, chave: str,
             quando=None) -> None:
    automacao.agendar(tipo=tipo, servidor_id=ps.servidor_id, recurso=_recurso(ps.pk),
                      chave=chave, unidade_id=ps.prestacao.oficio.unidade_id,
                      criada_por=autor, contexto={"ps": ps.pk}, versao=versao(ps),
                      agendada_para=quando)


def diarias_liberadas(ps: PrestacaoServidor, autor) -> None:
    """Na transação de `prestacao.salvar_solicitacao`: a cada versão da liberação, um aviso
    (o da versão antiga, se ainda não saiu, fica obsoleto no envio)."""
    if not ps.data_liberacao_diarias:
        return
    _agendar(AVISO, ps, autor, f"{AVISO}:{ps.pk}:{versao(ps)}")


@transaction.atomic
def agendar_lembretes(hoje: date | None = None) -> int:
    """Rotina diária: a 2 dias do prazo e no dia, sem comprovante, um lembrete por etapa.
    Quem age é quem registrou a liberação (o autor do aviso), para o comprovante que voltar
    entrar em nome dele."""
    from gestao.automacao.models import Comunicacao

    hoje = hoje or timezone.localdate()
    total = 0
    alvo = {hoje + timedelta(days=2): "d-2", hoje: "d0"}
    candidatas = (PrestacaoServidor.objects.select_related("prestacao__oficio")
                  .filter(removida_em__isnull=True, finalizada_em__isnull=True,
                          arquivada_em__isnull=True, data_liberacao_diarias__isnull=False,
                          prazo_limite_saque__in=list(alvo),
                          prestacao__oficio__situacao=Oficio.Situacao.EMITIDO))
    for ps in candidatas:
        if _tem_comprovante(ps):
            continue
        aviso = (Comunicacao.objects.filter(tipo=AVISO, recurso=_recurso(ps.pk))
                 .exclude(criada_por=None).order_by("-criada_em").first())
        if aviso is None:
            continue  # sem aviso não há quem responda pelo lembrete
        if ps.prazo_limite_saque is None:  # inalcançável: filtrado por prazo_limite_saque__in
            raise KeyError(None)
        etapa = alvo[ps.prazo_limite_saque]
        automacao.agendar(tipo=LEMBRETE, servidor_id=ps.servidor_id, recurso=_recurso(ps.pk),
                          chave=f"{LEMBRETE}:{ps.pk}:{versao(ps)}:{etapa}",
                          unidade_id=ps.prestacao.oficio.unidade_id,
                          criada_por=aviso.criada_por, contexto={"ps": ps.pk},
                          versao=versao(ps))
        total += 1
    return total


# ------------------------------------------------------------------ comprovante recebido
def _associar(pedido: ganchos.PedidoDeAssociacao) -> str:
    """O arquivo vira comprovante da prestação, pelo serviço de anexos (policies valem
    para quem age). O mesmo arquivo de novo não duplica."""
    from django.core.exceptions import PermissionDenied

    from . import anexos

    ps = _ps(_pk(pedido.recurso) or _pk(pedido.contexto))
    if motivo := _aberta(ps):
        if ps is not None and motivo.startswith("O comprovante já"):
            existente = anexos.ativos(AnexoPrestacao.objects.filter(
                servidor=ps, tipo=AnexoPrestacao.Tipo.COMPROVANTE, sha256=pedido.sha256)
            ).first()
            if existente:
                return f"viagens.anexoprestacao:{existente.pk}"
        raise ganchos.ErroDeAssociacao(motivo)
    if ps is None:  # _aberta já devolveu o motivo; aqui só por segurança
        raise ganchos.ErroDeAssociacao("A prestação não existe mais.")
    try:
        anexo = anexos.anexar(pedido.usuario, ps.prestacao_id, AnexoPrestacao.Tipo.COMPROVANTE,
                              nome=pedido.nome, conteudo=pedido.conteudo, servidor_pk=ps.pk)
    except anexos.AnexoInvalido as erro:
        raise ganchos.ErroDeAssociacao(str(erro)) from erro
    except PermissionDenied:
        raise
    automacao.encerrar_relacionadas(_recurso(ps.pk), (AVISO, LEMBRETE),
                                    "O comprovante chegou pelo WhatsApp.")
    return f"viagens.anexoprestacao:{anexo.pk}"


def _candidatos(servidor_id: int) -> list[ganchos.Candidato]:
    saida = []
    for ps in (PrestacaoServidor.objects.select_related("prestacao__oficio")
               .filter(servidor_id=servidor_id, removida_em__isnull=True,
                       finalizada_em__isnull=True, arquivada_em__isnull=True,
                       data_liberacao_diarias__isnull=False,
                       prestacao__oficio__situacao=Oficio.Situacao.EMITIDO)
               .order_by("-data_liberacao_diarias")[:10]):
        if _tem_comprovante(ps):
            continue
        oficio = ps.prestacao.oficio
        saida.append(ganchos.Candidato(
            recurso=_recurso(ps.pk),
            rotulo=f"Ofício {oficio.numero_formatado} — diárias liberadas em "
                   f"{ps.data_liberacao_diarias:%d/%m/%Y}",
            unidade_id=oficio.unidade_id, contexto={"ps": ps.pk}))
    return saida


def _descrever(referencia: str) -> ganchos.Assunto | None:
    _, _, pk = referencia.partition(":")
    anexo = (AnexoPrestacao.objects.select_related("prestacao__oficio", "servidor")
             .filter(pk=int(pk)).first() if pk.isdigit() else None)
    if anexo is None:
        return None
    oficio = anexo.prestacao.oficio
    return ganchos.Assunto(
        f"Comprovante de {anexo.servidor} — Ofício {oficio.numero_formatado}",
        reverse("viagens:prestacoes") + f"?q={oficio.numero_formatado}")


def _confirmacao(referencia: str) -> str:
    descricao = _descrever(referencia)
    onde = descricao.rotulo.split(" — ", 1)[-1] if descricao else "a sua prestação"
    return (f"[TESTE] Recebemos o comprovante e ele já está na prestação de contas ({onde}). "
            "A equipe ainda confere antes de finalizar. Obrigado!")


def registrar() -> None:
    ganchos.registrar_tipo(ganchos.TipoComunicacao(
        chave=AVISO, rotulo="Diárias liberadas", fluxo="diarias_liberadas",
        preparar=_preparar_aviso, validade=timedelta(days=5), aceita_resposta=COMPROVANTE,
        janela_resposta=timedelta(days=30), assunto=_assunto))
    ganchos.registrar_tipo(ganchos.TipoComunicacao(
        chave=LEMBRETE, rotulo="Lembrete de comprovante", fluxo="lembretes_comprovante",
        preparar=_preparar_lembrete, validade=timedelta(hours=20),
        aceita_resposta=COMPROVANTE, janela_resposta=timedelta(days=30), assunto=_assunto))
    ganchos.registrar_destino(ganchos.DestinoRecebimento(
        chave=COMPROVANTE, rotulo="Comprovante de saque das diárias", associar=_associar,
        candidatos=_candidatos, descrever=_descrever, confirmacao=_confirmacao))


def situacoes(ps_ids: list[int]) -> dict[int, tuple[int, str]]:
    """{ps: (comunicação, "WhatsApp: enviada · lida")} da mensagem mais recente de cada
    prestação — uma consulta para a página inteira da lista."""
    from gestao.automacao.models import Comunicacao

    if not ps_ids:
        return {}
    saida: dict[int, tuple[int, str]] = {}
    for pk, recurso, situacao, entrega in (
            Comunicacao.objects.filter(recurso__in=[_recurso(i) for i in ps_ids],
                                       tipo__in=(AVISO, LEMBRETE))
            .order_by("criada_em", "id").values_list("pk", "recurso", "situacao", "entrega")):
        rotulo = Comunicacao.Situacao(situacao).label
        if entrega:
            rotulo += f" · {Comunicacao.Entrega(entrega).label.lower()}"
        saida[int(recurso.rsplit(":", 1)[1])] = (pk, f"WhatsApp: {rotulo.lower()}")
    return saida
