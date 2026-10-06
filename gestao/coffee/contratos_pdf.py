"""Anexar o contrato ou o termo aditivo por PDF (CB5d; paridade com
`coffee_break/contratos_pdf.py` e `views.py:2648-2743`, §2.2 — só o administrador do
módulo): basta anexar; o sistema identifica o documento (`dominio_contrato`), cria o
fornecedor pelo CNPJ se não existir, cria ou completa o contrato (número, GMS, quantidade,
valores, vigência — estimada pelo prazo no contrato inicial; o aditivo traz a data e
corrige), guarda o PDF no contrato ou no termo aditivo e cria o lote se o contrato não
tiver nenhum. Mensagens da referência."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from . import dominio, dominio_contrato, policies, services
from .certidoes import texto_do_pdf
from .forms import conferir_pdf
from .models import Contrato, Fornecedor, Lote, TermoAditivo
from .pedidos import PedidoInvalido

MSG_ESCOLHA = "Escolha o PDF do contrato ou do termo aditivo."
MSG_NAO_E_CONTRATO = ("Este PDF não parece ser um contrato nem um termo aditivo da SESP (não "
                      "achei o número do contrato).")


@dataclass
class Resultado:
    mensagem: str
    aviso: bool = False
    contrato: Contrato | None = None


def _fornecedor(doc: dominio_contrato.Documento) -> Fornecedor:
    f = Fornecedor.objects.filter(cnpj=doc.cnpj).first()
    if f is not None:
        return f
    razao = doc.razao_social[:200] or f"Fornecedor {dominio.formatar_cnpj(doc.cnpj)}"
    mesmo_nome = Fornecedor.objects.filter(razao_social__iexact=razao).first()
    if mesmo_nome is not None:
        if mesmo_nome.cnpj:  # outro CNPJ com a mesma razão social: confira à mão
            raise PedidoInvalido(f"Já existe o fornecedor {mesmo_nome} com o CNPJ "
                                 f"{mesmo_nome.cnpj_formatado}, e este documento traz "
                                 f"{dominio.formatar_cnpj(doc.cnpj)}: confira o cadastro.")
        mesmo_nome.cnpj = doc.cnpj  # o cadastro sem CNPJ ganha o do documento
        mesmo_nome.save(update_fields=["cnpj", "atualizado_em"])
        return mesmo_nome
    return Fornecedor.objects.create(razao_social=razao, cnpj=doc.cnpj)


def _completar(c: Contrato, doc: dominio_contrato.Documento) -> None:
    """O que o documento traz sobrescreve; o que não traz fica como está."""
    if doc.numero_gms:
        c.numero_gms = doc.numero_gms[:30]
    if doc.quantidade:
        c.quantidade_contratada = doc.quantidade
    if doc.valor_unitario is not None:
        c.valor_unitario = doc.valor_unitario
    if doc.valor_total is not None:
        c.valor_total = doc.valor_total
    if doc.tipo == "contrato" and doc.vigencia_fim and (c.vigencia_fim is None
                                                         or c.vigencia_estimada):
        c.vigencia_inicio, c.vigencia_fim = doc.vigencia_inicio, doc.vigencia_fim
        c.vigencia_estimada = doc.vigencia_estimada
    if doc.tipo == "aditivo":
        c.termo_aditivo = doc.termo_aditivo[:30]
        if doc.vigencia_fim:  # a data escrita do aditivo corrige a estimada
            c.vigencia_fim, c.vigencia_estimada = doc.vigencia_fim, False


@transaction.atomic
def anexar(usuario, arquivo, hoje: date | None = None) -> Resultado:
    if not policies.pode_gerir_cadastros(usuario, "contratos"):
        raise PermissionDenied
    hoje = hoje or timezone.localdate()
    if not arquivo:
        raise PedidoInvalido(MSG_ESCOLHA)
    try:
        conferir_pdf(arquivo)
    except ValidationError as exc:
        raise PedidoInvalido(" ".join(exc.messages)) from None
    doc = dominio_contrato.ler(texto_do_pdf(arquivo, paginas=20))
    if not doc.tipo or not doc.numero:
        raise PedidoInvalido(MSG_NAO_E_CONTRATO)
    if len(doc.cnpj) != 14:
        raise PedidoInvalido(f"Não achei o CNPJ do contratado no documento do contrato "
                             f"{doc.numero}.")
    c = Contrato.objects.select_for_update().filter(numero=doc.numero).first()
    if c is not None and c.fornecedor.cnpj and c.fornecedor.cnpj != doc.cnpj:
        raise PedidoInvalido(f"O contrato {doc.numero} está cadastrado para {c.fornecedor}, "
                             f"mas este documento é de {doc.razao_social or doc.cnpj}.")
    if c is None:
        c = Contrato(fornecedor=_fornecedor(doc), numero=doc.numero[:30])
    _completar(c, doc)
    if doc.tipo == "contrato":
        antigo = str(c.arquivo.name) if c.arquivo else ""
        c.arquivo = arquivo
        c.save()
        services.apagar_arquivo_depois(Contrato, antigo)
    else:
        c.save()
        a, _novo = TermoAditivo.objects.get_or_create(contrato=c, numero=doc.termo_aditivo[:30])
        antigo = str(a.arquivo.name) if a.arquivo else ""
        a.arquivo = arquivo
        if doc.vigencia_fim:
            a.vigencia_inicio, a.vigencia_fim = doc.vigencia_inicio, doc.vigencia_fim
        a.save()
        services.apagar_arquivo_depois(TermoAditivo, antigo)
    lote_criado = None
    if not c.lotes.exists() and doc.quantidade:
        ano = (doc.vigencia_inicio or hoje).year
        lote_criado = Lote.objects.create(contrato=c, numero=doc.numero_lote or 1,
                                          exercicio=str(ano), quantidade_total=doc.quantidade)
    return _resultado(c, doc, lote_criado, hoje)


def _resultado(c: Contrato, doc: dominio_contrato.Documento, lote: Lote | None,
               hoje: date) -> Resultado:
    fim = c.fim_efetivo()
    if doc.tipo == "aditivo":
        partes = [f"Termo aditivo {doc.termo_aditivo} do contrato {c.numero} ({c.fornecedor}) "
                  "anexado e conferido"]
    else:
        partes = [f"Contrato {c.numero} ({c.fornecedor}) anexado e conferido"]
    if fim:
        texto = f"vigente até {fim:%d/%m/%Y}"
        if c.vigencia_estimada:
            texto += " (estimada pelo prazo; o termo aditivo confirma)"
        partes.append(texto)
    if c.quantidade_contratada:
        partes.append(f"{c.quantidade_contratada:,} unidades".replace(",", "."))
    if lote is not None:
        partes.append(f"lote {lote.numero} criado — escolha os municípios dele em Lotes")
    return Resultado("; ".join(partes) + ".", aviso=bool(fim and fim < hoje), contrato=c)
