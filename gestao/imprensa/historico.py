"""Histórico do atendimento: o registro (trilha de auditoria do banco), as edições dos
campos (salvamentos seguidos da mesma pessoa viram uma linha) e cada andamento com a
anotação. Do mais novo ao mais antigo, no formato das linhas de histórico das folhas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from gestao.plataforma.auditoria import passos_do_registro

from .models import Atendimento

JANELA = timedelta(minutes=20)

# Coluna → nome na tela, na ordem da folha (horário de início e fim viram um nome só).
NOMES = {
    "data": "data do pedido", "horario": "horário do pedido", "jornalista": "jornalista",
    "veiculo_id": "veículo", "contato": "contato", "pedido": "pedido",
    "deadline": "deadline", "responsavel_id": "responsável",
    "fonte": "fontes", "inicio_pedido": "fontes", "final_pedido": "fontes",
    "horario_resposta": "horário da resposta",
    "responsavel_resposta_id": "responsável pela resposta", "resposta": "resposta",
}


@dataclass
class Evento:
    em: datetime
    acao: str  # criado | alterado | andamento
    usuario: object | None
    texto: str = ""
    partes: list[str] = field(default_factory=list)
    situacao: str = ""
    tom: str = ""

    @property
    def descricao(self) -> str:
        if self.partes:
            nomes = self.partes
            junto = nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]
            return "Alterou " + junto
        return self.texto


def do_atendimento(atendimento: Atendimento) -> list[Evento]:
    eventos: list[Evento] = []
    for p in passos_do_registro(Atendimento._meta.db_table, atendimento.pk):
        if p.operacao == "INSERT":
            eventos.append(Evento(p.em, "criado", p.usuario, "Atendimento registrado"))
            continue
        if p.operacao != "UPDATE":
            continue
        partes: list[str] = []
        for coluna, nome in NOMES.items():
            if coluna in p.campos and nome not in partes:
                partes.append(nome)
        if not partes:  # só situação/andamento: aparece pelo Andamento
            continue
        anterior = eventos[-1] if eventos else None
        if (anterior is not None and anterior.acao == "alterado"
                and anterior.usuario == p.usuario and anterior.em - p.em <= JANELA):
            anterior.partes.extend(n for n in partes if n not in anterior.partes)
            ordem = list(dict.fromkeys(NOMES.values()))  # na ordem da folha
            anterior.partes.sort(key=ordem.index)
            continue
        eventos.append(Evento(p.em, "alterado", p.usuario, partes=partes))
    for a in atendimento.andamentos.select_related("usuario"):
        texto = f"Situação: {a.get_situacao_nova_display()}"
        if a.anotacao:
            texto += f" — {a.anotacao}"
        eventos.append(Evento(a.em, "andamento", a.usuario, texto,
                              situacao=a.get_situacao_nova_display()))
    eventos.sort(key=lambda e: e.em, reverse=True)
    return eventos
