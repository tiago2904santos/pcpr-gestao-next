"""Regras da solicitação de evento social, em Python puro (sem Django).

Paridade com `solicitacoes/{models,services,permissions,presenters}.py` da referência
(docs/migration/eventos-sociais.md): status e transições, o que o envio à DG exige, as
regras do despacho, quando dá para marcar como atendida, o selo de tempo do evento e o
"pedido em cima da hora". Mensagens como na referência.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

# (valor, rótulo, tom)
STATUS: tuple[tuple[str, str, str], ...] = (
    ("rascunho", "Rascunho", "neutro"),
    ("aguardando_despacho", "Aguardando despacho", "aviso"),
    ("devolvida", "Devolvida para correção", "aviso"),
    ("deferida", "Deferida — em andamento", "info"),
    ("atendida", "Atendida", "sucesso"),
    ("nao_atendida", "Não atendida", "perigo"),
    ("cancelada", "Cancelada", "perigo"),
)
ROTULOS = {v: r for v, r, _t in STATUS}
TONS = {v: t for v, _r, t in STATUS}
RASCUNHO, AGUARDANDO, DEVOLVIDA, DEFERIDA = ("rascunho", "aguardando_despacho", "devolvida",
                                             "deferida")
ATENDIDA, NAO_ATENDIDA, CANCELADA = "atendida", "nao_atendida", "cancelada"
FINAIS = frozenset({ATENDIDA, NAO_ATENDIDA, CANCELADA})
EDITAVEIS = frozenset({RASCUNHO, DEVOLVIDA})

TRANSICOES: dict[str, frozenset[str]] = {
    RASCUNHO: frozenset({AGUARDANDO}),
    AGUARDANDO: frozenset({DEFERIDA, NAO_ATENDIDA, CANCELADA, DEVOLVIDA, AGUARDANDO}),
    DEVOLVIDA: frozenset({AGUARDANDO, CANCELADA}),
    DEFERIDA: frozenset({ATENDIDA, CANCELADA, AGUARDANDO}),
}

# Decisão da DG → status.
DECISOES: tuple[tuple[str, str, str], ...] = (
    ("atender", "Atender", DEFERIDA),
    ("nao_atender", "Não atender", NAO_ATENDIDA),
    ("cancelado", "Evento cancelado", CANCELADA),
    ("devolver", "Enviar para correção", DEVOLVIDA),
)
STATUS_DA_DECISAO = {d: s for d, _r, s in DECISOES}
ROTULO_DA_DECISAO = {d: r for d, r, _s in DECISOES}

ANTECEDENCIA_MINIMA = 10  # dias: abaixo disso, "pedido em cima da hora"

MSG_TRANSICAO = "Transição de {de} para {para} não é permitida."
MSG_SO_RASCUNHO_OU_DEVOLVIDA = "Apenas rascunhos ou solicitações devolvidas podem ser enviados."
MSG_CAMPOS = "Preencha os campos obrigatórios antes de enviar: {lista}."
MSG_SERVICO = "Selecione ao menos um serviço para enviar a solicitação."
MSG_EQUIPE = "Designe ao menos uma equipe para enviar à DG."
MSG_QUANTIDADE = "Informe a quantidade de servidores de {equipes} para enviar à DG."
MSG_UNIDADE_MOVEL = "Informe qual unidade móvel vai ao evento."
MSG_DECISAO = "Selecione a decisão da DG."
MSG_OBS_OBRIGATORIA = "A observação é obrigatória para não atendimento ou cancelamento."
MSG_MOTIVO_DEVOLUCAO = "Informe brevemente o que o solicitante deve corrigir."
MSG_SO_AGUARDANDO = "Somente solicitações aguardando despacho podem receber decisão da DG."
MSG_FINALIZADA = "A solicitação já foi finalizada e não aceita novo despacho."
MSG_ATENDIDA_ANTES = ("A solicitação só pode ser marcada como atendida depois que o evento "
                      "terminar (após {data}).")
MSG_MOTIVO_CANCELAMENTO = "Informe o motivo do cancelamento do evento."
MSG_SO_EM_ANDAMENTO = "Apenas solicitações em andamento podem ser canceladas."
MSG_FIM_ANTES = "A data de fim não pode ser anterior à data de início."
MSG_PROTOCOLO = "O protocolo tem 9 dígitos (00.000.000-0)."

CAMPOS_DO_ENVIO: tuple[tuple[str, str], ...] = (
    ("data_solicitacao", "Data da solicitação"), ("data_inicio_evento", "Início do evento"),
    ("data_fim_evento", "Fim do evento"), ("tipo_evento", "Tipo de evento"),
    ("municipio", "Município"), ("solicitante_nome", "Solicitante"),
    ("solicitante_cargo_unidade", "Cargo / unidade"), ("orgao_responsavel", "Órgão responsável"),
)


class RegraViolada(ValueError):
    def __init__(self, mensagem: str, campo: str | None = None) -> None:
        super().__init__(mensagem)
        self.campo = campo


def conferir_transicao(de: str, para: str) -> None:
    if para not in TRANSICOES.get(de, frozenset()):
        raise RegraViolada(MSG_TRANSICAO.format(de=ROTULOS.get(de, de),
                                                para=ROTULOS.get(para, para)))


@dataclass(frozen=True)
class DadosDoEnvio:
    preenchidos: dict[str, bool]  # campo → tem valor
    servicos: int
    equipes: dict[str, int | None]  # nome da equipe → quantidade
    tipo_operacao: str
    unidade_movel: bool
    unidade_movel_designada: bool


def erros_do_envio(status: str, d: DadosDoEnvio) -> list[str]:
    """Tudo o que impede enviar à DG (vazio = pode)."""
    if status not in EDITAVEIS:
        return [MSG_SO_RASCUNHO_OU_DEVOLVIDA]
    erros = []
    faltando = [rotulo for campo, rotulo in CAMPOS_DO_ENVIO if not d.preenchidos.get(campo)]
    if not d.tipo_operacao:
        faltando.append("Tipo de operação")
    if faltando:
        erros.append(MSG_CAMPOS.format(lista=", ".join(faltando)))
    if d.servicos < 1:
        erros.append(MSG_SERVICO)
    if not d.equipes:
        erros.append(MSG_EQUIPE)
    else:
        sem = [nome for nome, q in d.equipes.items() if not q or q < 1]
        if sem:
            erros.append(MSG_QUANTIDADE.format(equipes=", ".join(sem)))
    if d.unidade_movel and not d.unidade_movel_designada:
        erros.append(MSG_UNIDADE_MOVEL)
    return erros


def conferir_despacho(status: str, decisao: str, observacao: str) -> str:
    """O status que a decisão produz; ou RegraViolada com a mensagem da referência."""
    if status in FINAIS:
        raise RegraViolada(MSG_FINALIZADA)
    if status != AGUARDANDO:
        raise RegraViolada(MSG_SO_AGUARDANDO)
    if decisao not in STATUS_DA_DECISAO:
        raise RegraViolada(MSG_DECISAO, "decisao")
    if decisao in ("nao_atender", "cancelado") and not observacao.strip():
        raise RegraViolada(MSG_OBS_OBRIGATORIA, "observacao")
    if decisao == "devolver" and not observacao.strip():
        raise RegraViolada(MSG_MOTIVO_DEVOLUCAO, "observacao")
    return STATUS_DA_DECISAO[decisao]


def pode_concluir(status: str, fim_do_evento: date | None, hoje: date) -> str:
    """'' se pode marcar como atendida; senão a mensagem."""
    if status != DEFERIDA:
        return MSG_TRANSICAO.format(de=ROTULOS.get(status, status), para=ROTULOS[ATENDIDA])
    if fim_do_evento is None or fim_do_evento >= hoje:
        data = f"{fim_do_evento:%d/%m/%Y}" if fim_do_evento else "o fim do evento"
        return MSG_ATENDIDA_ANTES.format(data=data)
    return ""


def conferir_cancelamento(status: str, motivo: str) -> None:
    if status not in (AGUARDANDO, DEVOLVIDA, DEFERIDA):
        raise RegraViolada(MSG_SO_EM_ANDAMENTO)
    if not motivo.strip():
        raise RegraViolada(MSG_MOTIVO_CANCELAMENTO, "motivo")


def conferir_periodo(inicio: date | None, fim: date | None) -> None:
    if inicio and fim and fim < inicio:
        raise RegraViolada(MSG_FIM_ANTES, "data_fim_evento")


def formatar_protocolo(texto: str | None) -> str:
    digitos = re.sub(r"\D", "", texto or "")
    if not digitos:
        return ""
    if len(digitos) != 9:
        raise RegraViolada(MSG_PROTOCOLO, "protocolo")
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}-{digitos[8]}"


@dataclass(frozen=True)
class Selo:
    texto: str
    tom: str


def selo_de_tempo(inicio: date | None, fim: date | None, status: str, hoje: date) -> Selo | None:
    """Quando o evento acontece; "Evento em N dias" (perigo ≤ 3, aviso ≤ 7) só enquanto a
    decisão não saiu (rascunho, aguardando, devolvida)."""
    if not inicio:
        return None
    ultimo = fim or inicio
    if ultimo < hoje:
        return Selo("Realizado", "sucesso")
    if inicio <= hoje:
        return Selo("Acontecendo", "info")
    faltam = (inicio - hoje).days
    if status in (RASCUNHO, AGUARDANDO, DEVOLVIDA):
        texto = "Evento amanhã" if faltam == 1 else f"Evento em {faltam} dias"
        tom = "perigo" if faltam <= 3 else ("aviso" if faltam <= 7 else "neutro")
        return Selo(texto, tom)
    return Selo("Previsto", "neutro")


def em_cima_da_hora(pedido: date | None, inicio: date | None) -> str:
    """"Pedido em cima da hora (N dias antes / no dia do evento)" — menos de 10 dias."""
    if not (pedido and inicio):
        return ""
    dias = (inicio - pedido).days
    if dias >= ANTECEDENCIA_MINIMA or dias < 0:
        return ""
    quando = "no dia do evento" if dias == 0 else ("1 dia antes" if dias == 1
                                                   else f"{dias} dias antes")
    return f"Pedido em cima da hora ({quando})"


@dataclass(frozen=True)
class Etapa:
    titulo: str
    estado: str  # concluido | atual | pendente


def etapas(status: str) -> list[Etapa]:
    """Enviar para a DG → Aguardando despacho → Deferida → Atendimento do evento (com o
    rótulo final quando terminou)."""
    ordem = [RASCUNHO, AGUARDANDO, DEFERIDA, ATENDIDA]
    titulos = ["Enviar para a DG", "Aguardando despacho DG", "Deferida — em andamento",
               "Atendimento do evento"]
    if status in (NAO_ATENDIDA, CANCELADA):
        titulos[3] = ROTULOS[status]
        return [Etapa(t, "concluido" if i < 2 else ("atual" if i == 3 else "pendente"))
                for i, t in enumerate(titulos)]
    atual = ordem.index(AGUARDANDO if status == DEVOLVIDA else status)
    if status == ATENDIDA:
        return [Etapa(t, "concluido") for t in titulos]
    return [Etapa(t, "concluido" if i < atual else ("atual" if i == atual else "pendente"))
            for i, t in enumerate(titulos)]
