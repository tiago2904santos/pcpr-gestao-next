"""Regras das palestras e eventos da ASCOM, em Python puro (sem Django).

Paridade com a planilha "Palestras e Eventos ASCOM" da referência (`demandas_eventos`):
status, tipos de evento e canais; o que cada status pede antes de mudar (Agendada pede data
e palestrante; Atendida pede o público e que o dia do evento já tenha chegado); as etapas
do acompanhamento; a resposta padrão com marcadores; os links de e-mail e WhatsApp; e o
jeito de escrever período, contato, canal e protocolo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, time
from urllib.parse import quote

# (valor, rótulo, dica, tom)
STATUS: tuple[tuple[str, str, str, str], ...] = (
    ("pendente", "Pendente", "Recebida, ainda sem tratativa", "aviso"),
    ("em_andamento", "Em andamento", "Tratando com o solicitante e o palestrante", "info"),
    ("aguardando_retorno", "Aguardando retorno", "Esperando resposta do solicitante", "aviso"),
    ("agendada", "Agendada", "Data e palestrante confirmados", "info"),
    ("atendida", "Atendida", "Palestra ou evento realizado", "sucesso"),
    ("cancelada", "Cancelada", "Não vai acontecer", "perigo"),
)
ROTULOS = {v: r for v, r, _d, _t in STATUS}
DICAS = {v: d for v, _r, d, _t in STATUS}
TONS = {v: t for v, _r, _d, t in STATUS}
PENDENTE, AGUARDANDO, AGENDADA, ATENDIDA, CANCELADA = (
    "pendente", "aguardando_retorno", "agendada", "atendida", "cancelada")
ENCERRADOS = frozenset({ATENDIDA, CANCELADA})
ABERTOS = frozenset(ROTULOS) - ENCERRADOS

TIPOS_EVENTO = (("palestra", "Palestra"), ("pcpr_na_comunidade", "PCPR na Comunidade"),
                ("evento", "Evento"))
CANAIS = (("email", "E-mail"), ("whatsapp", "WhatsApp"), ("protocolo", "Protocolo"),
          ("telefone", "Telefone"), ("presencial", "Presencial"), ("outro", "Outro"))
PROTOCOLO = "protocolo"

# Etapas do acompanhamento, na ordem do fluxo ("aguardando retorno" é uma pausa dentro de
# "em andamento"; cancelada não é etapa).
ETAPAS: tuple[tuple[str, frozenset[str]], ...] = (
    ("Recebida", frozenset({PENDENTE})),
    ("Em andamento", frozenset({"em_andamento", AGUARDANDO})),
    ("Agendada", frozenset({AGENDADA})),
    ("Atendida", frozenset({ATENDIDA})),
)

MSG_ESCOLHA = "Escolha o novo status."
MSG_DATA = "Informe a data do evento."
MSG_DATA_DEPOIS_DO_FIM = "A data do evento não pode ser depois da data final já registrada."
MSG_PALESTRANTE = "Informe o palestrante."
MSG_ANTES_DO_EVENTO = "A palestra só pode ser marcada como atendida depois da data do evento."
MSG_PUBLICO = "Informe a quantidade de público."
MSG_FIM_SEM_INICIO = "Informe a data inicial do evento."
MSG_FIM_ANTES = "A data final não pode ser anterior à inicial."
MSG_PROTOCOLO_VAZIO = "Informe o número do protocolo."
MSG_PROTOCOLO = "O protocolo tem 9 dígitos (00.000.000-0)."
MSG_TELEFONE = "Informe o telefone com DDD: (00) 0000-0000 ou (00) 00000-0000."
MSG_CEP = "O CEP tem 8 dígitos (00000-000)."


class RegraViolada(ValueError):
    """Uma ou mais regras violadas; `campo` diz onde mostrar o erro."""

    def __init__(self, mensagem: str, campo: str | None = None) -> None:
        super().__init__(mensagem)
        self.campo = campo


def ainda_nao_aconteceu(data_inicio: date | None, hoje: date) -> bool:
    return data_inicio is not None and data_inicio > hoje


def opcoes_de_status(atual: str, data_inicio: date | None, hoje: date) -> list[str]:
    """Para onde a palestra pode ir: todos menos o atual; "Atendida" só depois do dia do
    evento."""
    return [v for v, *_ in STATUS
            if v != atual and not (v == ATENDIDA and ainda_nao_aconteceu(data_inicio, hoje))]


@dataclass(frozen=True)
class Faltas:
    data: bool
    palestrante: bool
    publico: bool


def faltas(data_inicio: date | None, tem_palestrante: bool, publico: int | None) -> Faltas:
    """O que falta na palestra para os status que pedem dado (a tela pergunta só isso)."""
    return Faltas(data=data_inicio is None, palestrante=not tem_palestrante,
                  publico=publico is None)


def conferir_andamento(*, atual: str, novo: str, hoje: date, data_inicio: date | None,
                       data_fim: date | None, data_informada: date | None,
                       tem_palestrante: bool, palestrante_informado: bool,
                       publico: int | None, publico_informado: int | None) -> list[str]:
    """Todos os erros da mudança de status (vazio = pode). Regras da referência."""
    if novo not in ROTULOS or novo == atual:
        return [MSG_ESCOLHA]
    erros: list[str] = []
    data = data_inicio
    if novo in (AGENDADA, ATENDIDA) and data_inicio is None:
        if data_informada is None:
            erros.append(MSG_DATA)
        elif data_fim and data_fim < data_informada:
            erros.append(MSG_DATA_DEPOIS_DO_FIM)
        else:
            data = data_informada
    if novo == AGENDADA and not tem_palestrante and not palestrante_informado:
        erros.append(MSG_PALESTRANTE)
    if novo == ATENDIDA:
        if ainda_nao_aconteceu(data, hoje):
            erros.append(MSG_ANTES_DO_EVENTO)
        if publico is None and publico_informado is None:
            erros.append(MSG_PUBLICO)
    return erros


@dataclass(frozen=True)
class Etapa:
    titulo: str
    estado: str  # concluido | atual | pendente


def etapas(status: str) -> list[Etapa]:
    atual = next((i for i, (_t, grupo) in enumerate(ETAPAS) if status in grupo), None)
    saida = []
    for i, (titulo, _grupo) in enumerate(ETAPAS):
        if status == ATENDIDA or (atual is not None and i < atual):
            estado = "concluido"
        elif i == atual:
            estado = "atual"
        else:
            estado = "pendente"
        if i == 1 and status == AGUARDANDO:
            titulo = "Aguardando retorno"
        saida.append(Etapa(titulo, estado))
    return saida


# ------------------------------------------------------------------ resposta padrão
MARCADORES = ("solicitante", "data", "horario", "municipio", "palestrante", "tema")
_MARCADOR = re.compile(r"\{(\w+)\}")


def preencher_resposta(mensagem: str, valores: dict[str, str]) -> str:
    """A mensagem com os marcadores trocados pelos dados da palestra. Marcador desconhecido
    (ou sem dado) fica em branco; chave solta, que não é marcador, fica como está."""
    def trocar(m: re.Match[str]) -> str:
        chave = m.group(1).lower()
        return valores.get(chave, "") or "" if chave in MARCADORES else ""
    return _MARCADOR.sub(trocar, mensagem or "")


def link_email(email: str, assunto: str, texto: str) -> str:
    if not email:
        return ""
    return f"mailto:{email}?subject={quote(assunto)}&body={quote(texto)}"


def link_whatsapp(telefone: str, texto: str) -> str:
    digitos = re.sub(r"\D", "", telefone or "")
    if len(digitos) not in (10, 11):
        return ""
    return f"https://wa.me/55{digitos}?text={quote(texto)}"


# ------------------------------------------------------------------ formatos
def formatar_telefone(texto: str | None) -> str:
    """'41999998888' → '(41) 99999-8888'; vazio → ''; inválido → RegraViolada."""
    digitos = re.sub(r"\D", "", texto or "")
    if not digitos:
        return ""
    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    raise RegraViolada(MSG_TELEFONE, "telefone")


def formatar_cep(texto: str | None) -> str:
    digitos = re.sub(r"\D", "", texto or "")
    if not digitos:
        return ""
    if len(digitos) != 8:
        raise RegraViolada(MSG_CEP, "cep")
    return f"{digitos[:5]}-{digitos[5:]}"


def formatar_protocolo(canal: str, texto: str | None) -> str:
    """Só o canal Protocolo tem número: 9 dígitos, '00.000.000-0'."""
    if canal != PROTOCOLO:
        return ""
    digitos = re.sub(r"\D", "", texto or "")
    if not digitos:
        raise RegraViolada(MSG_PROTOCOLO_VAZIO, "protocolo")
    if len(digitos) != 9:
        raise RegraViolada(MSG_PROTOCOLO, "protocolo")
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}-{digitos[8]}"


def conferir_periodo(inicio: date | None, fim: date | None) -> None:
    if fim and not inicio:
        raise RegraViolada(MSG_FIM_SEM_INICIO, "data_fim_evento")
    if inicio and fim and fim < inicio:
        raise RegraViolada(MSG_FIM_ANTES, "data_fim_evento")


def data_do_evento(inicio: date | None, fim: date | None) -> str:
    if inicio and fim and fim != inicio:
        return f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"
    return f"{inicio:%d/%m/%Y}" if inicio else ""


def periodo_do_evento(inicio: date | None, fim: date | None, hora: time | None,
                      observacao: str) -> str:
    """Data, hora e a observação ("à definir", "manhã") — a observação com números some
    quando já há data (seria a mesma data escrita à mão)."""
    texto = (observacao or "").strip()
    data = data_do_evento(inicio, fim)
    if texto and data and any(c.isdigit() for c in texto):
        texto = ""
    return " · ".join(p for p in (data, f"{hora:%H:%M}" if hora else "", texto) if p)


@dataclass(frozen=True)
class SeloQuando:
    texto: str
    tom: str


def quando(inicio: date | None, fim: date | None, hoje: date) -> SeloQuando | None:
    """Quando o evento acontece — a mesma régua dos termos e roteiros."""
    if not inicio:
        return None
    if (fim or inicio) < hoje:
        return SeloQuando("Realizado", "sucesso")
    if inicio <= hoje:
        return SeloQuando("Acontecendo", "info")
    return SeloQuando("Previsto", "neutro")


def uma_linha(texto: str | None) -> str:
    return " ".join((texto or "").split())
