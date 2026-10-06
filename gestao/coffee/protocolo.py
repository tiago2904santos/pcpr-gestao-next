"""O protocolo de pagamento (CB5c; paridade com `coffee_break/documentos.py` §5 e
`protocolo_pagamento.py`): a lista ordenada do anexo (ofício; nota e certifico de cada OS do
pagamento; certidões; termos aditivos; contrato), cada item pronto ou dizendo o que falta,
os quatro arquivos para baixar (PDF de cada um, ZIP com vários ou PDF único na ordem) e os
textos para copiar no eProtocolo. Baixar os arquivos registra o "atesto e envio ao GAF"
(uma vez; exige o protocolo). O protocolo em si é aberto à mão (o eProtocolo alcançado é de
treinamento)."""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from functools import partial

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from . import certidoes, conjunto, documentos, policies, vias
from . import dominio_certidoes as regras_certidoes
from .models import ConfiguracaoOficio, Movimento, Solicitacao
from .pedidos import PedidoInvalido

ORDEM_CERTIDOES = ("fgts", "trabalhista", "municipal", "estadual", "federal")
PARTES = (("os", "Ordens de serviço"), ("oficio", "Ofício"),
          ("notas", "Notas fiscais e certificos"),
          ("contrato", "Contrato, termos aditivos e certidões"))
ROTULO_PARTE = dict(PARTES)
MSG_MARQUE = "Marque ao menos um arquivo para baixar."


@dataclass
class Item:
    titulo: str
    parte: str
    pronto: bool
    falta: str = ""
    aviso: str = ""
    resolver: str = ""
    obter: Callable[[], bytes] | None = field(default=None, repr=False)


def _ler(arquivo) -> bytes:
    with arquivo.open("rb") as f:
        return f.read()


def _doc(usuario, s: Solicitacao, tipo: str) -> bytes:
    return vias.obter(usuario, s, tipo).conteudo


def itens(usuario, s: Solicitacao, hoje: date | None = None) -> list[Item]:
    """A lista do anexo na ordem do protocolo."""
    hoje = hoje or timezone.localdate()
    grupo = conjunto.membros(s)
    contrato = s.lote.contrato
    fornecedor = contrato.fornecedor
    folha = reverse("coffee:solicitacao", args=[s.pk])
    saida: list[Item] = []
    for m in grupo:
        faltas = documentos.pendencias("os", m)
        saida.append(Item(f"Ordem de serviço {m}", "os", not faltas, " ".join(faltas),
                          resolver=reverse("coffee:solicitacao", args=[m.pk]) + "#entrega",
                          obter=partial(_doc, usuario, m, "os")))
    faltas = documentos.pendencias("oficio", s)
    saida.append(Item(f"Ofício {s.numero_oficio or ''}".strip(), "oficio", not faltas,
                      " ".join(faltas), resolver=folha + "#nota",
                      obter=partial(_doc, usuario, s, "oficio")))
    for m in grupo:
        saida.append(Item(f"Nota fiscal {m.nota_fiscal or ''} ({m})".replace("  ", " "),
                          "notas", bool(m.nota_pdf),
                          "" if m.nota_pdf else "Anexe o PDF da nota fiscal.",
                          resolver=reverse("coffee:solicitacao", args=[m.pk]) + "#pdfs",
                          obter=partial(_ler, m.nota_pdf) if m.nota_pdf else None))
        faltas = documentos.pendencias("certifico", m)
        saida.append(Item(f"Certifico digital ({m})", "notas", not faltas, " ".join(faltas),
                          resolver=reverse("coffee:solicitacao", args=[m.pk]) + "#nota",
                          obter=partial(_doc, usuario, m, "certifico")))
    vig = certidoes.vigentes(fornecedor)
    for tipo in ORDEM_CERTIDOES:
        c = vig.get(tipo)
        rotulo = regras_certidoes.ROTULOS[tipo]
        resolver = reverse("coffee:certidoes") + f"?anexar={fornecedor.pk}:{tipo}"
        if c is None:
            saida.append(Item(f"Certidão {rotulo}", "contrato", False,
                              "Certidão não cadastrada.", resolver=resolver))
            continue
        aviso = f"Vencida em {c.validade:%d/%m/%Y}." if c.validade < hoje else ""
        saida.append(Item(f"Certidão {rotulo}", "contrato", True, aviso=aviso,
                          resolver=resolver if aviso else "",
                          obter=partial(_ler, c.arquivo)))
    cadastro = reverse("coffee:cadastros", args=["aditivos"])
    for a in contrato.aditivos.order_by("vigencia_fim", "pk"):
        saida.append(Item(f"Termo aditivo {a.numero}", "contrato", bool(a.arquivo),
                          "" if a.arquivo else
                          "Anexe o PDF do termo aditivo em Cadastros › Contratos.",
                          resolver="" if a.arquivo else f"{cadastro}?editar={a.pk}",
                          obter=partial(_ler, a.arquivo) if a.arquivo else None))
    saida.append(Item(f"Contrato {contrato.numero}", "contrato", bool(contrato.arquivo),
                      "" if contrato.arquivo else "Anexe o PDF no cadastro do contrato.",
                      resolver="" if contrato.arquivo else
                      reverse("coffee:cadastros", args=["contratos"]) + f"?editar={contrato.pk}",
                      obter=partial(_ler, contrato.arquivo) if contrato.arquivo else None))
    return saida


def _juntar(conteudos: list[bytes]) -> bytes:
    from pypdf import PdfReader, PdfWriter

    escritor = PdfWriter()
    for c in conteudos:
        for pagina in PdfReader(io.BytesIO(c)).pages:
            escritor.add_page(pagina)
    saida = io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()


def _nome(s: Solicitacao, parte: str) -> str:
    curto = s.lote.contrato.fornecedor.nome_para_documentos
    n = {"os": "01", "oficio": "02", "notas": "03", "contrato": "04"}[parte]
    return f"{n} - {ROTULO_PARTE[parte]} - {s.numero_oficio or s.numero} {curto}"[:120] \
        .replace("/", "-") + ".pdf"


@dataclass
class Pacote:
    conteudo: bytes
    nome: str
    tipo: str  # application/pdf | application/zip


@transaction.atomic
def baixar(usuario, pk: int, partes: list[str], formato: str = "zip",
           hoje: date | None = None) -> Pacote:
    """Os arquivos marcados (o que falta fica de fora). Com o protocolo registrado, a
    primeira vez registra o atesto e envio ao GAF (espelhado no pagamento conjunto)."""
    if not policies.pode_acessar(usuario):
        raise PermissionDenied
    hoje = hoje or timezone.localdate()
    s = Solicitacao.objects.select_for_update().get(pk=pk)
    partes = [p for p in partes if p in ROTULO_PARTE]
    if not partes:
        raise PedidoInvalido(MSG_MARQUE)
    lista = itens(usuario, s, hoje)
    arquivos: list[tuple[str, bytes]] = []
    for parte in partes:
        conteudos = [i.obter() for i in lista if i.parte == parte and i.pronto and i.obter]
        if not conteudos:
            raise PedidoInvalido(f"{ROTULO_PARTE[parte]}: nenhum documento disponível ainda.")
        arquivos.append((_nome(s, parte), _juntar(conteudos)))
    if s.protocolo_pagamento and not s.atesto_em and not s.cancelada:
        s.atesto_em = hoje
        s.save(update_fields=["atesto_em", "atualizado_em"])
        conjunto.espelhar(s, usuario, ["atesto_em"])
        Movimento.objects.create(solicitacao=s, acao=Movimento.Acao.ANDAMENTO, usuario=usuario,
                                 texto=f"Atesto e envio ao GAF em {hoje:%d/%m/%Y} (arquivos "
                                       "do protocolo baixados).")
    base = f"Protocolo {s.numero_oficio or s.numero}".replace("/", "-")
    if len(arquivos) == 1 and formato != "unico":
        nome, conteudo = arquivos[0]
        return Pacote(conteudo, nome, "application/pdf")
    if formato == "unico":
        return Pacote(_juntar([c for _n, c in arquivos]), f"{base}.pdf", "application/pdf")
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as zipado:
        for nome, conteudo in arquivos:
            zipado.writestr(nome, conteudo)
    return Pacote(memoria.getvalue(), f"{base}.zip", "application/zip")


def textos(s: Solicitacao) -> list[tuple[str, str, str]]:
    """(chave, rótulo, texto) para copiar no eProtocolo."""
    cfg = ConfiguracaoOficio.atual()
    contrato = s.lote.contrato
    fornecedor = contrato.fornecedor
    notas = [m.nota_fiscal for m in conjunto.membros(s) if m.nota_fiscal]
    lista = documentos.juntar(notas)
    plural = len(notas) > 1
    curto = fornecedor.nome_para_documentos
    detalhamento = (f"ENVIO P/ PAGAMENTO {'DAS NOTAS FISCAIS' if plural else 'DA NOTA FISCAL'}"
                    f" N {lista.upper()} - ({curto})")
    qual = "das Notas fiscais" if plural else "da Nota fiscal"
    despacho = (f"{cfg.destino_despacho}\nEncaminhamos o presente protocolado com as devidas "
                f"informações para o pagamento {qual} n° {lista}.")
    assunto = f"CONTRATO {contrato.numero}"
    if contrato.numero_gms:
        assunto += f" - GMS {contrato.numero_gms}"
    if contrato.termo_aditivo:
        assunto += f" - TERMO ADITIVO No {contrato.termo_aditivo}"
    oficio_n, _, oficio_ano = (s.numero_oficio or "").partition("/")
    return [
        ("interessado", "Interessado", f"{fornecedor.cnpj_formatado} — {fornecedor.razao_social}"),
        ("assunto", "Assunto", cfg.assunto_protocolo),
        ("palavras", "Palavras-chave", cfg.palavras_chave),
        ("detalhamento", "Detalhamento", detalhamento),
        ("oficio", "Nº/Ano do ofício", f"{oficio_n}/{oficio_ano}" if oficio_n else ""),
        ("assunto_despacho", "Assunto do despacho", assunto),
        ("despacho", "Despacho", despacho),
    ]
