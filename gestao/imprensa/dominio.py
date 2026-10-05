"""Regras do atendimento à imprensa da ASCOM, em Python puro (sem Django).

Paridade com o "Relatório de atendimento" da referência: as situações do pedido e as filas
da lista, o selo do deadline, a leitura de horários escritos à mão ("17h03", "16h",
"17:03") e as fontes consultadas, que a planilha registra em blocos separados por linha em
branco nas três colunas (fonte, acionamento, retorno) e a tela reúne por posição.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time

# (valor, rótulo, dica, tom do selo) — na ordem da referência.
SITUACOES: tuple[tuple[str, str, str, str], ...] = (
    ("em_andamento", "Em andamento", "Tratando o pedido", "info"),
    ("em_andamento_texto", "Em andamento — texto", "Preparando a resposta por escrito",
     "info"),
    ("em_andamento_video", "Em andamento — vídeo", "Preparando gravação ou entrevista",
     "info"),
    ("aguardando_fonte", "Aguardando fonte", "Esperando a fonte responder", "aviso"),
    ("aguardando_produtora", "Aguardando produtora", "Esperando a produção do veículo",
     "aviso"),
    ("aguardar_nova_solicitacao", "Aguardar nova solicitação",
     "O jornalista vai voltar a pedir", "aviso"),
    ("proximo_mes", "Próximo mês", "Fica para o mês que vem", "neutro"),
    ("atendido", "Atendido", "Resposta enviada ao jornalista", "sucesso"),
    ("nao_responder", "Não responder", "A assessoria não vai atender", "perigo"),
)
ROTULOS = {valor: rotulo for valor, rotulo, _dica, _tom in SITUACOES}
DICAS = {valor: dica for valor, _rotulo, dica, _tom in SITUACOES}
TONS = {valor: tom for valor, _rotulo, _dica, tom in SITUACOES}

ATENDIDO = "atendido"
NAO_RESPONDER = "nao_responder"
AGUARDANDO_FONTE = "aguardando_fonte"
INICIAL = "em_andamento"
ENCERRADAS = frozenset({ATENDIDO, NAO_RESPONDER})
ABERTAS = frozenset(ROTULOS) - ENCERRADAS

# Filas da lista (as abas): chave, rótulo, situações.
FILAS: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("abertos", "Em aberto", ABERTAS),
    ("aguardando", "Aguardando fonte", frozenset({AGUARDANDO_FONTE})),
    ("atendidos", "Atendidos", frozenset({ATENDIDO})),
    ("nao_responder", "Não responder", frozenset({NAO_RESPONDER})),
)

MSG_ESCOLHA = "Escolha a nova situação."
MSG_ATENDIDO = "Para marcar como atendido, escreva o andamento ou registre a resposta enviada."
MSG_DEADLINE = "O deadline não pode ser anterior à data do pedido."


class RegraViolada(ValueError):
    """Uma regra do atendimento foi violada; a mensagem vai para a tela."""


def conferir_andamento(atual: str, nova: str, anotacao: str, resposta: str,
                       andamento_atual: str) -> None:
    """A mudança de situação pelo registro de andamento (regra da referência)."""
    if nova not in ROTULOS or nova == atual:
        raise RegraViolada(MSG_ESCOLHA)
    if nova == ATENDIDO and not (anotacao.strip() or resposta.strip()
                                 or andamento_atual.strip()):
        raise RegraViolada(MSG_ATENDIDO)


def conferir_deadline(data_pedido: date | None, deadline: date | None) -> str:
    """Mensagem de erro do deadline, ou vazio."""
    if data_pedido and deadline and deadline < data_pedido:
        return MSG_DEADLINE
    return ""


@dataclass(frozen=True)
class SeloPrazo:
    texto: str
    tom: str  # perigo | aviso | neutro


def selo_do_deadline(deadline: date | None, situacao: str, hoje: date) -> SeloPrazo | None:
    """O deadline como selo: vencido, hoje, ou a data que vem. Encerrado não tem selo."""
    if deadline is None or situacao in ENCERRADAS:
        return None
    if deadline < hoje:
        return SeloPrazo(f"Deadline vencido em {deadline:%d/%m}", "perigo")
    if deadline == hoje:
        return SeloPrazo("Deadline hoje", "aviso")
    return SeloPrazo(f"Deadline {deadline:%d/%m/%Y}", "neutro")


_HORA = re.compile(r"^\s*(\d{1,2})\s*([:hH.])\s*(\d{2})?\s*(?::\d{2})?\s*$")


def ler_hora(texto: str | None) -> time | None:
    """'17h03', '16h', '17:03', '17.03', '17H03' ou '17:03:00' → time. Inválido → None."""
    if not texto or not texto.strip():
        return None
    m = _HORA.match(texto)
    if not m:
        return None
    if m.group(3) is None and m.group(2) in ":.":  # "17:" sem minutos; só "16h" dispensa
        return None
    hora, minuto = int(m.group(1)), int(m.group(3) or 0)
    if hora > 23 or minuto > 59:
        return None
    return time(hora, minuto)


def _blocos(texto: str | None) -> list[str]:
    partes = (" ".join(p.split()) for p in (texto or "").replace("\r", "").split("\n\n"))
    return [p for p in partes if p]


@dataclass(frozen=True)
class Fonte:
    fonte: str
    inicio: str
    fim: str


def fontes_alinhadas(fontes: str, inicios: str, finais: str) -> list[Fonte]:
    """Cada fonte com os horários de acionamento e de retorno do mesmo bloco."""
    f, i, r = _blocos(fontes), _blocos(inicios), _blocos(finais)
    return [Fonte(nome, i[n] if n < len(i) else "", r[n] if n < len(r) else "")
            for n, nome in enumerate(f)]


def resumo(texto: str, limite: int = 90) -> str:
    """O pedido numa linha, cortado no fim."""
    linha = " ".join((texto or "").split())
    return linha if len(linha) <= limite else linha[:limite - 3].rstrip() + "…"


def uma_linha(texto: str | None) -> str:
    return " ".join((texto or "").split())


def multilinha(texto: str | None) -> str:
    """Apara cada linha e no máximo uma linha em branco seguida (mantém os blocos)."""
    linhas = [" ".join(linha.split()) for linha in (texto or "").replace("\r", "").split("\n")]
    saida: list[str] = []
    for linha in linhas:
        if not linha and (not saida or not saida[-1]):
            continue
        saida.append(linha)
    while saida and not saida[-1]:
        saida.pop()
    return "\n".join(saida)


def percentual(parte: int, total: int) -> int:
    return round(parte * 100 / total) if total else 0


def momento(data_pedido: date, hora: time | None) -> datetime:
    return datetime.combine(data_pedido, hora or time(0, 0))
