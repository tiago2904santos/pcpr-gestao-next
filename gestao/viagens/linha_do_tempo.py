"""Histórico de termos e ordens de serviço, lido da trilha de auditoria do banco.

O ofício tem um histórico de negócio próprio (`Historico`); termos e OS não precisam de
outro: cada salvamento já fica na trilha (trigger), com quem, quando e o que mudou. Aqui a
trilha vira frases curtas — "Alterou destinos e período", "Cancelada — motivo" — no mesmo
formato das linhas do histórico do ofício (`oficios/_evento.html`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from gestao.plataforma.auditoria import Passo, passos_do_registro

from .models import OrdemServico, OrdemServicoDestino, TermoAutorizacao, TermoDestino

# Salvamentos seguidos da mesma pessoa (o autosave grava a cada pausa) viram uma linha só.
JANELA = timedelta(minutes=20)


@dataclass
class Evento:
    em: datetime
    acao: str  # criado | alterado | cancelado | reativado | documento
    usuario: object | None
    texto: str = ""
    partes: list[str] = field(default_factory=list)

    @property
    def descricao(self) -> str:
        if self.partes:
            return "Alterou " + _juntar_nomes(self.partes)
        return self.texto


def _juntar_nomes(nomes: list[str]) -> str:
    return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]


def _partes(passo: Passo, campos: dict[str, str], filhas: dict[str, str]) -> list[str]:
    """Os nomes do que mudou, na ordem da tela, sem repetir (início e fim = "período")."""
    vistos: list[str] = []
    for chave, nome in campos.items():
        if chave in passo.campos and nome not in vistos:
            vistos.append(nome)
    for tabela, nome in filhas.items():
        if tabela in passo.filhas and nome not in vistos:
            vistos.append(nome)
    return vistos


def _eventos(passos: list[Passo], *, criado: str, cancelado: str, reativado: str,
             campos: dict[str, str], filhas: dict[str, str]) -> list[Evento]:
    eventos: list[Evento] = []
    for p in passos:  # do mais novo ao mais antigo
        if p.operacao == "INSERT":
            eventos.append(Evento(p.em, "criado", p.usuario, criado))
            continue
        if p.operacao != "UPDATE":
            continue
        if "situacao" in p.campos:
            if p.depois.get("situacao") in ("cancelada", "cancelado"):
                motivo = (p.depois.get("motivo_cancelamento") or "").strip()
                texto = f"{cancelado} — {motivo}" if motivo else cancelado
                eventos.append(Evento(p.em, "cancelado", p.usuario, texto))
            else:
                eventos.append(Evento(p.em, "reativado", p.usuario, reativado))
            continue
        if "documento_gerado_em" in p.campos and not p.antes.get("documento_gerado_em"):
            eventos.append(Evento(p.em, "documento", p.usuario,
                                  "Documento gerado pela primeira vez"))
        partes = _partes(p, campos, filhas)
        if not partes:
            continue
        anterior = eventos[-1] if eventos else None
        if (anterior is not None and anterior.acao == "alterado"
                and anterior.usuario == p.usuario and anterior.em - p.em <= JANELA):
            anterior.partes.extend(n for n in partes if n not in anterior.partes)
            continue
        eventos.append(Evento(p.em, "alterado", p.usuario, partes=partes))
    return eventos


def _m2m(modelo, campo: str) -> tuple[str, str]:
    """(tabela da relação, coluna que aponta para o registro)."""
    relacao = modelo._meta.get_field(campo).remote_field.through
    return relacao._meta.db_table, f"{modelo._meta.model_name}_id"


MARCOS = ("situacao", "documento_gerado_em")


def da_ordem(ordem: OrdemServico) -> list[Evento]:
    oficios, servidores = _m2m(OrdemServico, "oficios"), _m2m(OrdemServico, "servidores")
    destinos = (OrdemServicoDestino._meta.db_table, "ordem_id")
    filhas = {oficios[0]: "ofícios", destinos[0]: "destinos", servidores[0]: "equipe"}
    campos = {"tipo": "tipo de necessidade", "data_inicio": "período", "data_fim": "período",
              "funcoes": "funções da equipe", "motivo": "motivo",
              "assinante_id": "quem assina", "data_documento": "data do documento"}
    passos = passos_do_registro(OrdemServico._meta.db_table, ordem.pk,
                                dict([oficios, destinos, servidores]), marcos=MARCOS)
    return _eventos(passos, criado="Ordem de serviço criada", cancelado="Cancelada",
                    reativado="Reativada", campos=campos, filhas=filhas)


def do_termo(termo: TermoAutorizacao) -> list[Evento]:
    servidores = _m2m(TermoAutorizacao, "servidores")
    destinos = (TermoDestino._meta.db_table, "termo_id")
    filhas = {destinos[0]: "destinos", servidores[0]: "servidores"}
    campos = {"oficio_id": "ofício vinculado", "evento": "evento", "data_inicio": "período",
              "data_fim": "período", "viatura_id": "viatura"}
    passos = passos_do_registro(TermoAutorizacao._meta.db_table, termo.pk,
                                dict([destinos, servidores]), marcos=MARCOS)
    return _eventos(passos, criado="Termo criado", cancelado="Cancelado",
                    reativado="Reativado", campos=campos, filhas=filhas)
