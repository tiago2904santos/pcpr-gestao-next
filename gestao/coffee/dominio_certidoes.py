"""Certidões dos fornecedores em Python puro (CB5a; paridade com `coffee_break/certidoes.py`):
situação de cada uma (faltando, vencida, vencendo em até 15 dias, vigente), a validade lida
do texto do PDF, o tipo reconhecido pelas marcas do texto e a conferência do CNPJ.
Mensagens da referência."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta

TIPOS = (("federal", "Federal"), ("estadual", "Estadual (Paraná)"), ("municipal", "Municipal"),
         ("trabalhista", "Trabalhista"), ("fgts", "FGTS"))
ROTULOS = dict(TIPOS)
PORTAIS = {  # a municipal vem do cadastro do fornecedor
    "federal": "https://servicos.receitafederal.gov.br/servico/certidoes/#/home/cnpj",
    "estadual": "https://cdwfazenda.paas.pr.gov.br/cdwportal/certidao/automatica",
    "trabalhista": "https://cndt-certidao.tst.jus.br/gerarCertidao",
    "fgts": "https://consulta-crf.caixa.gov.br/consultacrf/pages/consultaEmpregador.jsf",
}
DIAS_AVISO = 15
MARCAS = {
    "federal": ("receita federal", "divida ativa da uniao", "tributos federais"),
    "estadual": ("receita estadual", "divida ativa estadual", "secretaria de estado da fazenda"),
    "municipal": ("municip", "prefeitura", "cnd-cidadao"),
    "trabalhista": ("debitos trabalhistas", "cndt"),
    "fgts": ("fgts", "regularidade do empregador"),
}
MSG_IMAGEM = "O PDF é uma imagem: não deu para conferir o conteúdo; vale a data informada."
MSG_ILEGIVEL = ("Não deu para ler este PDF (parece uma imagem). Anexe de novo informando até "
                "quando ele é válido.")
MSG_SEM_VALIDADE = ("Não achei a validade nesta certidão. Anexe de novo informando até quando "
                    "ela é válida.")

_DATA = r"(\d{2})/(\d{2})/(\d{4})"
_VALIDADE = re.compile(r"(?:valid[ao]|validade)[^0-9]{0,40}?" + _DATA
                       + r"(?:\s*(?:a|ate|-)\s*" + _DATA + r")?")
_PRAZO = re.compile(r"(?:valid[ao]|validade)\D{0,30}?(\d{1,3})\s*(?:\([^)]*\)\s*)?dias")
_EMISSAO = re.compile(r"(?:emitid[ao]|emissao|expedid[ao]|expedicao)[^0-9]{0,40}?" + _DATA)
_CNPJ = re.compile(r"\d{2}\.?\d{3}\.?\d{3}(?:/?\d{4}-?\d{2})?")


def limpo(texto: str) -> str:
    sem = unicodedata.normalize("NFKD", texto or "")
    return re.sub(r"\s+", " ", "".join(c for c in sem if not unicodedata.combining(c)).lower())


def _data(d: str, m: str, a: str) -> date | None:
    try:
        return date(int(a), int(m), int(d))
    except ValueError:
        return None


def validade_do_texto(texto: str) -> date | None:
    """"Válida até 17/03/2027"; "Validade: 14/09/2026 a 13/10/2026" (vale o fim);
    "emitida em 01/09/2026 … válida por 90 dias" (prefeituras). None quando não dá."""
    t = limpo(texto)
    candidatas = []
    for achado in _VALIDADE.finditer(t):
        g = achado.groups()
        candidatas.append((_data(*g[3:6]) if g[3] else None) or _data(*g[0:3]))
    datas = [c for c in candidatas if c]
    if datas:
        return max(datas)
    prazo, emissao = _PRAZO.search(t), _EMISSAO.search(t)
    if prazo and emissao and (inicio := _data(*emissao.groups())):
        return inicio + timedelta(days=int(prazo.group(1)))
    return None


def tipos_do_texto(texto: str) -> list[str]:
    t = limpo(texto)
    return [tipo for tipo, marcas in MARCAS.items() if any(m in t for m in marcas)]


def parece_certidao(texto: str) -> bool:
    return bool(re.search(r"\bcertidao\b|\bcertifica", limpo(texto)))


def cnpj_aparece(cnpj: str, texto: str) -> bool:
    """O CNPJ inteiro ou a raiz (8 dígitos) no texto; sem CNPJ cadastrado, não confere."""
    alvo = re.sub(r"\D", "", cnpj or "")
    if not alvo:
        return True
    numeros = {re.sub(r"\D", "", n) for n in _CNPJ.findall(texto or "")}
    return alvo in numeros or alvo[:8] in numeros


@dataclass(frozen=True)
class Conferencia:
    validade: date
    aviso: str = ""


def conferir(texto: str, tipo: str, cnpj: str, razao_social: str, cnpj_formatado: str,
             validade_informada: date | None = None) -> Conferencia:
    """Com texto: do tipo pedido, do CNPJ do fornecedor e com a validade escrita. Só imagem:
    vale a data informada. Erro: ValueError com a mensagem da referência."""
    if not parece_certidao(texto):
        if validade_informada:
            return Conferencia(validade_informada, MSG_IMAGEM)
        raise ValueError(MSG_ILEGIVEL)
    tipos = tipos_do_texto(texto)
    if tipo not in tipos:
        if tipos:
            raise ValueError(f"Este PDF parece ser a certidão {ROTULOS[tipos[0]]}, não a "
                             f"{ROTULOS[tipo]}.")
        raise ValueError(f"Este PDF não parece ser a certidão {ROTULOS[tipo]}.")
    if not cnpj_aparece(cnpj, texto):
        raise ValueError(f"Esta certidão não é de {razao_social}: o CNPJ {cnpj_formatado} não "
                         "aparece nela.")
    validade = validade_do_texto(texto) or validade_informada
    if validade is None:
        raise ValueError(MSG_SEM_VALIDADE)
    return Conferencia(validade)


def situacao(validade: date | None, hoje: date) -> tuple[str, str, str]:
    """(chave, rótulo, tom): faltando, vencida, vencendo (≤ 15 dias), vigente."""
    if validade is None:
        return "faltando", "Faltando", "perigo"
    if validade < hoje:
        return "vencida", f"Vencida em {validade:%d/%m/%Y}", "perigo"
    if (validade - hoje).days <= DIAS_AVISO:
        return "vencendo", f"Vence em {validade:%d/%m/%Y}", "aviso"
    return "vigente", f"Válida até {validade:%d/%m/%Y}", "sucesso"
