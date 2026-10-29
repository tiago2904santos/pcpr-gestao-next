"""Chaves de liga/desliga: geral, por canal e por fluxo. Sem linha = desligada.

`permissao_de_efeito(canal, fluxo)` responde antes de cada efeito novo (reservar um envio,
associar um arquivo automaticamente). Registrar o que já aconteceu nunca passa por aqui.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from . import policies
from .models import ChaveAutomacao

GERAL = "geral"


def nome_canal(canal: str) -> str:
    return f"canal:{canal}"


def nome_fluxo(fluxo: str) -> str:
    return f"fluxo:{fluxo}"


@dataclass(frozen=True)
class Permissao:
    permitido: bool
    motivo: str = ""
    modo: str = ChaveAutomacao.Modo.ASSISTIDO


def _estados(nomes: list[str]) -> dict[str, ChaveAutomacao]:
    return {c.nome: c for c in ChaveAutomacao.objects.filter(nome__in=nomes)}


def permissao_de_efeito(canal: str | None, fluxo: str) -> Permissao:
    """Geral + canal (se houver) + fluxo, todos ligados; o modo é o do fluxo."""
    nomes = [GERAL, *([nome_canal(canal)] if canal else []), nome_fluxo(fluxo)]
    chaves = _estados(nomes)
    rotulos = {GERAL: "A automação está", nome_fluxo(fluxo): "Este fluxo está"}
    if canal:
        rotulos[nome_canal(canal)] = "O canal está"
    for nome in nomes:
        chave = chaves.get(nome)
        estado = chave.estado if chave else ChaveAutomacao.Estado.DESLIGADA
        if estado != ChaveAutomacao.Estado.LIGADA:
            texto = "bloqueado" if estado == ChaveAutomacao.Estado.BLOQUEADA else "desligado"
            return Permissao(False, f"{rotulos[nome]} {texto}.")
    return Permissao(True, "", chaves[nome_fluxo(fluxo)].modo)


def bloqueios(canal: str, fluxos) -> tuple[str, list[str]]:
    """Para o painel, numa consulta: (o que para TUDO no canal, fluxos desligados)."""
    fluxos = list(fluxos)
    estados = _estados([GERAL, nome_canal(canal), *(nome_fluxo(f) for f in fluxos)])

    def situacao(nome: str) -> str:
        chave = estados.get(nome)
        return chave.estado if chave else ChaveAutomacao.Estado.DESLIGADA

    for nome, sujeito in ((GERAL, "A automação está"), (nome_canal(canal), "O canal está")):
        estado = situacao(nome)
        if estado != ChaveAutomacao.Estado.LIGADA:
            texto = "bloqueado" if estado == ChaveAutomacao.Estado.BLOQUEADA else "desligado"
            if nome == GERAL:
                texto = texto[:-1] + "a"
            return f"{sujeito} {texto}.", []
    return "", [f for f in fluxos if situacao(nome_fluxo(f)) != ChaveAutomacao.Estado.LIGADA]


def geral_ligada() -> bool:
    return ChaveAutomacao.objects.filter(nome=GERAL,
                                         estado=ChaveAutomacao.Estado.LIGADA).exists()


def modo_do_fluxo(fluxo: str) -> str:
    chave = ChaveAutomacao.objects.filter(nome=nome_fluxo(fluxo)).first()
    return chave.modo if chave else ChaveAutomacao.Modo.ASSISTIDO


@transaction.atomic
def alterar(usuario, nome: str, *, estado: str, modo: str | None = None,
            motivo: str = "") -> ChaveAutomacao:
    policies.exigir(policies.pode_administrar(usuario),
                    "Só quem administra a automação liga ou desliga chaves.")
    if estado not in ChaveAutomacao.Estado.values:
        raise ValueError("Estado inválido.")
    if modo is not None and modo not in ChaveAutomacao.Modo.values:
        raise ValueError("Modo inválido.")
    if not (nome == GERAL or nome.startswith(("canal:", "fluxo:"))) or len(nome) > 80:
        raise ValueError("Chave inválida.")
    chave, _ = ChaveAutomacao.objects.select_for_update().get_or_create(nome=nome)
    chave.estado = estado
    if modo is not None:
        chave.modo = modo
    chave.motivo = (motivo or "").strip()[:255]
    chave.alterada_por = usuario
    chave.save()
    if nome == GERAL:
        from . import eventos

        eventos.publicar("automacao.religada" if estado == ChaveAutomacao.Estado.LIGADA
                         else "automacao.desligada",
                         {"tipo": "chave_automacao", "id": chave.pk, "versao": 1},
                         {"fluxo": None}, correlacao=f"chave-{chave.pk}")  # nulo = geral
    return chave


def desligar_tudo(usuario, motivo: str) -> ChaveAutomacao:
    """O botão de emergência: a chave geral desligada para todos os efeitos novos."""
    return alterar(usuario, GERAL, estado=ChaveAutomacao.Estado.DESLIGADA,
                   motivo=motivo or f"Desligada em {timezone.localtime():%d/%m %H:%M}")


def bloquear_canal(canal: str, motivo: str) -> None:
    """Problema da conta (token vencido, conta restrita): o próprio worker bloqueia."""
    chave, _ = ChaveAutomacao.objects.get_or_create(nome=nome_canal(canal))
    if chave.estado != ChaveAutomacao.Estado.BLOQUEADA:
        chave.estado = ChaveAutomacao.Estado.BLOQUEADA
        chave.motivo = motivo[:255]
        chave.alterada_por = None
        chave.save()
