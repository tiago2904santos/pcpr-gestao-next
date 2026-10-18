"""Validador de fatos da saída da IA, em Python puro (testável sem modelo e sem banco).

Uma sugestão de texto só passa se:
- não traz dado pessoal (CPF, telefone, e-mail, link) nem nome de pessoa do cadastro;
- todo número (inclusive de data) aparece nos fatos do sistema enviados;
- não fala de dinheiro, diária, quilometragem, viatura ou motorista (o sistema calcula e a
  pessoa escolhe — a IA nunca);
- não cita entidade do catálogo (município, atividade…) que não esteja nos fatos;
- não afirma o que exige dado ("ribeirinhos", "sem intercorrências"…) sem o dado;
- não promete resultado ("garantir", "atenderá todos");
- não cita norma, decreto ou lei sem que estejam nos fatos;
- cita ao menos uma fonte, e só fontes que existem neste pedido.

Devolve códigos (`codigo` ou `codigo:detalhe`); os códigos vão para o registro, o detalhe só
para o conteúdo com retenção.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from gestao.integracoes.ia.protecao import dados_pessoais_em

VEDADOS_PADRAO: dict[str, str] = {
    "valor_monetario": r"r\$|\breais\b|\bcentavos?\b",
    "diaria": r"\bdiarias?\b",
    "quilometragem": r"\bkm\b|\bquilometr|\bquilomet",
    "viatura": r"\bviaturas?\b|\bplaca\b",
    "motorista": r"\bmotoristas?\b",
}
NORMA = r"\bdecretos?\b|\bportarias?\b|\bleis?\b|\bresolu[cç][aã]o\b|\bnormas?\b"
AFIRMACOES = ("ribeirinh", "rural", "indigen", "quilombol", "vulnerab", "dificil acesso",
              "primeira edicao", "grande procura", "alta demanda", "intercorrencia",
              "superou", "recorde")
PROMESSAS = r"\bgarant(?:e|ir|ira|indo|ido)\b|\batender[aá] tod|\bcom certeza\b|\b100 ?%"


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def numeros(texto: str) -> set[str]:
    return {n.lstrip("0") or "0" for n in re.findall(r"\d+", texto or "")}


def _contem(texto_norm: str, termo: str) -> bool:
    termo = normalizar(termo)
    return bool(termo) and re.search(rf"(?<![a-z0-9]){re.escape(termo)}(?![a-z0-9])",
                                     texto_norm) is not None


def validar_texto(texto: str, *, fatos: str, nomes_proibidos: Iterable[str] = (),
                  catalogo: Iterable[str] = (), vedados: dict[str, str] | None = None,
                  max_caracteres: int = 1500) -> list[str]:
    erros: list[str] = []
    bruto = (texto or "").strip()
    if not bruto:
        return ["vazio"]
    if len(bruto) > max_caracteres:
        erros.append("longo_demais")
    t = normalizar(bruto)
    f = normalizar(fatos)
    for achado in dados_pessoais_em(bruto):
        erros.append(f"dado_pessoal:{achado}")
    sem_fonte = sorted(numeros(bruto) - numeros(fatos), key=lambda n: (len(n), n))
    if sem_fonte:
        erros.append("numero_sem_fonte:" + ",".join(sem_fonte[:5]))
    for codigo, padrao in (VEDADOS_PADRAO if vedados is None else vedados).items():
        if re.search(padrao, t) and not re.search(padrao, f):
            erros.append(f"termo_vedado:{codigo}")
    if re.search(NORMA, t) and not re.search(NORMA, f):
        erros.append("norma_sem_fonte")
    for nome in nomes_proibidos:
        partes = normalizar(nome).split()
        if len(partes) >= 2 and (_contem(t, nome) or _contem(t, f"{partes[0]} {partes[-1]}")):
            erros.append("nome_de_pessoa")
            break
    fora = [e for e in catalogo if _contem(t, e) and not _contem(f, e)]
    if fora:
        erros.append("entidade_fora_dos_dados:" + ",".join(sorted(fora)[:3]))
    for termo in AFIRMACOES:
        if termo in t and termo not in f:
            erros.append(f"afirmacao_sem_dado:{termo}")
    if re.search(PROMESSAS, t) and not re.search(PROMESSAS, f):
        erros.append("promessa_de_resultado")
    return erros


def validar_fontes(fontes: Iterable[str], disponiveis: Iterable[str]) -> list[str]:
    fontes = list(fontes)
    if not fontes:
        return ["sem_fonte"]
    fora = [x for x in fontes if x not in set(disponiveis)]
    return ["fonte_inexistente"] if fora else []


def codigo(erro: str) -> str:
    """Só o código (o que vai para a tabela auditada), sem o detalhe."""
    return erro.split(":", 1)[0]
