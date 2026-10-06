"""A viagem que nasce de uma solicitação de evento deferida (E4; paridade com
`solicitacoes/integracao_viagens.py` da referência). Viagens conhece Eventos; o contrário
não — Eventos chama pelos ganchos (`gestao.eventos.ganchos`), registrados no `ready`.

O que a viagem traz da solicitação: título (município e data), período, destino, motivo
com o número da solicitação (o fio que liga as duas), descrição e o tipo de viagem com o
nome do tipo de evento, quando existe. O que a solicitação não sabe — quem vai, em que
viatura, o percurso — fica para os documentos da viagem.

Decisões do agente (a confirmar, docs/migration/decisoes.md): aqui não há "ambiente" por
setor; a viagem é de uma unidade, escolhida na geração (sugerida pela equipe designada com
o mesmo nome/sigla da unidade, senão a lotação de quem gera). A geração é um botão da folha
deferida (DG ou quem cria viagens), não automática; o roteiro e os anexos ficam para a
viagem (não são copiados).

Quando a solicitação não vai mais acontecer (não atendida ou cancelada), a viagem sem
documento é cancelada junto; com documento, a equipe de viagens da unidade é avisada.
"""

from __future__ import annotations

import logging
import unicodedata
from functools import partial
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import TipoViagem, Unidade
from gestao.eventos import dominio as dominio_eventos
from gestao.eventos import ganchos, solicitacoes
from gestao.eventos import policies as eventos_policies
from gestao.eventos.models import Solicitacao
from gestao.plataforma.notificacoes import notificar, usuarios_do_grupo

from . import policies
from .models import Viagem, ViagemDestino
from .viagem import TIPOS_DE_DOCUMENTO

logger = logging.getLogger(__name__)


def _chave(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def pode_gerar(usuario) -> bool:
    """A DG, que deferiu, ou quem cria viagens (referência: `pode_gerar_viagem`)."""
    return (usuario.has_perm("eventos.despachar_solicitacao")
            or policies.pode_criar_viagem(usuario))


def unidades_para(usuario):
    """A DG e quem vê todas as unidades escolhem qualquer unidade ativa; os demais, a sua."""
    if usuario.has_perm("eventos.despachar_solicitacao") or policies.ve_todas_unidades(usuario):
        return Unidade.objects.filter(ativo=True).order_by("sigla", "nome")
    propria = policies.unidade_do_usuario(usuario)
    return Unidade.objects.filter(pk=propria.pk) if propria else Unidade.objects.none()


def unidade_sugerida(usuario, s: Solicitacao, unidades) -> Unidade | None:
    nomes = {_chave(e.equipe.nome) for e in s.equipes.select_related("equipe")}
    for u in unidades:
        if nomes & {_chave(u.sigla), _chave(u.nome)} - {""}:
            return u
    propria = policies.unidade_do_usuario(usuario)
    return next((u for u in unidades if propria and u.pk == propria.pk), None)


def viagens_da_solicitacao(s: Solicitacao) -> list[Viagem]:
    return list(Viagem.objects.filter(solicitacoes_de_evento__solicitacao=s)
                .select_related("unidade").distinct().order_by("pk"))


def motivo_que_impede(s: Solicitacao) -> str:
    if s.status != dominio_eventos.DEFERIDA:
        return "A viagem nasce do deferimento: a solicitação precisa estar deferida."
    if not s.municipio_id:
        return "A solicitação não tem município definido."
    if not s.data_inicio_evento:
        return "A solicitação não tem data de início do evento."
    if any(not v.cancelada for v in viagens_da_solicitacao(s)):
        return "Esta solicitação já tem viagem gerada."
    return ""


def tem_documentos(viagem: Viagem) -> bool:
    return any(getattr(viagem, t).exists() for t in TIPOS_DE_DOCUMENTO)


def resumo(usuario, s: Solicitacao) -> dict[str, Any]:
    viagens = viagens_da_solicitacao(s)
    unidades = list(unidades_para(usuario)) if pode_gerar(usuario) else []
    sugerida = unidade_sugerida(usuario, s, unidades) if unidades else None
    return {
        "viagens": [{"viagem": v, "url": (reverse("viagens:editar_viagem", args=[v.pk])
                                          if policies.pode_ver_viagem(usuario, v) else ""),
                     "documentos": tem_documentos(v)} for v in viagens],
        "pode_gerar": bool(unidades) and not motivo_que_impede(s),
        "motivo": motivo_que_impede(s), "unidades": unidades,
        "sugerida": sugerida.pk if sugerida else None,
    }


def _equipe_de_viagens(unidade_id: int):
    return (usuarios_do_grupo("OPERADOR_VIAGENS").filter(lotacao__unidade=unidade_id)
            | usuarios_do_grupo("GESTOR_VIAGENS").filter(lotacao__unidade=unidade_id))


def _motivo(s: Solicitacao) -> str:
    partes = [p for p in ((s.tipo_evento.nome if s.tipo_evento else ""), s.local_evento) if p]
    texto = " — ".join(partes) or "Atendimento de solicitação de evento"
    return f"{texto} (Solicitação #{s.pk})"


@transaction.atomic
def gerar(usuario, s: Solicitacao, unidade_id: int | None) -> Viagem:
    if not pode_gerar(usuario):
        raise PermissionDenied
    s = Solicitacao.objects.select_for_update(of=("self",)).select_related(
        "municipio", "tipo_evento").get(pk=s.pk)
    if not eventos_policies.pode_ver(usuario, s):
        raise PermissionDenied
    motivo = motivo_que_impede(s)
    if motivo:
        raise ValueError(motivo)
    unidade = unidades_para(usuario).filter(pk=unidade_id).first() if unidade_id else None
    if unidade is None:
        raise ValueError("Escolha a unidade responsável pela viagem.")
    if s.municipio is None or s.data_inicio_evento is None:  # conferido acima
        raise ValueError(motivo_que_impede(s))
    inicio = s.data_inicio_evento
    viagem = Viagem.objects.create(
        unidade=unidade, criado_por=usuario,
        titulo=f"{s.municipio.nome}/{s.municipio.uf} — {inicio:%d/%m/%Y}",
        motivo=_motivo(s), descricao=(s.descricao_complementar or "").strip(),
        data_inicio=inicio, data_fim=s.data_fim_evento or inicio)
    ViagemDestino.objects.create(viagem=viagem, municipio=s.municipio, ordem=0)
    if s.tipo_evento:
        alvo = _chave(s.tipo_evento.nome)
        viagem.tipos.set([t for t in TipoViagem.objects.filter(ativo=True)
                          if _chave(t.nome) == alvo])
    solicitacoes.registrar_viagem(usuario, s.pk, viagem.pk,
                                  f"Viagem #{viagem.pk} gerada para {unidade}")
    transaction.on_commit(lambda: notificar(
        _equipe_de_viagens(unidade.pk), f"Viagem gerada da Solicitação #{s.pk}",
        f"{viagem.titulo}: monte a equipe e os documentos.",
        reverse("viagens:editar_viagem", args=[viagem.pk]), exceto=usuario))
    logger.info("Viagem %s gerada da solicitação %s.", viagem.pk, s.pk)
    return viagem


def encerrar(usuario, s: Solicitacao, motivo: str = "") -> str:
    """A solicitação não vai mais acontecer: cancela a viagem sem documento; com documento,
    avisa a equipe de viagens da unidade (desfazer papel oficial é decisão dela)."""
    viagens = [v for v in viagens_da_solicitacao(s) if not v.cancelada]
    if not viagens:
        return ""
    texto = f"Solicitação #{s.pk} {s.get_status_display().lower()}"
    if motivo:
        texto = f"{texto}: {motivo}"
    resultado = "cancelada"
    for v in viagens:
        if not tem_documentos(v):
            v.situacao_anterior, v.situacao = v.situacao, Viagem.Situacao.CANCELADA
            v.motivo_cancelamento, v.cancelado_em = texto[:1000], timezone.now()
            v.save(update_fields=["situacao", "situacao_anterior", "motivo_cancelamento",
                                  "cancelado_em", "atualizado_em"])
            continue
        transaction.on_commit(partial(
            _avisar_documentos, v.unidade_id, f"Viagem #{v.pk}: {texto}"[:150],
            reverse("viagens:editar_viagem", args=[v.pk]), usuario))
        resultado = "avisada"
    return resultado


def _avisar_documentos(unidade_id: int, titulo: str, link: str, usuario) -> None:
    notificar(_equipe_de_viagens(unidade_id), titulo,
              "A viagem já tem documentos e não foi cancelada; confira e cancele pela viagem "
              "se for o caso.", link, exceto=usuario)


def registrar() -> None:
    ganchos.registrar_viagem(ganchos.IntegracaoViagem(resumo=resumo, gerar=gerar,
                                                      encerrar=encerrar))
