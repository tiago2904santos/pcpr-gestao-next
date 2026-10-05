"""Carimbo do número de solicitação no ofício assinado (módulo 9d-3, paridade com
`carimbo_services` da referência, só com o ajuste manual — a posição automática lia o texto
do PDF e fica de fora; docs/migration/prestacao.md).

O ofício volta assinado com a coluna da solicitação em branco: o número só existe depois de
protocolar. Aqui se guarda onde desenhar o número de cada servidor (página e posição em
frações da página); o desenho é aplicado na hora — na prévia e no pacote final — sobre a via
assinada, que não muda no disco.
"""

from __future__ import annotations

import io

from django.db import transaction
from django.utils.html import escape

from . import assinados, diario, policies
from .models import CarimboSolicitacao, PrestacaoContas, PrestacaoServidor, ViaAssinada

PENDENCIA = ("O número de solicitação não está carimbado no ofício assinado: use “Ajustar "
             "posição do número”.")


class CarimboInvalido(Exception):
    pass


def via_do_oficio(prestacao: PrestacaoContas) -> ViaAssinada | None:
    return assinados.vigente(assinados.Alvo(ViaAssinada.Tipo.OFICIO, prestacao.oficio))


def numero_de_paginas(via: ViaAssinada) -> int:
    from pypdf import PdfReader
    with via.arquivo.open("rb") as f:
        return len(PdfReader(io.BytesIO(f.read())).pages)


@transaction.atomic
def posicionar(usuario, ps_pk: int, *, pagina: int, x: float, y: float,
               tamanho: float | None = None) -> CarimboSolicitacao:
    ps = (PrestacaoServidor.objects.select_related("prestacao__oficio", "servidor")
          .get(pk=ps_pk, removida_em__isnull=True))
    policies.exigir(policies.pode_editar_equipe_prestacao(usuario, ps.prestacao),
                    "Você não pode alterar esta prestação.")
    if diario.equipe_finalizada(ps.prestacao) or ps.finalizada:
        raise CarimboInvalido("Prestação finalizada — reabra para editar.")
    via = via_do_oficio(ps.prestacao)
    if via is None:
        raise CarimboInvalido("Anexe a via assinada do ofício antes de carimbar.")
    if not 0 <= x <= 1 or not 0 <= y <= 1:
        raise CarimboInvalido("A posição precisa estar dentro da página (0 a 100%).")
    paginas = numero_de_paginas(via)
    if not 0 <= pagina < paginas:
        raise CarimboInvalido(f"O ofício assinado tem {paginas} página(s).")
    carimbo, _ = CarimboSolicitacao.objects.update_or_create(
        via=via, servidor=ps,
        defaults={"pagina": pagina, "x": x, "y": y,
                  **({"tamanho": tamanho} if tamanho else {})})
    return carimbo


def carimbos(via: ViaAssinada) -> list[CarimboSolicitacao]:
    return list(via.carimbos.select_related("servidor__servidor")
                .filter(servidor__removida_em__isnull=True).order_by("pagina", "y", "x"))


def _camada(largura: float, altura: float, itens: list[CarimboSolicitacao]) -> bytes:
    """Uma página transparente do mesmo tamanho com os números nas posições."""
    from weasyprint import HTML
    spans = "".join(
        f'<span style="left:{c.x * 100:.3f}%;top:{c.y * 100:.3f}%;'
        f'font-size:{c.tamanho * altura:.2f}pt">{escape(c.servidor.numero_solicitacao)}</span>'
        for c in itens if c.servidor.numero_solicitacao.strip())
    html = (f"<html><head><style>@page{{size:{largura:.2f}pt {altura:.2f}pt;margin:0}}"
            "body{margin:0;position:relative;width:100%;height:100vh}"
            "span{position:absolute;font-family:sans-serif;font-weight:bold;"
            "transform:translateY(-50%);white-space:nowrap}</style></head>"
            f"<body>{spans}</body></html>")
    return HTML(string=html).write_pdf()


def carimbado(via: ViaAssinada) -> bytes:
    """O PDF da via com os números desenhados (sem carimbo, a via como está)."""
    from pypdf import PdfReader, PdfWriter
    with via.arquivo.open("rb") as f:
        original = f.read()
    lista = carimbos(via)
    if not lista:
        return original
    leitor = PdfReader(io.BytesIO(original))
    escritor = PdfWriter()
    for i, pagina in enumerate(leitor.pages):
        desta = [c for c in lista if c.pagina == i]
        if desta:
            caixa = pagina.mediabox
            camada = PdfReader(io.BytesIO(_camada(float(caixa.width), float(caixa.height),
                                                  desta))).pages[0]
            pagina.merge_page(camada)
        escritor.add_page(pagina)
    saida = io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()


def falta_carimbo(ps: PrestacaoServidor, via: ViaAssinada | None = None) -> bool:
    """Referência: há ofício assinado e número de solicitação, mas não há carimbo dele."""
    if not ps.numero_solicitacao.strip():
        return False
    via = via if via is not None else via_do_oficio(ps.prestacao)
    if via is None:
        return False
    return not via.carimbos.filter(servidor=ps).exists()
