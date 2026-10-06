"""Regras do painel e das entregas do Coffee Break em Python puro (CB6a; paridade com
`coffee_break/services.py` §8.2): projeção do saldo do lote pelo ritmo dos últimos 3 meses
completos, alerta de vigência (faixas de 30/60/90 dias), "parada há N dias" e os grupos de
"O que fazer hoje". Mensagens da referência."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

DIAS_POR_MES = 30.44
LIMITE_SALDO = 15  # % — sem como projetar, alerta quando o restante fica abaixo disso
FAIXAS_VIGENCIA = (30, 60, 90)
DIAS_PARADA = 7  # a lista mostra "Parada há N dias" a partir daqui

TIPOS_ENTREGA = (("sem_ocorrencia", "Entregue sem ocorrência"), ("atraso", "Atraso na entrega"),
                 ("falta_itens", "Falta de itens"), ("qualidade", "Problema de qualidade"),
                 ("nao_entregue", "Não entregue"), ("outra", "Outra ocorrência"))
ROTULO_ENTREGA = dict(TIPOS_ENTREGA)
MSG_ENTREGA_ANTES = "A entrega se registra a partir do dia do evento."
MSG_DESCREVA = "Descreva a ocorrência: é a base de uma notificação ao fornecedor."


def meses_completos(hoje: date, quantos: int = 3) -> list[tuple[int, int]]:
    """(ano, mês) dos últimos `quantos` meses completos, do mais antigo ao mais novo."""
    saida = []
    primeiro = hoje.replace(day=1)
    for _ in range(quantos):
        primeiro = (primeiro - timedelta(days=1)).replace(day=1)
        saida.append((primeiro.year, primeiro.month))
    return list(reversed(saida))


def ritmo(consumo_por_mes: dict[tuple[int, int], int], hoje: date) -> float:
    """Média mensal dos últimos 3 meses completos (0 quando não há consumo)."""
    meses = meses_completos(hoje)
    return sum(consumo_por_mes.get(m, 0) for m in meses) / len(meses)


@dataclass(frozen=True)
class AlertaSaldo:
    texto: str
    acaba_em: date | None = None


def alerta_de_saldo(restante: int, total: int, ritmo_mensal: float, fim: date | None,
                    hoje: date) -> AlertaSaldo | None:
    """Com ritmo e fim de vigência: se o saldo acaba antes do fim, avisa a data; sem como
    projetar: restante ≤ 15% da capacidade."""
    if not total:
        return None
    if ritmo_mensal > 0 and fim:
        acaba_em = hoje + timedelta(days=round(max(restante, 0) / ritmo_mensal * DIAS_POR_MES))
        if acaba_em < fim:
            ritmo_txt = f"{ritmo_mensal:.1f}".replace(".", ",")
            return AlertaSaldo(
                f"No ritmo dos últimos 3 meses ({ritmo_txt} por mês), os {restante} de saldo "
                f"acabam por volta de {acaba_em:%d/%m/%Y}, antes do fim do contrato "
                f"({fim:%d/%m/%Y}): providencie o aditivo ou o reforço.", acaba_em)
        return None
    if restante * 100 <= total * LIMITE_SALDO:
        return AlertaSaldo(f"Restam apenas {restante} de {total} unidades (limite de alerta: "
                           f"{LIMITE_SALDO}%).")
    return None


def sobra_no_fim(restante: int, ritmo_mensal: float, fim: date | None, hoje: date) -> float | None:
    """Quanto sobra (negativo: falta) no fim da vigência, no ritmo atual."""
    if not fim or ritmo_mensal <= 0:
        return None
    meses = max((fim - hoje).days, 0) / DIAS_POR_MES
    return restante - ritmo_mensal * meses


def alerta_de_vigencia(fim: date | None, hoje: date) -> str:
    if fim is None:
        return ""
    if fim < hoje:
        return (f"Vigência encerrada em {fim:%d/%m/%Y}. Novas solicitações com evento depois "
                "dessa data não são aceitas neste contrato.")
    dias = (fim - hoje).days
    for faixa in FAIXAS_VIGENCIA:
        if dias <= faixa:
            return (f"A vigência termina em {fim:%d/%m/%Y} (em {dias} dias, faixa de {faixa} "
                    "dias). Providencie o aditivo de prorrogação.")
    return ""


def dias_parada(ultimo_movimento: date, fim_evento: date | None, hoje: date) -> int:
    """Desde o último histórico, ou desde o fim do evento se for posterior."""
    referencia = max(ultimo_movimento, fim_evento) if fim_evento else ultimo_movimento
    return max((hoje - referencia).days, 0)


def texto_parada(dias: int) -> str:
    return "Parada hoje" if dias == 0 else f"Parada há {dias} dia{'s' if dias != 1 else ''}"


# "O que fazer hoje": (chave, título, ajuda, rótulo do botão, seção da OS), na ordem do fluxo.
GRUPOS = (
    ("entregas", "Entregas desta semana",
     "Eventos de hoje aos próximos 7 dias: confira o local e quem recebe; no dia, registre a "
     "entrega.", "Abrir a OS", "entrega"),
    ("sem_nota", "Eventos realizados sem nota fiscal",
     "O evento já aconteceu e a nota não chegou.", "Anexar a nota", "pdfs"),
    ("sem_oficio", "Notas sem ofício", "Com nota, falta gerar o ofício ao GAF.",
     "Informar o ofício", "nota"),
    ("sem_protocolo", "Ofícios sem protocolo", "Com ofício, falta abrir o protocolo.",
     "Informar o protocolo", "pagamento"),
    ("sem_ob", "Protocolos sem ordem bancária", "Aguardando a ordem bancária do pagamento.",
     "Registrar a OB", "pagamento"),
    ("ob_nao_enviada", "Ordens bancárias não enviadas à empresa",
     "Falta avisar o fornecedor do pagamento e informar a data do envio.",
     "Informar o envio da OB", "pagamento"),
)
MSG_NADA_PENDENTE = ("Nada pendente com a equipe: nenhuma entrega nos próximos dias e nenhum "
                     "pagamento parado.")


def grupo_de(*, cancelada: bool, concluida: bool, data_evento: date | None, nota: bool,
             oficio: bool, protocolo: bool, ob: bool, hoje: date) -> str | None:
    """Em que grupo de "O que fazer hoje" a OS está (None: nada a fazer agora)."""
    if cancelada or concluida:
        return None
    if ob:
        return "ob_nao_enviada"
    if protocolo:
        return "sem_ob"
    if nota and oficio:
        return "sem_protocolo"
    if nota:
        return "sem_oficio"
    if data_evento and data_evento < hoje:
        return "sem_nota"
    if data_evento and hoje <= data_evento <= hoje + timedelta(days=7):
        return "entregas"
    return None
