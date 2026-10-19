"""A "minha situação" do servidor viajante (AUT-97), só com os registros DELE.

Fonte registrada na assistência (`registrar_fonte_situacao`): o assistente (portal e
WhatsApp) e a futura página com link pessoal chamam `assistencia.assistente
.situacao_do_servidor(servidor_id)`. O servidor vem da identidade resolvida pelo sistema
(LinkAcesso, contato verificado) — nunca de um número digitado na conversa.

Pendências com código estável e texto para o servidor (as de `prestacao.pendencias` são
escritas para o operador), dizendo quem resolve. Prazos vêm do domínio
(`prazo_para_prestar`), nunca de estimativa.
"""

from __future__ import annotations

from django.db.models import Prefetch
from django.utils import timezone

from gestao.assistencia.ganchos import (
    PendenciaDoServidor,
    PrestacaoDoServidor,
    SituacaoDoServidor,
    ViagemDoServidor,
    registrar_fonte_situacao,
)

from . import anexos, carimbo, diario, prestacao, relatorio
from .dominio.prestacao import prazo_para_prestar
from .dominio.relatorio import listar
from .models import Oficio, PrestacaoServidor, Trecho, Viajante
from .viagem import periodo_curto

EQUIPE, VOCE = "a equipe", "você"
#: (início do texto do operador, código, texto para o servidor, quem resolve)
PENDENCIAS = (
    ("Informe o número da solicitação", "PREST_SEM_SOLICITACAO",
     "número da solicitação de diárias", EQUIPE),
    ("Anexe o despacho", "PREST_SEM_DESPACHO", "despacho assinado do ofício", EQUIPE),
    ("Anexe o comprovante", "PREST_SEM_COMPROVANTE",
     "enviar o comprovante do saque ou da transferência", VOCE),
    (diario.PENDENCIA[:30], "PREST_SEM_DIARIO", "diário de bordo", EQUIPE),
    (relatorio.PENDENCIA[:30], "PREST_SEM_RT", "relatório técnico", EQUIPE),
    (carimbo.PENDENCIA[:30], "PREST_SEM_CARIMBO", "número carimbado no ofício assinado",
     EQUIPE),
    ("Os comprovantes somam", "PREST_VALOR_DIVERGENTE",
     "conferir com a equipe o valor dos comprovantes (diferente da diária)", VOCE),
)


def traduzir(texto_do_operador: str) -> PendenciaDoServidor:
    for inicio, codigo, texto, quem in PENDENCIAS:
        if texto_do_operador.startswith(inicio):
            return PendenciaDoServidor(codigo, texto, quem)
    return PendenciaDoServidor("PREST_OUTRA", "um item da prestação (fale com a equipe)",
                               EQUIPE)


def _trechos_em_ordem(caminho: str) -> Prefetch:
    """Os trechos (com destino) numa consulta para todos os ofícios da lista."""
    return Prefetch(caminho, queryset=Trecho.objects.select_related("destino").order_by("ordem"))


def _destinos_periodo(oficio: Oficio) -> tuple[str, str]:
    trechos = list(oficio.trechos.all())  # já pré-carregados, em ordem
    destinos = list(dict.fromkeys(str(t.destino) for t in trechos
                                  if t.destino_id != oficio.sede_id))
    periodo = (periodo_curto(timezone.localtime(trechos[0].saida_em).date(),
                             timezone.localtime(trechos[-1].chegada_em).date())
               if trechos else "")
    return listar(destinos), periodo


def situacao(servidor_id: int) -> SituacaoDoServidor | None:
    linhas = list(prestacao.ativos(PrestacaoServidor.objects.filter(
        servidor_id=servidor_id, prestacao__oficio__situacao=Oficio.Situacao.EMITIDO))
        .select_related("prestacao__oficio__sede")
        .prefetch_related(_trechos_em_ordem("prestacao__oficio__trechos"))
        .order_by("-prestacao__oficio__ano", "-prestacao__oficio__numero")[:10])
    # A situação dos anexos de todas as prestações numa leitura só (não uma por prestação).
    anexados = anexos.situacao([ps.prestacao_id for ps in linhas]) if linhas else None
    prestacoes = []
    for ps in linhas:
        oficio = ps.prestacao.oficio
        destinos, periodo = _destinos_periodo(oficio)
        finalizada = ps.finalizada_em is not None
        pendencias = () if finalizada else tuple(
            dict.fromkeys(traduzir(p) for p in prestacao.pendencias(ps, anexados)))
        prestacoes.append(PrestacaoDoServidor(
            chave=f"ps:{ps.pk}", oficio=oficio.numero_formatado, destinos=destinos,
            periodo=periodo, liberacao=ps.data_liberacao_diarias,
            prazo_saque=ps.prazo_limite_saque,
            prazo_prestar=prazo_para_prestar(ps.prazo_limite_saque),
            situacao=ps.get_situacao_display(), finalizada=finalizada,
            pendencias=pendencias))
    viagens = []
    for v in (Viajante.objects.filter(servidor_id=servidor_id,
                                      oficio__situacao=Oficio.Situacao.EMITIDO)
              .select_related("oficio__sede")
              .prefetch_related(_trechos_em_ordem("oficio__trechos"))
              .order_by("-oficio__ano", "-oficio__numero")[:10]):
        trechos = list(v.oficio.trechos.all())
        destinos, _ = _destinos_periodo(v.oficio)
        viagens.append(ViagemDoServidor(
            oficio=v.oficio.numero_formatado, destinos=destinos,
            saida=trechos[0].saida_em if trechos else None,
            retorno=trechos[-1].chegada_em if trechos else None,
            situacao=v.oficio.get_situacao_display()))
    if not prestacoes and not viagens:
        return None
    return SituacaoDoServidor(servidor_id=servidor_id, gerada_em=timezone.now(),
                              viagens=tuple(viagens), prestacoes=tuple(prestacoes),
                              fontes=("Prestação de contas", "Ofícios emitidos"))


registrar_fonte_situacao(situacao)
