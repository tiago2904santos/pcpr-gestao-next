"""Regras puras da automação (sem Django): telefone E.164, ordem dos status de entrega,
palavras-chave das mensagens recebidas, espera entre tentativas e janela de 24 h.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timedelta

DDI_BRASIL = "55"
JANELA_DE_ATENDIMENTO = timedelta(hours=24)
MAX_RODADAS = 3                      # envio: no máximo 3 rodadas automáticas
ESPERA_BASE = timedelta(minutes=2)   # 2, 8, 32 min (4^n)

# ---------------------------------------------------------------- telefone


def somente_digitos(valor: str | None) -> str:
    return re.sub(r"[^0-9]", "", valor or "")


def e164_do_brasil(telefone: str | None) -> str:
    """`41999990000` (DDD + número, como o cadastro guarda) → `5541999990000`.

    Aceita o número já com 55. Devolve vazio quando não é um telefone brasileiro plausível:
    DDD de 11 a 99 e 8 ou 9 dígitos de número (9 só para celular, começando por 9)."""
    digitos = somente_digitos(telefone)
    if len(digitos) in (12, 13) and digitos.startswith(DDI_BRASIL):
        digitos = digitos[2:]
    if len(digitos) not in (10, 11):
        return ""
    ddd, numero = digitos[:2], digitos[2:]
    if not 11 <= int(ddd) <= 99 or ddd[1] == "0":
        return ""
    if len(numero) == 9 and not numero.startswith("9"):
        return ""
    if numero == numero[0] * len(numero):
        return ""
    return DDI_BRASIL + digitos


def variantes(e164: str) -> set[str]:
    """As formas com e sem o 9º dígito de um celular brasileiro: a Meta pode devolver o
    `wa_id` de um jeito e a pessoa estar cadastrada de outro (referência, seção 2)."""
    digitos = somente_digitos(e164)
    saida = {digitos} if digitos else set()
    if digitos.startswith(DDI_BRASIL):
        local = digitos[2:]
        if len(local) == 11 and local[2] == "9":
            saida.add(DDI_BRASIL + local[:2] + local[3:])
        elif len(local) == 10 and local[2] in "6789":
            saida.add(DDI_BRASIL + local[:2] + "9" + local[2:])
    return saida


def mesmo_numero(a: str, b: str) -> bool:
    return bool(a and b and variantes(a) & variantes(b))


# ---------------------------------------------------------------- status de entrega
#: Ordem do que a Meta informa. Nunca regride: um `delivered` atrasado não desfaz o `read`.
ORDEM = {"": 0, "aceita": 1, "enviada": 2, "entregue": 3, "lida": 4}
DA_META = {"sent": "enviada", "delivered": "entregue", "read": "lida", "played": "lida",
           "failed": "falhou"}


def proxima_entrega(atual: str, recebido: str) -> str:
    """Novo estado de entrega dado o atual e o status que chegou (fora de ordem é normal).

    - `failed` só vale se nada indica que chegou: com `entregue`/`lida`, a mensagem chegou
      a pelo menos um aparelho e o `failed` é de outro (referência, seção 5);
    - os demais só avançam."""
    if recebido == "falhou":
        return "falhou" if ORDEM.get(atual, 0) < ORDEM["entregue"] else atual
    if atual == "falhou":
        return recebido if ORDEM.get(recebido, 0) >= ORDEM["entregue"] else atual
    return recebido if ORDEM.get(recebido, 0) > ORDEM.get(atual, 0) else atual


# ---------------------------------------------------------------- tentativas


def espera(rodada: int, sugerida_segundos: int | None = None) -> timedelta:
    """Depois da rodada n (1, 2, …): 2 min, 8 min, 32 min — ou o que o provedor pediu."""
    if sugerida_segundos:
        return timedelta(seconds=min(max(sugerida_segundos, 6), 3600))
    return ESPERA_BASE * (4 ** max(0, rodada - 1))


def janela_aberta(ultima_mensagem_recebida: datetime | None, agora: datetime) -> bool:
    """Dentro de 24 h da última mensagem da pessoa, vale texto livre; fora, só modelo."""
    return bool(ultima_mensagem_recebida
                and agora - ultima_mensagem_recebida < JANELA_DE_ATENDIMENTO)


# ---------------------------------------------------------------- mensagens recebidas
SAIR = frozenset({"sair", "parar", "pare", "cancelar", "stop", "descadastrar"})
ACEITO = frozenset({"aceito", "sim aceito", "concordo", "aceito participar"})
AJUDA = frozenset({"ajuda", "menu", "oi", "ola", "bom dia", "boa tarde", "boa noite"})


def _normal(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", sem_acento.lower()).split())


def intencao(texto: str) -> str:
    """Palavra-chave de uma mensagem curta: `sair`, `aceito`, `ajuda` ou vazio (texto livre
    vai para uma pessoa). Só a mensagem inteira conta: "não quero sair" não é `sair`."""
    normal = _normal(texto)
    if normal in SAIR:
        return "sair"
    if normal in ACEITO:
        return "aceito"
    if normal in AJUDA:
        return "ajuda"
    return ""


def nome_seguro(nome: str, extensao: str) -> str:
    """Nome de arquivo recebido sem caminho nem caracteres estranhos (o original é dado da
    pessoa, nunca caminho de disco)."""
    base = unicodedata.normalize("NFKD", (nome or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1])
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip(".-")[:80]
    raiz = base.rsplit(".", 1)[0] if "." in base else base
    return f"{raiz or 'arquivo'}{extensao}"


LIMITE_CHAVE = 200  # Idempotency-Key e Recebimento.chave: até 200 caracteres (contrato)


def chave_recebimento(canal: str, mensagem_id: str, indice: int) -> str:
    """`receb:<canal>:<mensagem_id>:<anexo>`; se passar de 200 caracteres (o id do canal pode ter
    até 300), `receb#sha256:<canal>:<hex do id>:<anexo>` — a mesma regra do contrato v1 e dos
    workflows do n8n. O `#` no 1º segmento impede que um id curto reproduza a forma com hash."""
    bruta = f"receb:{canal}:{mensagem_id}:{indice}"
    # só ASCII imprimível: mede igual ao `.length` do JS no n8n (emoji = 2) e cabe no cabeçalho
    if len(bruta) <= LIMITE_CHAVE and bruta.isascii() and bruta.isprintable():
        return bruta
    return f"receb#sha256:{canal}:{hashlib.sha256(mensagem_id.encode()).hexdigest()}:{indice}"
