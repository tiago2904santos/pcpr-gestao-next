"""Histórico da palestra: o registro e as edições (trilha de auditoria do banco; edições
seguidas da mesma pessoa viram uma linha), cada andamento com a anotação e cada resposta
enviada ao solicitante. Do mais novo ao mais antigo, no formato das linhas de histórico."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from gestao.plataforma.auditoria import passos_do_registro

from .models import Palestra

JANELA = timedelta(minutes=20)

NOMES = {
    "data_solicitacao": "pedido", "canal_solicitacao": "pedido", "protocolo": "pedido",
    "solicitante": "solicitante", "telefone": "contato", "email": "contato",
    "assunto_email": "pedido", "pedido_contato": "pedido",
    "informacoes_previas": "informações prévias", "descricao": "descrição",
    "evento": "tipo de evento", "data_inicio_evento": "data do evento",
    "data_fim_evento": "data do evento", "hora_inicio": "horário",
    "municipio_id": "local", "local": "local", "endereco": "local", "bairro": "local",
    "cep": "local", "quantidade_publico": "público",
}
FILHAS = {"palestras_palestra_temas": "temas", "palestras_palestra_palestrantes": "palestrantes"}


@dataclass
class Evento:
    em: datetime
    acao: str  # criado | alterado | andamento | resposta | dg
    usuario: object | None
    texto: str = ""
    partes: list[str] = field(default_factory=list)

    @property
    def descricao(self) -> str:
        if self.partes:
            n = self.partes
            return "Alterou " + (n[0] if len(n) == 1 else ", ".join(n[:-1]) + " e " + n[-1])
        return self.texto


def da_palestra(p: Palestra) -> list[Evento]:
    ordem = list(dict.fromkeys([*NOMES.values(), *FILHAS.values()]))
    eventos: list[Evento] = []
    filhas = dict.fromkeys(FILHAS, "palestra_id")
    for passo in passos_do_registro(Palestra._meta.db_table, p.pk, filhas):
        if passo.operacao == "INSERT":
            eventos.append(Evento(passo.em, "criado", passo.usuario, "Pedido registrado"))
            continue
        if passo.operacao != "UPDATE" or "status" in passo.campos:
            continue  # a mudança de status vem pelo Andamento
        partes = [n for n in ordem if n in {NOMES[c] for c in passo.campos if c in NOMES}
                  | {FILHAS[t] for t in passo.filhas if t in FILHAS}]
        if not partes:
            continue
        anterior = eventos[-1] if eventos else None
        if (anterior is not None and anterior.acao == "alterado"
                and anterior.usuario == passo.usuario and anterior.em - passo.em <= JANELA):
            anterior.partes = [n for n in ordem if n in set(anterior.partes) | set(partes)]
            continue
        eventos.append(Evento(passo.em, "alterado", passo.usuario, partes=partes))
    for a in p.andamentos.select_related("usuario"):
        texto = f"Status: {a.get_status_novo_display()}"
        eventos.append(Evento(a.em, "andamento", a.usuario,
                              f"{texto} — {a.anotacao}" if a.anotacao else texto))
    for r in p.respostas.select_related("usuario"):
        eventos.append(Evento(r.em, "resposta", r.usuario, f"Resposta enviada: {r.tipo}"))
    from .encaminhamento import movimentos_da_dg  # o que a DG fez na solicitação ligada

    for m in movimentos_da_dg(p):
        texto = (f"Solicitação #{m.solicitacao_id} — {m.get_acao_display()}: "
                 f"{m.solicitacao.get_status_display()}")
        eventos.append(Evento(m.em, "dg", m.usuario,
                              f"{texto} — {m.observacao}" if m.observacao else texto))
    eventos.sort(key=lambda e: e.em, reverse=True)
    return eventos
