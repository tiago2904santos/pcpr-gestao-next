"""Regras do controle de publicações da ASCOM, em Python puro (sem Django).

Paridade com o "Relatório de Publicações" da referência: cada pauta entra pela assessoria,
passa por redação, edição e revisão e sai publicada no site (e, às vezes, na AEN). Aqui
ficam os status e as filas, a mudança de status pelo andamento (publicar sem data usa o
agora), a conferência das datas, o tempo até publicar e a leitura de horários escritos à
mão ("17h03", "16h", "17:03").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

# (valor, rótulo, dica, tom do selo) — na ordem da referência.
STATUS: tuple[tuple[str, str, str, str], ...] = (
    ("pendente", "Pendente", "Pauta recebida, ainda sem redação", "aviso"),
    ("em_andamento", "Em andamento", "Em apuração, redação ou edição", "info"),
    ("publicada", "Publicada", "Matéria no ar no site da PCPR", "sucesso"),
    ("cancelada", "Cancelada", "A pauta não vai sair", "perigo"),
)
ROTULOS = {v: r for v, r, _d, _t in STATUS}
DICAS = {v: d for v, _r, d, _t in STATUS}
TONS = {v: t for v, _r, _d, t in STATUS}

PENDENTE, EM_ANDAMENTO, PUBLICADA, CANCELADA = "pendente", "em_andamento", "publicada", "cancelada"
ABERTOS = frozenset({PENDENTE, EM_ANDAMENTO})
ENCERRADOS = frozenset({PUBLICADA, CANCELADA})

FILAS: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("pendentes", "Pendentes", frozenset({PENDENTE})),
    ("andamento", "Em andamento", frozenset({EM_ANDAMENTO})),
    ("publicadas", "Publicadas", frozenset({PUBLICADA})),
    ("canceladas", "Canceladas", frozenset({CANCELADA})),
)

MSG_ESCOLHA = "Escolha o novo status."
MSG_DATA_PUBLICADA = "Informe a data em que a pauta foi publicada."
MSG_ANTES_DA_PAUTA = "A publicação não pode ser anterior à data da pauta."
MSG_UNIDADE = "Escolha a unidade responsável ou informe uma nova."


class RegraViolada(ValueError):
    """Uma regra da pauta foi violada; `campo` diz onde mostrar o erro."""

    def __init__(self, mensagem: str, campo: str | None = None) -> None:
        super().__init__(mensagem)
        self.campo = campo


def conferir_novo_status(atual: str, novo: str) -> None:
    if novo not in ROTULOS or novo == atual:
        raise RegraViolada(MSG_ESCOLHA, "novo_status")


def publicacao_automatica(data_pauta: date, data_publicacao: date | None,
                          horario_publicacao: time | None,
                          agora: datetime) -> tuple[date, time | None]:
    """Ao marcar como publicada sem data, a publicação fica com a data e a hora do
    registro (nunca antes da pauta); dá para corrigir depois na folha. Com data já
    informada, nada muda."""
    if data_publicacao:
        return data_publicacao, horario_publicacao
    return (max(agora.date(), data_pauta),
            horario_publicacao or agora.time().replace(second=0, microsecond=0))


def conferir_datas(status: str, data_pauta: date | None,
                   data_publicacao: date | None) -> None:
    if status == PUBLICADA and not data_publicacao:
        raise RegraViolada(MSG_DATA_PUBLICADA, "data_publicacao")
    if data_pauta and data_publicacao and data_publicacao < data_pauta:
        raise RegraViolada(MSG_ANTES_DA_PAUTA, "data_publicacao")


def tempo_ate_publicar(data_pauta: date | None, inicio: time | None,
                       data_publicacao: date | None, horario: time | None) -> timedelta | None:
    """Do início da pauta à publicação; None se faltar dado ou se a ordem estiver trocada."""
    if not (data_pauta and inicio and data_publicacao and horario):
        return None
    comeco = datetime.combine(data_pauta, inicio)
    fim = datetime.combine(data_publicacao, horario)
    return fim - comeco if fim >= comeco else None


def formatar_duracao(delta: timedelta | None) -> str:
    """"1h25" / "2d 3h" (leitura humana do tempo até publicar)."""
    if delta is None:
        return ""
    total = int(delta.total_seconds() // 60)
    dias, resto = divmod(total, 24 * 60)
    horas, minutos = divmod(resto, 60)
    return f"{dias}d {horas}h" if dias else f"{horas}h{minutos:02d}"


def media(deltas: list[timedelta]) -> timedelta | None:
    return sum(deltas, timedelta()) / len(deltas) if deltas else None


def quando_publicada(data_publicacao: date | None, horario: time | None) -> str:
    if not data_publicacao:
        return ""
    texto = f"Publicada em {data_publicacao:%d/%m/%Y}"
    return texto + (f" às {horario:%H:%M}" if horario else "")


def sim_nao(valor: bool | None) -> str:
    return "" if valor is None else ("Sim" if valor else "Não")


_HORA = re.compile(r"^\s*(\d{1,2})\s*([:hH.])\s*(\d{2})?\s*(?::\d{2})?\s*$")


def ler_hora(texto: str | None) -> time | None:
    """'17h03', '16h', '17:03', '17.03' ou '17:03:00' → time. Inválido → None."""
    if not texto or not texto.strip():
        return None
    m = _HORA.match(texto)
    if not m or (m.group(3) is None and m.group(2) in ":."):
        return None
    hora, minuto = int(m.group(1)), int(m.group(3) or 0)
    if hora > 23 or minuto > 59:
        return None
    return time(hora, minuto)


def uma_linha(texto: str | None) -> str:
    return " ".join((texto or "").split())


def percentual(parte: int, total: int) -> int:
    return round(parte * 100 / total) if total else 0


@dataclass(frozen=True)
class Fato:
    icone: str
    rotulo: str
    texto: str
    ausente: bool = False
