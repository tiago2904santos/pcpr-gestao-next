"""Leitura do release (ou do pedido de divulgação) em Python puro (P2; comportamento da
referência, `publicacoes/preenchimento.py` §2.5 — implementação própria): data e início da
pauta (os do envio), o título (o sugerido em "Sugestão de título:", a linha em CAIXA ALTA que
abre o texto, o assunto sem "RES:"/"Release -"/"Para divulgação:", ou a primeira frase), a
unidade (só sugestão: a cadastrada citada; sem cadastro, o nome do remetente vai para "Outra
unidade") e a fonte (quem assina: "Del. Fulano", "Informações: escrivão Fulano"). Nada grava."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time

from gestao.plataforma import leitura_email as le

TITULO_MAX = 300
_R_SUGESTAO = re.compile(r"^\s*(?:sugestao de titulo|titulo sugerido|titulo)\s*:\s*(.+)$")
_R_PREFIXO = re.compile(r"^\s*(?:release|para divulgacao|divulgacao|pauta|sugestao de pauta"
                        r"|pedido de divulgacao)\s*[-:–]\s*", re.IGNORECASE)
_R_CARGO = re.compile(r"^(?:del(?:egad[oa])?\.?|inv(?:estigador[a]?)?\.?|esc(?:rivao|riva)?\.?"
                      r"|agente|ag\.|perito|papiloscopista|dr\.|dra\.)\s+[a-z]")
_R_INFORMACOES = re.compile(r"\b(?:informacoes|informacao|contato|fonte)\s*:\s*(.+)$")


@dataclass
class Leitura:
    data: date | None = None
    inicio: time | None = None
    titulo: str = ""
    unidade_id: int | None = None
    unidade_texto: str = ""
    fonte: str = ""

    @property
    def vazia(self) -> bool:
        return not (self.titulo or self.fonte)


def _limpar(texto: str) -> str:
    return " ".join(texto.split()).strip(" .;:-–")


def titulo(texto_corpo: str, assunto: str) -> str:
    linhas = [x for x in texto_corpo.splitlines() if x.strip()]
    for linha in linhas:  # "Sugestão de título: …"
        m = _R_SUGESTAO.match(le.dobrar(linha))
        if m:
            return _limpar(linha[m.start(1):])[:TITULO_MAX]
    for linha in linhas[:4]:  # a linha em CAIXA ALTA que abre o release
        letras = [c for c in linha if c.isalpha()]
        if len(letras) >= 12 and all(c.isupper() for c in letras):
            return _limpar(linha)[:TITULO_MAX]
    limpo = _R_PREFIXO.sub("", assunto or "")
    if len(_limpar(limpo)) >= 12:
        return _limpar(limpo)[:TITULO_MAX]
    for linha in linhas:  # a primeira frase com corpo
        d = le.dobrar(linha).strip()
        if len(d) >= 30 and not d.startswith(("bom dia", "boa tarde", "boa noite", "ola",
                                              "prezad", "segue", "encaminho")):
            return _limpar(re.split(r"(?<=[.!?])\s", linha.strip())[0])[:TITULO_MAX]
    return ""


def fonte(texto: str) -> str:
    """Quem assina: a linha de cargo ("Del. Fulano") na assinatura ou no corpo, ou o que vem
    depois de "Informações:"."""
    for linha in [*le.assinatura(texto), *reversed(texto.splitlines())]:
        d = le.dobrar(linha).strip()
        if _R_CARGO.match(d):
            return _limpar(linha)[:200]
        m = _R_INFORMACOES.search(d)
        if m and len(m.group(1)) >= 5:
            return _limpar(linha.strip()[m.start(1) - (len(linha) - len(linha.lstrip())):])[:200]
    return ""


def unidade(texto: str, cab: dict[str, str],
            unidades: list[tuple[int, str]]) -> tuple[int | None, str]:
    d = le.dobrar(texto)
    achados = [(len(nome), pk) for pk, nome in unidades
               if len(nome) >= 3 and re.search(r"\b" + re.escape(le.dobrar(nome)) + r"\b", d)]
    if achados:
        return max(achados)[1], ""
    nome = le.nome_do_remetente(cab.get("de") or cab.get("from") or "")
    return None, nome[:150]


def ler(texto: str, agora: datetime, unidades: list[tuple[int, str]]) -> Leitura:
    texto = (texto or "")[:20000]
    cab = le.cabecalhos(texto)
    enviado = le.enviado_em(cab)
    corpo = le.corpo(texto)
    t = titulo(corpo, le.assunto(cab))
    uid, utexto = unidade(f"{le.assunto(cab)}\n{texto}", cab, unidades)
    f = fonte(texto)
    return Leitura(
        data=(enviado or agora).date() if (t or f) else None,
        inicio=enviado.time() if enviado and (enviado.hour or enviado.minute) else None,
        titulo=t, unidade_id=uid, unidade_texto=utexto, fonte=f)
