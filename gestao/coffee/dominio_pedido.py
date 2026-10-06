"""Regras do pedido de coffee break (a ordem de serviço) em Python puro: escolha do lote pelo
município, saldo, valor em reais, situação financeira, vigência, retroativo e antecedência
(paridade com `coffee_break/services.py`, `forms.py` e `models.py` da referência; mensagens
como lá — ver docs/migration/coffee-break.md §3)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

MSG_SEM_LOTE = ("Nenhum lote ativo atende {municipio}. Inclua o município na lista de um lote "
                "em Cadastros › Lotes.")
MSG_SALDO = "Quantidade acima do saldo do lote: restam {restante} de {total} unidades."
MSG_QUANTIDADE = "A quantidade deve ser de pelo menos 1 unidade."
MSG_VENCIDO = ("Contrato vencido em {fim:%d/%m/%Y}: o contrato {contrato} do {lote} não cobre "
               "um evento em {data:%d/%m/%Y}. Providencie o aditivo de prorrogação ou cadastre "
               "outro lote para o município.")
MSG_RETROATIVO = ('O evento é anterior à data da solicitação. Confira a data ou marque '
                  '"registro retroativo" e justifique.')
MSG_JUSTIFIQUE = "Justifique o registro retroativo."
MSG_JA_CANCELADA = "A solicitação já está cancelada."
MSG_CONCLUIDA_NAO_CANCELA = ("Solicitações com o fluxo financeiro concluído não podem ser "
                             "canceladas.")
MSG_MOTIVO = "Informe o motivo do cancelamento."
MSG_NAO_CANCELADA = "A solicitação não está cancelada."
MSG_EXCLUIR = "A solicitação {numero} já tem nota ou protocolo: cancele em vez de excluir."
MSG_BLOQUEADA = "Solicitações canceladas ou concluídas ficam bloqueadas para edição."
MSG_VERSAO = "Esta solicitação foi alterada por outra pessoa. Recarregue a página antes de salvar."

KM_POR_GRAU = 111.0


@dataclass(frozen=True)
class LoteCandidato:
    """O que a escolha precisa saber de cada lote ativo."""

    id: int
    rotulo: str  # "Lote 1 (2026)"
    exercicio: str
    municipios: frozenset[int]
    fim_vigencia: date | None
    restante: int
    # (município_id, nome, latitude, longitude) das cidades listadas no lote.
    cidades: tuple[tuple[int, str, float | None, float | None], ...] = field(default=())


@dataclass(frozen=True)
class Escolha:
    lote_id: int
    por_proximidade: bool = False
    cidade: str = ""  # "Londrina, a 34 km" quando foi pela mais próxima
    km: int = 0


def _vencido(c: LoteCandidato, data: date) -> bool:
    return bool(c.fim_vigencia and data > c.fim_vigencia)


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine, em km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def escolher_lote(municipio_id: int, lat: float | None, lon: float | None, data: date,
                  candidatos: list[LoteCandidato]) -> Escolha | None:
    """1) Lotes que listam o município: não vencido na data, depois o do exercício do ano da
    data, depois o de maior saldo. 2) Senão, o lote com a cidade listada mais perto em linha
    reta (não vencido, menor distância, exercício do ano). 3) Nenhum: None."""
    ano = str(data.year)
    diretos = [c for c in candidatos if municipio_id in c.municipios]
    if diretos:
        melhor = min(diretos, key=lambda c: (_vencido(c, data), c.exercicio != ano,
                                             -c.restante, c.id))
        return Escolha(melhor.id)
    if lat is None or lon is None:
        return None
    perto: list[tuple[bool, int, bool, int, str, int]] = []
    for c in candidatos:
        for _mid, nome, clat, clon in c.cidades:
            if clat is None or clon is None:
                continue
            km = round(distancia_km(lat, lon, clat, clon))
            perto.append((_vencido(c, data), km, c.exercicio != ano, c.id, nome, c.id))
    if not perto:
        return None
    _venc, km, _ano, _id, nome, lote_id = min(perto)
    return Escolha(lote_id, True, f"{nome}, a {km} km", km)


def quantidade_efetiva(pedida: int | None, faturada: int | None) -> int:
    return faturada if faturada else (pedida or 0)


def valor(quantidade: int, unitario: Decimal | None) -> Decimal | None:
    """Quantidade × valor unitário, a centavo (meio para cima)."""
    if unitario is None:
        return None
    return (Decimal(quantidade) * unitario).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def moeda(v: Decimal | None) -> str:
    if v is None:
        return "—"
    inteiro, _, centavos = f"{v:.2f}".partition(".")
    grupos = f"{int(inteiro):,}".replace(",", ".")
    return f"R$ {grupos},{centavos}"


def percentual_consumido(consumido: int, total: int) -> int:
    return round(consumido * 100 / total) if total else 0


def tom_do_consumo(pct: int) -> str:
    return "perigo" if pct >= 90 else "aviso" if pct >= 70 else "sucesso"


# Situação financeira (derivada, nunca gravada), na ordem dos marcos.
SITUACOES = (
    ("cancelada", "Cancelada", "perigo"),
    ("concluida", "Concluída", "sucesso"),
    ("aguardando_envio", "Aguardando envio à empresa", "info"),
    ("aguardando_ob", "Aguardando ordem bancária", "info"),
    ("aguardando_atesto", "Aguardando atesto", "aviso"),
    ("aguardando_protocolo", "Aguardando protocolo", "aviso"),
    ("aguardando_nota", "Aguardando nota fiscal", "neutro"),
)
ROTULO_SITUACAO = {c: r for c, r, _t in SITUACOES}
TOM_SITUACAO = {c: t for c, _r, t in SITUACOES}


@dataclass(frozen=True)
class Marcos:
    cancelada: bool = False
    nota: bool = False
    protocolo: bool = False
    atesto: bool = False
    ordem_bancaria: bool = False
    envio_empresa: bool = False


def situacao(m: Marcos) -> str:
    if m.cancelada:
        return "cancelada"
    if m.envio_empresa:
        return "concluida"
    if m.ordem_bancaria:
        return "aguardando_envio"
    if m.atesto:
        return "aguardando_ob"
    if m.protocolo:
        return "aguardando_atesto"
    if m.nota:
        return "aguardando_protocolo"
    return "aguardando_nota"


def financeiro_iniciado(m: Marcos) -> bool:
    return any((m.nota, m.protocolo, m.atesto, m.ordem_bancaria, m.envio_empresa))


def conferir_vigencia(fim: date | None, data: date, contrato: str, lote: str) -> None:
    if fim and data > fim:
        raise ValueError(MSG_VENCIDO.format(fim=fim, contrato=contrato, lote=lote, data=data))


def conferir_retroativo(evento: date | None, pedido: date, retroativo: bool,
                        justificativa: str) -> None:
    if evento and evento < pedido:
        if not retroativo:
            raise ValueError(MSG_RETROATIVO)
        if not justificativa.strip():
            raise ValueError(MSG_JUSTIFIQUE)


def aviso_antecedencia(evento: date | None, hoje: date, minimo: int, contrato: str) -> str:
    """Aviso (não bloqueia): evento com menos dias que a antecedência do contrato."""
    if not evento or evento < hoje:
        return ""
    dias = (evento - hoje).days
    if dias >= minimo:
        return ""
    quando = "hoje" if dias == 0 else "amanhã" if dias == 1 else f"em {dias} dias"
    return (f"O evento é {quando} ({evento:%d/%m/%Y}), com menos que os {minimo} dias de "
            f"antecedência do contrato {contrato}: ligue para o fornecedor para confirmar o "
            "atendimento.")


def formatar_numero(texto: str, ano: int) -> str:
    """"41" → "41/2026"; "41/2025" fica como está."""
    texto = (texto or "").strip()
    if not texto:
        return ""
    if "/" in texto:
        seq, _, a = texto.partition("/")
        return f"{int(seq)}/{a.strip()}" if seq.strip().isdecimal() else texto
    if not texto.isdecimal():
        return texto
    if int(texto) < 1:
        raise ValueError("O número da OS deve ser 1 ou mais.")
    return f"{int(texto)}/{ano}"


def sequencia(numero: str) -> tuple[int, int] | None:
    """"41/2026" → (2026, 41)."""
    seq, _, ano = (numero or "").partition("/")
    if seq.strip().isdecimal() and ano.strip().isdecimal():
        return int(ano), int(seq)
    return None


# ---------------------------------------------------------------- fluxo financeiro (CB3)
# Os marcos na ordem do fluxo: (campo, etapa no stepper, rótulo, tipo).
MARCOS = (
    ("nota_fiscal", "Nota fiscal", "Número da nota fiscal", "texto"),
    ("protocolo_pagamento", "Protocolo", "Protocolo de pagamento", "texto"),
    ("atesto_em", "Atesto", "Atesto e envio ao GAF em", "data"),
    ("ordem_bancaria_em", "Ordem bancária", "Ordem bancária emitida em", "data"),
    ("envio_empresa_em", "Paga", "OB enviada à empresa em", "data"),
)
MSG_SEM_MARCO = "Esta solicitação não tem marco a registrar."
MSG_PROTOCOLO_VAZIO = "Informe o número do protocolo aberto no eProtocolo."
MSG_PROTOCOLO_FORMATO = "O número do protocolo deve estar no formato 00.000.000-0."
MSG_NOTA_OBRIGATORIA = ("O protocolo de pagamento já foi registrado: a nota não pode ficar em "
                        "branco.")
MSG_SO_CONCLUIDA = "Só solicitações concluídas são reabertas para correção."
MSG_JA_EM_CORRECAO = "A solicitação já está aberta para correção."
MSG_MOTIVO_CORRECAO = "Informe o motivo da correção."
MSG_NAO_EM_CORRECAO = "A solicitação não está aberta para correção."


def erros_dos_marcos(nota: str, protocolo: str, atesto: date | None, ob: date | None,
                     envio: date | None) -> dict[str, str]:
    """A ordem dos marcos (mensagens da referência), por campo."""
    erros: dict[str, str] = {}
    if protocolo and not nota:
        erros["protocolo_pagamento"] = "Informe a nota fiscal antes do protocolo de pagamento."
    if atesto and not protocolo:
        erros["atesto_em"] = "Informe o protocolo de pagamento antes do atesto."
    if ob and not atesto:
        erros["ordem_bancaria_em"] = "Informe o atesto antes da ordem bancária."
    if envio and not ob:
        erros["envio_empresa_em"] = ("Informe a emissão da ordem bancária antes do envio à "
                                     "empresa.")
    if atesto and ob and ob < atesto:
        erros["ordem_bancaria_em"] = "A ordem bancária não pode ser anterior ao atesto."
    if ob and envio and envio < ob:
        erros["envio_empresa_em"] = ("O envio à empresa não pode ser anterior à emissão da "
                                     "ordem bancária.")
    return erros


def formatar_protocolo(texto: str | None) -> str:
    """9 dígitos → 00.000.000-0; vazio → ""; outro formato → ValueError."""
    digitos = "".join(c for c in (texto or "") if c.isdigit() and c.isascii())
    if not digitos:
        return ""
    if len(digitos) != 9:
        raise ValueError(MSG_PROTOCOLO_FORMATO)
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}-{digitos[8]}"


def _feito(valor) -> bool:
    return bool(valor.strip()) if isinstance(valor, str) else valor is not None


def etapas(valores: dict, cancelada: bool) -> list[tuple[str, str]]:
    """O stepper: (título, estado) — um marco conta como feito quando ele ou um posterior
    está preenchido; o atual é o próximo (nada é atual em cancelada)."""
    feitos = [_feito(valores.get(campo)) for campo, *_ in MARCOS]
    ultimo = max((i for i, f in enumerate(feitos) if f), default=-1)
    saida = [("Pedido", "concluido")]
    for i, (_campo, titulo, *_r) in enumerate(MARCOS):
        estado = ("concluido" if i <= ultimo
                  else "atual" if i == ultimo + 1 and not cancelada else "pendente")
        saida.append((titulo, estado))
    return saida


def proximo_marco(valores: dict, cancelada: bool) -> tuple[str, str, str] | None:
    """(campo, rótulo, tipo) do marco que falta, ou None quando acabou (ou cancelada)."""
    if cancelada:
        return None
    feitos = [_feito(valores.get(campo)) for campo, *_ in MARCOS]
    ultimo = max((i for i, f in enumerate(feitos) if f), default=-1)
    if ultimo + 1 >= len(MARCOS):
        return None
    campo, _titulo, rotulo, tipo = MARCOS[ultimo + 1]
    return campo, rotulo, tipo


def texto_faturada(pedida: int, antes: int | None, depois: int | None) -> str:
    """O histórico da quantidade faturada (o saldo do lote acompanha)."""
    if depois == antes:
        return ""
    if depois is None:
        return f"Quantidade faturada removida: o lote volta a descontar as {pedida} pedidas."
    if depois < pedida:
        return (f"Quantidade faturada: {depois} de {pedida} pedidas; {pedida - depois} "
                "voltaram ao saldo do lote.")
    if depois > pedida:
        return (f"Quantidade faturada: {depois} de {pedida} pedidas; {depois - pedida} a mais "
                "saíram do saldo do lote.")
    return f"Quantidade faturada: {depois} de {pedida} pedidas."
