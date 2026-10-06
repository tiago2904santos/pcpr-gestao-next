"""Certidões dos fornecedores (CB5a): o quadro por fornecedor com lote ativo (situação de
cada tipo, validade, portal emissor) e o anexo com a conferência do texto do PDF (tipo,
CNPJ e validade lidos; imagem vale a data informada). Mensagens da referência."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from . import dominio_certidoes as regras
from . import policies
from .forms import conferir_pdf
from .models import Certidao, Fornecedor, Lote
from .pedidos import PedidoInvalido


def texto_do_pdf(arquivo, paginas: int = 3) -> str:
    """O texto das primeiras páginas ("" se for imagem ou não abrir)."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    posicao = arquivo.tell() if hasattr(arquivo, "tell") else 0
    try:
        arquivo.seek(0)
        leitor = PdfReader(arquivo)
        return "\n".join((p.extract_text() or "") for p in leitor.pages[:paginas])
    except (PdfReadError, ValueError, KeyError, TypeError):
        return ""
    finally:
        arquivo.seek(posicao)


@dataclass
class Linha:
    tipo: str
    rotulo: str
    certidao: Certidao | None
    situacao: str
    texto: str
    tom: str
    portal: str


def vigentes(fornecedor: Fornecedor) -> dict[str, Certidao]:
    """A de maior validade de cada tipo (vencida ou não)."""
    saida: dict[str, Certidao] = {}
    for c in fornecedor.certidoes.all():  # ordem: tipo, -validade
        saida.setdefault(c.tipo, c)
    return saida


def quadro(fornecedor: Fornecedor, hoje: date | None = None) -> list[Linha]:
    hoje = hoje or timezone.localdate()
    vig = vigentes(fornecedor)
    linhas = []
    for tipo, rotulo in regras.TIPOS:
        c = vig.get(tipo)
        chave, texto, tom = regras.situacao(c.validade if c else None, hoje)
        portal = (fornecedor.portal_certidao_municipal if tipo == "municipal"
                  else regras.PORTAIS[tipo])
        linhas.append(Linha(tipo, rotulo, c, chave, texto, tom, portal))
    return linhas


def fornecedores_com_lote_ativo():
    return (Fornecedor.objects.filter(pk__in=Lote.objects.filter(ativo=True).values(
        "contrato__fornecedor")).prefetch_related("certidoes").order_by("razao_social"))


@transaction.atomic
def anexar(usuario, fornecedor_pk: int, tipo: str, arquivo,
           validade_informada: date | None = None) -> Certidao:
    if not policies.pode_acessar(usuario):
        raise PermissionDenied
    if tipo not in regras.ROTULOS:
        raise PedidoInvalido("Tipo de certidão desconhecido.")
    f = Fornecedor.objects.get(pk=fornecedor_pk)
    rotulo = regras.ROTULOS[tipo]
    if not arquivo:
        raise PedidoInvalido(f"Certidão {rotulo}: escolha o PDF.")
    try:
        conferir_pdf(arquivo)
    except ValidationError as exc:
        raise PedidoInvalido(f"Certidão {rotulo}: " + " ".join(exc.messages)) from None
    try:
        c = regras.conferir(texto_do_pdf(arquivo), tipo, f.cnpj, f.razao_social,
                            f.cnpj_formatado, validade_informada)
    except ValueError as exc:
        raise PedidoInvalido(f"Certidão {rotulo}: {exc}") from None
    return Certidao.objects.create(fornecedor=f, tipo=tipo, arquivo=arquivo,
                                   validade=c.validade, aviso=c.aviso, enviada_por=usuario)


def mensagem(c: Certidao, hoje: date | None = None) -> tuple[str, bool]:
    """O sucesso (ou aviso, se vencida) da referência."""
    hoje = hoje or timezone.localdate()
    rotulo = regras.ROTULOS[c.tipo]
    vencida = c.validade < hoje
    texto = (f"Certidão {rotulo} de {c.fornecedor} conferida e anexada — "
             f"{'vencida em' if vencida else 'válida até'} {c.validade:%d/%m/%Y}.")
    if c.aviso:
        texto += f" {c.aviso}"
    return texto, vencida or bool(c.aviso)
