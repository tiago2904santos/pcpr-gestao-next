"""Recuperação conservadora dos rascunhos afetados pelo externo fantasma (Lote H).

A auditoria é apenas consultada. Ausência de prova nunca autoriza escolher uma pessoa.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import connection, transaction
from django.db.models import Q

from gestao.plataforma import ambiente
from gestao.plataforma.auditoria import contexto
from gestao.plataforma.models import EventoAuditoria

from .models import Historico, Oficio, Viajante


@dataclass(frozen=True)
class ResultadoRecuperacao:
    oficio_id: int
    aplicavel: bool
    aplicado: bool = False
    motorista_id: int | None = None
    evidencia_id: int | None = None
    selecao_manual: bool = False


def exigir_ambiente_de_recuperacao() -> None:
    nome = str(connection.settings_dict.get("NAME", "")).lower()
    permitido = ambiente.atual() in ambiente.DESTRUTIVOS_PERMITIDOS
    if ambiente.atual() == "preview":
        permitido = "preview" in nome or "demo" in nome
    if not permitido:
        raise ambiente.OperacaoBloqueadaPorAmbiente(
            "A recuperação só pode alterar LAB/DEV/TEST ou PREVIEW com banco identificado "
            "por preview/demo. STAGING e PRODUCTION são somente leitura."
        )


def rascunhos_afetados():
    return Oficio.objects.filter(
        situacao=Oficio.Situacao.RASCUNHO, arquivado_em__isnull=True,
        motorista_externo=Oficio.MotoristaExterno.SERVIDOR,
        motorista_externo_servidor__isnull=True,
    ).order_by("pk")


def _fantasma(dados: dict) -> bool:
    return (dados.get("motorista_externo") == Oficio.MotoristaExterno.SERVIDOR
            and dados.get("motorista_externo_servidor_id") is None)


def _prova_de_motorista(oficio: Oficio, viajantes: list[Viajante]) -> tuple[Viajante, int] | None:
    """Liga a desmarcação à ativação fantasma, recusando alterações posteriores.

    O serviço defeituoso desmarcava a equipe antes de gravar o ofício. A mesma
    requisição e o intervalo entre atualizações do ofício identificam essa operação.
    Sem identificador de requisição, ou se a equipe mudou depois, não inferimos nada.
    """
    eventos = EventoAuditoria.objects.filter(
        tabela=Oficio._meta.db_table, registro_id=str(oficio.pk),
    ).order_by("-id")
    ativacao = next((e for e in eventos if e.operacao == "UPDATE"
                     and _fantasma(e.depois or {})
                     and (e.antes or {}).get("motorista_externo") == ""), None)
    if ativacao is None or not ativacao.requisicao_id:
        return None
    anterior = eventos.filter(id__lt=ativacao.id).first()
    if anterior is None:
        return None
    equipe = EventoAuditoria.objects.filter(tabela=Viajante._meta.db_table).filter(
        Q(antes__oficio_id=oficio.pk) | Q(depois__oficio_id=oficio.pk))
    # Inclusão, remoção ou outra seleção depois da ativação invalida a inferência.
    if equipe.filter(id__gt=ativacao.id).filter(
        Q(operacao__in=["INSERT", "DELETE"]) | Q(alterados__contains=["motorista"])
    ).exists():
        return None
    desmarcados = list(equipe.filter(
        id__gt=anterior.id, id__lt=ativacao.id, operacao="UPDATE",
        antes__motorista=True, depois__motorista=False,
    ))
    if len(desmarcados) != 1:
        return None
    evento = desmarcados[0]
    if evento.requisicao_id != ativacao.requisicao_id:
        return None
    candidato = next((v for v in viajantes if str(v.pk) == evento.registro_id), None)
    if candidato is None or candidato.motorista:
        return None
    antes, depois = evento.antes or {}, evento.depois or {}
    if (antes.get("servidor_id") != candidato.servidor_id
            or depois.get("servidor_id") != candidato.servidor_id
            or set(evento.alterados or []) != {"motorista"}):
        return None
    return candidato, evento.id


def recuperar_rascunho(oficio_id: int, *, aplicar: bool = False) -> ResultadoRecuperacao:
    if aplicar:
        exigir_ambiente_de_recuperacao()
    with transaction.atomic():
        # Mesmo lock dos serviços de edição: revalidar após aguardar outra transação.
        oficio = Oficio.objects.select_for_update().filter(pk=oficio_id).first()
        if oficio is None or not rascunhos_afetados().filter(pk=oficio_id).exists():
            return ResultadoRecuperacao(oficio_id, aplicavel=False)
        viajantes = list(Viajante.objects.select_for_update().filter(oficio=oficio))
        motorista = next((v for v in viajantes if v.motorista), None)
        prova = None
        if motorista is None and oficio.tipo_transporte == Oficio.TipoTransporte.VIATURA:
            prova = _prova_de_motorista(oficio, viajantes)
        restaurado = prova[0] if prova else None
        evidencia_id = prova[1] if prova else None
        escolhido = motorista or restaurado
        selecao_manual = (motorista is None and restaurado is None
                          and oficio.tipo_transporte == Oficio.TipoTransporte.VIATURA)
        resultado = ResultadoRecuperacao(
            oficio_id, aplicavel=True, aplicado=aplicar,
            motorista_id=escolhido.pk if escolhido is not None else None,
            evidencia_id=evidencia_id, selecao_manual=selecao_manual,
        )
        if not aplicar:
            return resultado
        with contexto(usuario_id=None, requisicao_id=f"recuperar_motoristas:{oficio.pk}"):
            oficio.motorista_externo = Oficio.MotoristaExterno.NENHUM
            oficio.motorista_oficio_origem = oficio.motorista_protocolo_origem = ""
            oficio.versao += 1
            oficio.save(update_fields=["motorista_externo", "motorista_oficio_origem",
                                      "motorista_protocolo_origem", "versao", "atualizado_em"])
            if restaurado is not None:
                restaurado.motorista = True
                restaurado.save(update_fields=["motorista"])
            descricao = "Motorista externo sem cadastro removido do rascunho."
            if restaurado:
                descricao += " Motorista da equipe restaurado com evidência de auditoria."
            elif selecao_manual:
                descricao += " Selecione manualmente quem vai dirigir."
            Historico.objects.create(
                oficio=oficio, acao=Historico.Acao.ALTERADO, descricao=descricao,
                dados={"recuperacao": "motorista_externo_fantasma",
                       "motorista_id": resultado.motorista_id, "evidencia_id": evidencia_id,
                       "selecao_manual": selecao_manual},
            )
        return resultado
