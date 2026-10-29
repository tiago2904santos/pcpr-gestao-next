"""Assistente de dúvidas (AUT-88), só leitura e determinístico primeiro.

`responder(pergunta, servidor_id)` devolve `Resposta(texto, fontes, lacunas)`:
- dado individual vem só de `situacao_do_servidor` (o contexto Viagens registra a fonte) e
  apenas do servidor identificado PELO SISTEMA — o texto da pergunta não identifica ninguém;
- orientação geral vem só da Central de ajuda aprovada (`conhecimento.py`), com o selo da
  natureza (procedimento aprovado ou regra do sistema);
- sem fonte, diz o que falta e oferece falar com a equipe; nunca estima data, prazo ou valor;
- recusa ação ("cancele", "troque"…), dado de outra pessoa e assunto sensível (saúde,
  vítima, ocorrência), sem guardar a pergunta.

Não chama IA: a reformulação opcional em linguagem simples é um uso próprio
(`assistencia.reformular_resposta`), com chave, modo e orçamento próprios, e roda no worker.
O canal (portal, WhatsApp) chama `responder` e mostra o texto e as fontes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from django.utils import timezone

from gestao.integracoes.ia.protecao import mascarar

from . import conhecimento, ganchos
from .dominio.validacao import normalizar


@dataclass(frozen=True)
class Fonte:
    tipo: str          # "artigo" | "registro"
    rotulo: str        # "Prazo para prestar contas (AJ-PRAZO-PRESTACAO v1)"
    referencia: str    # slug do artigo ou chave opaca do registro
    natureza: str = ""


@dataclass(frozen=True)
class Resposta:
    texto: str
    fontes: list[Fonte] = field(default_factory=list)
    lacunas: list[str] = field(default_factory=list)
    categoria: str = "orientacao"   # orientacao | dados | lacuna | recusa | sensivel
    sugerir_equipe: bool = False


SENSIVEIS = r"\b(saude|doenca|doente|atestado|cid|licenca medica|hospital|vitima|inquerito|" \
            r"ocorrencia|boletim de ocorrencia|crime|denuncia)\b"
# Pedidos de ação no imperativo ("cancele minha viagem"); "enviei o comprovante?" é dúvida.
ACOES = r"^\s*(?:por favor,?\s+|voce pode\s+|pode\s+)?(cancele|cancela|troque|troca|altere|" \
        r"altera|mude|muda|apague|apaga|exclua|exclui|emita|emite|assine|aprove|envie|" \
        r"cadastre|registre|marque|libere|pague)\b"
TERCEIRO = r"\b(do|da) (colega|outro servidor|outra servidora|meu chefe|minha chefe)\b|" \
           r"\bde outr[ao] (servidor|servidora|pessoa)\b"
INJECAO = r"\bignor\w* (as |todas as )?(regras|instrucoes|instrucao)\b"
PESSOAL = r"\b(minha|meu|minhas|meus|eu|tenho|posso|preciso)\b"
TEMAS = {
    "prazo": r"\b(prazo|vence|vencid\w*|ate quando|quando termina|dias? uteis)\b",
    "pendencias": r"\b(falta\w*|pendenc\w*|pendente|o que preciso|o que tenho)\b",
    "viagens": r"\b(viage\w*|proxima|oficio|destino|quando viajo)\b",
    "diaria": r"\b(diaria\w*|liberad\w*|liberacao|saque|sacar|deposit\w*)\b",
    "situacao": r"\bsituacao\b",
}


def situacao_do_servidor(servidor_id: int) -> ganchos.SituacaoDoServidor | None:
    """A "Minha situação" do servidor, só com os registros dele (vem dos contextos donos do
    dado). A página pública com link pessoal (LinkAcesso) chama esta função."""
    partes = [s for f in ganchos.fontes_situacao() if (s := f(servidor_id)) is not None]
    if not partes:
        return None
    return ganchos.SituacaoDoServidor(
        servidor_id=servidor_id, gerada_em=timezone.now(),
        viagens=tuple(v for s in partes for v in s.viagens),
        prestacoes=tuple(p for s in partes for p in s.prestacoes),
        fontes=tuple(dict.fromkeys(f for s in partes for f in s.fontes)))


def _data(d) -> str:
    return f"{d:%d/%m/%Y}" if d else ""


def _carimbo(s: ganchos.SituacaoDoServidor) -> str:
    return f"Situação em {timezone.localtime(s.gerada_em):%d/%m/%Y %H:%M}."


def _temas(t: str) -> set[str]:
    return {nome for nome, padrao in TEMAS.items() if re.search(padrao, t)}


def _texto_prestacao(p: ganchos.PrestacaoDoServidor, temas: set[str], hoje: date) -> list[str]:
    linhas = []
    cab = f"Ofício {p.oficio} ({p.destinos}{', ' + p.periodo if p.periodo else ''})"
    if p.finalizada:
        return [f"{cab}: prestação finalizada."]
    if {"diaria", "prazo", "situacao"} & temas or not temas & {"pendencias"}:
        if p.liberacao:
            linhas.append(f"{cab}: diárias liberadas em {_data(p.liberacao)}.")
        else:
            linhas.append(f"{cab}: a equipe ainda não registrou a liberação das diárias.")
    else:
        linhas.append(f"{cab}.")
    if {"prazo", "situacao"} & temas or not temas:
        if p.prazo_saque:
            vencido = " (já venceu)" if p.prazo_saque < hoje else ""
            linhas.append(f"Prazo limite de saque: {_data(p.prazo_saque)}{vencido}.")
        if p.prazo_prestar:
            vencido = " (já venceu)" if p.prazo_prestar < hoje else ""
            linhas.append(f"Prazo para prestar contas: {_data(p.prazo_prestar)}{vencido}.")
    if {"pendencias", "situacao"} & temas or not temas:
        suas = [x for x in p.pendencias if x.quem_resolve == "você"]
        da_equipe = [x for x in p.pendencias if x.quem_resolve != "você"]
        if suas:
            linhas.append("Com você: " + "; ".join(x.texto for x in suas) + ".")
        if da_equipe:
            linhas.append("Com a equipe: " + "; ".join(x.texto for x in da_equipe) + ".")
        if not p.pendencias:
            linhas.append("Nenhuma pendência registrada.")
    return linhas


def _responder_situacao(servidor_id: int, temas: set[str]) -> Resposta:
    s = situacao_do_servidor(servidor_id)
    if s is None:
        return Resposta("Não encontrei viagens nem prestações suas registradas no sistema.",
                        lacunas=["sem_registro"], categoria="lacuna", sugerir_equipe=True)
    hoje = timezone.localdate()
    linhas: list[str] = []
    fontes: list[Fonte] = []
    if "viagens" in temas and not ({"prazo", "pendencias", "diaria"} & temas):
        proximas = [v for v in s.viagens if v.saida and timezone.localtime(v.saida).date() >= hoje]
        for v in proximas[:3]:
            linhas.append(f"Ofício {v.oficio}: {v.destinos}, saída em "
                          f"{timezone.localtime(v.saida):%d/%m/%Y às %H:%M}.")
            fontes.append(Fonte("registro", f"Ofício {v.oficio} · trechos", f"oficio:{v.oficio}"))
        if not proximas:
            linhas.append("Você não tem viagem futura em ofício emitido.")
    else:
        abertas = [p for p in s.prestacoes if not p.finalizada] or list(s.prestacoes[:1])
        for p in abertas[:3]:
            linhas.extend(_texto_prestacao(p, temas, hoje))
            fontes.append(Fonte("registro", f"Prestação de contas · Ofício {p.oficio}", p.chave))
        if not abertas:
            linhas.append("Você não tem prestação de contas em aberto.")
    linhas.append(_carimbo(s))
    lacunas = []
    if any(p.liberacao is None and not p.finalizada for p in s.prestacoes):
        lacunas.append("liberacao_nao_registrada")
    return Resposta(" ".join(linhas), fontes=fontes, lacunas=lacunas, categoria="dados")


def _responder_artigo(pergunta: str, publico: str) -> Resposta | None:
    achados = conhecimento.buscar(pergunta, publico=publico)
    if not achados:
        return None
    artigo = achados[0][0]
    fontes = [Fonte("artigo", f"{a.titulo} ({a.referencia})", a.slug, a.rotulo_natureza)
              for a, _ in achados[:2]]
    selo = " (regra do sistema de testes)" if artigo.natureza == "regra_do_sistema" else ""
    return Resposta(f"{artigo.resumo}{selo} Mais em “{artigo.titulo}”, na Central de ajuda.",
                    fontes=fontes, categoria="orientacao")


def responder(pergunta: str, servidor_id: int | None = None, *,
              publico: str = "servidor") -> Resposta:
    texto = " ".join(str(pergunta or "").split())[:1000]
    if not texto:
        return Resposta("Escreva a sua dúvida sobre viagens, diárias, prazos ou prestação de "
                        "contas.", lacunas=["pergunta_vazia"], categoria="lacuna")
    t = normalizar(mascarar(texto))
    if re.search(SENSIVEIS, t):
        return Resposta("Por aqui não tratamos de saúde, vítimas ou ocorrências. Fale "
                        "diretamente com a equipe de viagens.", categoria="sensivel",
                        sugerir_equipe=True)
    if re.search(INJECAO, t):
        return Resposta("Só respondo dúvidas sobre viagens, diárias, prazos e prestação de "
                        "contas, com os dados do sistema.", categoria="recusa")
    if re.search(ACOES, t):
        return Resposta("O assistente só informa: não altera, cancela nem envia nada. Para "
                        "isso, fale com a equipe de viagens.", categoria="recusa",
                        sugerir_equipe=True)
    if re.search(TERCEIRO, t) or "[cpf]" in t:
        return Resposta("Só posso informar a sua própria situação. Dados de outra pessoa, "
                        "só com a equipe de viagens.", categoria="recusa", sugerir_equipe=True)
    temas = _temas(t)
    pessoal = bool(re.search(PESSOAL, t)) and bool(temas)
    if pessoal and servidor_id:
        resposta = _responder_situacao(int(servidor_id), temas)
        artigo = _responder_artigo(texto, publico)
        if artigo and resposta.categoria == "dados":
            resposta.fontes.extend(artigo.fontes[:1])
        return resposta
    artigo = _responder_artigo(texto, publico)
    if pessoal and not servidor_id:
        aviso = ("Para ver a sua situação (prazos, pendências e diárias), use o link pessoal "
                 "que o sistema envia ao seu contato verificado.")
        if artigo:
            return Resposta(f"{artigo.texto} {aviso}", fontes=artigo.fontes,
                            lacunas=["identificacao"], categoria="orientacao")
        return Resposta(aviso, lacunas=["identificacao"], categoria="lacuna")
    if artigo:
        return artigo
    return Resposta("Não encontrei um procedimento aprovado sobre isso. A equipe de viagens "
                    "pode responder.", lacunas=["sem_procedimento"], categoria="lacuna",
                    sugerir_equipe=True)
