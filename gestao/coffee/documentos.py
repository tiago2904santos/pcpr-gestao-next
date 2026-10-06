"""Documentos do Coffee Break (CB4; paridade com `coffee_break/documentos.py` da referência,
docs/migration/coffee-break.md §5): ordem de serviço, ofício ao GAF (um por pagamento, com um
item por OS e as notas no plural), certifico digital (um por nota) e o certificado da
solicitação (espelho do registro). Cada um diz o que falta (pendências que bloqueiam) e sai
em PDF (WeasyPrint) ou em prévia HTML. Todo PDF que sai fica guardado como via emitida (a
folha igual à última não gera outra); a via assinada vale no lugar do gerado até ser
removida."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date

from django.template.loader import render_to_string
from django.utils import timezone

from . import conjunto
from .models import ConfiguracaoOficio, Solicitacao

MESES = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro")
MSG_SEM_MOTOR = "O gerador de PDF (WeasyPrint) não está disponível neste servidor."
ATESTO = ("que os serviços e/ou bens acima identificados foram devidamente executados/entregues "
          "e atendem às exigências especificadas no (Termo de Referência/Edital).")

UNIDADES = ("zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove",
            "dez", "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete",
            "dezoito", "dezenove")
DEZENAS = ("", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta",
           "oitenta", "noventa")
CENTENAS = ("", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos",
            "setecentos", "oitocentos", "novecentos")


def _ate_mil(n: int) -> str:
    if n == 100:
        return "cem"
    partes = []
    c, resto = divmod(n, 100)
    if c:
        partes.append(CENTENAS[c])
    if resto:
        if resto < 20:
            partes.append(UNIDADES[resto])
        else:
            d, u = divmod(resto, 10)
            partes.append(DEZENAS[d] + (f" e {UNIDADES[u]}" if u else ""))
    return " e ".join(partes)


def extenso(n: int) -> str:
    """Inteiro por extenso (até 999.999): 40 → "quarenta", 1250 → "mil duzentos e
    cinquenta"."""
    if n < 20:
        return UNIDADES[max(n, 0)]
    milhar, resto = divmod(n, 1000)
    if not milhar:
        return _ate_mil(resto)
    inicio = "mil" if milhar == 1 else f"{_ate_mil(milhar)} mil"
    if not resto:
        return inicio
    liga = " e " if resto < 100 or resto % 100 == 0 else " "
    return f"{inicio}{liga}{_ate_mil(resto)}"


def data_por_extenso(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def juntar(itens: list[str]) -> str:
    """"8952", "8952 e 8954", "8950, 8952 e 8954"."""
    itens = [str(i).strip() for i in itens if str(i).strip()]
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + " e " + itens[-1]


@dataclass(frozen=True)
class Tipo:
    chave: str
    titulo: str
    prefixo: str
    template: str


TIPOS = {t.chave: t for t in (
    Tipo("os", "Ordem de serviço", "OS", "coffee/pdf/ordem_servico.html"),
    Tipo("oficio", "Ofício ao GAF", "Of.", "coffee/pdf/oficio.html"),
    Tipo("certifico", "Certifico digital", "CERTIFICO DIGITAL", "coffee/pdf/certifico.html"),
    Tipo("certificado", "Certificado da solicitação", "Certificado",
         "coffee/pdf/certificado.html"),
)}
ASSINAVEIS = ("os", "oficio", "certifico")


def pendencias(tipo: str, s: Solicitacao) -> list[str]:
    """O que impede o documento de sair (mensagens da referência)."""
    if tipo == "os":
        faltas = []
        if not s.numero:
            faltas.append("Informe o número da solicitação (é o número da OS).")
        if not s.local_entrega.strip():
            faltas.append("Informe o local de entrega.")
        if not s.responsavel.strip():
            faltas.append("Informe o responsável pelo recebimento.")
        return faltas
    if tipo == "oficio":
        faltas = [f"Informe o número da nota fiscal{'' if m.pk == s.pk else f' da {m}'}."
                  for m in conjunto.membros(s) if not m.nota_fiscal.strip()]
        if not s.numero_oficio.strip():
            faltas.append("Informe o número do ofício.")
        return faltas
    if tipo == "certifico":
        return [] if s.nota_fiscal.strip() else ["Informe o número da nota fiscal."]
    return []


def detalhamento(s: Solicitacao) -> str:
    """"Solicito coffee para: Dia 01/10 às 9h30 p/ 40 pessoas."."""
    quando = f"Dia {s.data_evento:%d/%m}" if s.data_evento else "Data a combinar"
    hora = f" às {s.horario.hour}h{s.horario.minute:02d}" if s.horario else ""
    return f"Solicito coffee para:\n{quando}{hora} p/ {s.quantidade} pessoas."


def contexto(tipo: str, s: Solicitacao) -> dict:
    lote = s.lote
    contrato = lote.contrato
    cfg = ConfiguracaoOficio.atual()
    hoje = timezone.localdate()
    ctx = {"s": s, "lote": lote, "contrato": contrato, "fornecedor": contrato.fornecedor,
           "cfg": cfg, "referencia": contrato.referencia_documental, "tipo": TIPOS[tipo],
           "destinatario": [linha for linha in cfg.destinatario.splitlines() if linha.strip()]}
    if tipo == "os":
        ctx.update(data=data_por_extenso(s.data_solicitacao), detalhamento=detalhamento(s))
    elif tipo == "oficio":
        grupo = conjunto.membros(s)
        notas = [m.nota_fiscal for m in grupo if m.nota_fiscal]
        ctx.update(data=data_por_extenso(s.data_oficio or hoje), notas=juntar(notas),
                   varias_notas=len(notas) > 1,
                   itens=[{"s": m, "extenso": extenso(m.quantidade_efetiva)} for m in grupo])
    elif tipo == "certifico":
        ctx.update(atesto=ATESTO)
    else:
        def fmt(v) -> str:
            return f"{v:%d/%m/%Y}" if isinstance(v, date) else (v or "Pendente")
        ctx.update(emitido_em=timezone.localtime(), marcos=tuple((r, fmt(v)) for r, v in (
            ("Nota fiscal", s.nota_fiscal), ("Protocolo de pagamento", s.protocolo_pagamento),
            ("Atesto e envio ao GAF", s.atesto_em), ("Ordem bancária", s.ordem_bancaria_em),
            ("Envio à empresa", s.envio_empresa_em))))
    return ctx


def html(tipo: str, s: Solicitacao, *, nonce: str = "", tela: bool = False) -> str:
    return render_to_string(TIPOS[tipo].template,
                            {**contexto(tipo, s), "nonce": nonce, "tela": tela})


def gerar_pdf(tipo: str, s: Solicitacao) -> tuple[bytes, str]:
    """O PDF e a folha (HTML) de onde ele saiu — a folha é o que compara as vias (o PDF leva
    a data da geração e muda a cada vez)."""
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as exc:  # sem o motor no servidor
        raise RuntimeError(MSG_SEM_MOTOR) from exc
    folha = html(tipo, s)
    return HTML(string=folha).write_pdf(), folha


def nome_do_arquivo(tipo: str, s: Solicitacao) -> str:
    """"<prefixo> <nº> - Lote <n> - <4 primeiras palavras do fornecedor>.pdf"."""
    t = TIPOS[tipo]
    numero = s.numero_oficio if tipo == "oficio" else (
        f"NF{s.nota_fiscal}" if tipo == "certifico" else s.numero)
    palavras = " ".join(s.lote.contrato.fornecedor.razao_social.split()[:4])
    nome = f"{t.prefixo} {numero or s.pk} - Lote {s.lote.numero} - {palavras}"
    return re.sub(r"[^\w .,()-]", "-", nome)[:150] + ".pdf"


def sha256(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()
