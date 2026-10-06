"""Encaminhar à DG (PL2a; paridade com `demandas_eventos/encaminhamento.py`): a palestra ou
o evento da ASCOM vira o rascunho de uma solicitação de evento (Eventos Sociais), já com o
que a palestra sabe — datas, município, tipo, solicitante, contato e a descrição com tema,
palestrante, horário e público — e as duas ficam ligadas. Quem encaminhou completa na
solicitação o que só ela pede (órgão, serviços, equipes) e envia; o que a DG decide aparece
no histórico da palestra (lido da solicitação ligada)."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db import transaction

from gestao.eventos import solicitacoes
from gestao.eventos.models import Movimento as MovimentoEvento
from gestao.eventos.models import Solicitacao, TipoEvento

from . import policies
from .models import Andamento, Palestra

# O tipo de evento da solicitação que corresponde a cada "Evento" da palestra (o relatório
# consolidado reconhece o PCPR pela palavra COMUNIDADE).
PALAVRA_DO_TIPO = {"pcpr_na_comunidade": "COMUNIDADE", "palestra": "PALESTRA"}
# O que da solicitação ligada vira linha no histórico da palestra.
ACOES_DA_DG = (MovimentoEvento.Acao.ENVIO, MovimentoEvento.Acao.DEVOLUCAO,
               MovimentoEvento.Acao.REENVIO, MovimentoEvento.Acao.DECISAO,
               MovimentoEvento.Acao.CONCLUSAO, MovimentoEvento.Acao.CANCELAMENTO)


class EncaminhamentoInvalido(Exception):
    pass


def _tipo(p: Palestra) -> TipoEvento | None:
    palavra = PALAVRA_DO_TIPO.get(p.evento)
    if not palavra:
        return None
    return (TipoEvento.objects.filter(ativo=True, nome__icontains=palavra)
            .order_by("nome").first())


def _descricao(p: Palestra) -> str:
    partes = [p.descricao.strip()] if (p.descricao or "").strip() else []
    temas = ", ".join(t.nome for t in p.temas.all())
    palestrantes = ", ".join(x.nome for x in p.palestrantes.all())
    horario = f"{p.hora_inicio:%H:%M}" if p.hora_inicio else (p.periodo_evento_texto or "")
    for rotulo, valor in (("Tema", temas), ("Palestrante", palestrantes),
                          ("Horário", horario),
                          ("Público previsto", f"{p.quantidade_publico} pessoas"
                           if p.quantidade_publico else ""),
                          ("Local", p.local)):
        if valor:
            partes.append(f"{rotulo}: {valor}")
    partes.append(f"Encaminhada da {p.get_evento_display().lower()} #{p.pk} da ASCOM.")
    return "\n".join(partes)


def pode_encaminhar(usuario, p: Palestra) -> bool:
    return (policies.pode_editar(usuario) and p.solicitacao_dg_id is None
            and p.status != Palestra.Status.CANCELADA)


@transaction.atomic
def encaminhar(usuario, pk: int) -> Solicitacao:
    p = Palestra.objects.select_for_update().get(pk=pk)
    if not policies.pode_editar(usuario):
        raise PermissionDenied
    if p.solicitacao_dg_id:
        raise EncaminhamentoInvalido(
            f"Já encaminhada à DG: solicitação de evento #{p.solicitacao_dg_id}.")
    if p.status == Palestra.Status.CANCELADA:
        raise EncaminhamentoInvalido("Palestra cancelada não vai à DG.")
    contato = " ".join(x for x in (p.telefone, p.email) if x)
    s = solicitacoes.criar(usuario, {
        "data_inicio_evento": p.data_inicio_evento,
        # A solicitação pede o fim do evento para ir à DG: evento de um dia.
        "data_fim_evento": p.data_fim_evento or p.data_inicio_evento,
        "municipio": p.municipio, "tipo_evento": _tipo(p),
        "solicitante_nome": p.solicitante[:150], "contato": contato[:100],
        "local_evento": (p.local or "")[:255], "endereco": (p.endereco or "")[:255],
        "bairro": (p.bairro or "")[:120], "cep": (p.cep or "")[:9],
        "descricao_complementar": _descricao(p)})
    p.solicitacao_dg = s
    p.save(update_fields=["solicitacao_dg", "atualizado_em"])
    Andamento.objects.create(palestra=p, status_anterior=p.status, status_novo=p.status,
                             usuario=usuario, anotacao=(
                                 f"Solicitação de evento #{s.pk} criada em rascunho para o "
                                 "despacho da DG."))
    return s


def movimentos_da_dg(p: Palestra) -> list[MovimentoEvento]:
    """O envio, a devolução, a decisão, a conclusão e o cancelamento na solicitação ligada."""
    if p.solicitacao_dg_id is None:
        return []
    return list(MovimentoEvento.objects.filter(solicitacao_id=p.solicitacao_dg_id,
                                               acao__in=ACOES_DA_DG)
                .select_related("usuario", "solicitacao"))

