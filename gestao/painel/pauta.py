"""A pauta da semana: a agenda em PDF, para a reunião (paridade com `agenda/pauta.py` da
referência). Um bloco por dia, de segunda a domingo (ou o período pedido, até 62 dias); em
cada compromisso o horário, o título, a situação e os detalhes da fonte. Compromisso de
vários dias aparece em cada dia que toca, marcado "continua" a partir do segundo.
Cancelados não entram. `?formato=html` mostra a mesma pauta na tela (imprimível).

O envio semanal por e-mail da referência depende do e-mail institucional (pendência
externa: SMTP) e não está aqui.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from django.http import HttpRequest, HttpResponse
from django.middleware.csp import get_nonce
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_GET

from gestao.plataforma import agenda

MAX_DIAS = 62
NOMES_DOS_DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
                  "sexta-feira", "sábado", "domingo")


@dataclass
class Item:
    compromisso: agenda.Compromisso
    rotulo_fonte: str
    continua: bool
    ate: date | None


@dataclass
class DiaDaPauta:
    data: date
    nome: str
    hoje: bool
    faixas: list[str] = field(default_factory=list)
    itens: list[Item] = field(default_factory=list)


def semana_de(dia: date) -> tuple[date, date]:
    """Segunda e domingo da semana do dia (a pauta é de segunda a domingo)."""
    segunda = dia - timedelta(days=dia.weekday())
    return segunda, segunda + timedelta(days=6)


def montar(usuario, inicio: date, fim: date, *, slugs: list[str] | None = None,
           so_meus: bool = False, hoje: date | None = None) -> dict:
    hoje = hoje or timezone.localdate()
    rotulos = {f.slug: f.rotulo for f in agenda.fontes_de(usuario)}
    todos = [c for c in agenda.compromissos_de(usuario, inicio, fim, slugs or None)
             if not c.encerrado and (not so_meus or c.meu or c.faixa)]
    dias = []
    d = inicio
    while d <= fim:
        dia = DiaDaPauta(d, NOMES_DOS_DIAS[d.weekday()], d == hoje)
        for c in todos:
            if not c.toca(d):
                continue
            if c.faixa:
                dia.faixas.append(c.titulo)
                continue
            dia.itens.append(Item(c, rotulos.get(c.fonte, c.fonte), c.inicio < d,
                                  c.ultimo_dia if c.ultimo_dia > d else None))
        dia.itens.sort(key=lambda i: (i.continua, i.compromisso.hora or "~",
                                      i.compromisso.titulo))
        dias.append(dia)
        d += timedelta(days=1)
    semana = (fim - inicio).days == 6 and inicio.weekday() == 0
    return {"inicio": inicio, "fim": fim, "dias": dias,
            "total": sum(len(x.itens) for x in dias), "usuario": usuario,
            "gerada_em": timezone.localtime(),
            "titulo": "Pauta da semana" if semana else "Pauta do período"}


def html(contexto: dict, *, nonce: str = "", tela: bool = False) -> str:
    return render_to_string("painel/pauta.html", {**contexto, "nonce": nonce, "tela": tela})


def pdf(contexto: dict) -> bytes:
    from weasyprint import HTML
    return HTML(string=html(contexto)).write_pdf()


def _data(texto: str | None) -> date | None:
    try:
        return date.fromisoformat((texto or "")[:10]) if texto else None
    except ValueError:
        return None


@require_GET
def baixar(request: HttpRequest) -> HttpResponse:
    """/agenda/pauta/?inicio=&fim=&fonte=&meus=1 (&formato=html para ver na tela)."""
    hoje = timezone.localdate()
    padrao_inicio, padrao_fim = semana_de(hoje)
    inicio = _data(request.GET.get("inicio")) or padrao_inicio
    fim = _data(request.GET.get("fim")) or padrao_fim
    fim = max(fim, inicio)
    if (fim - inicio).days >= MAX_DIAS:
        fim = inicio + timedelta(days=MAX_DIAS - 1)
    fontes = {f.slug for f in agenda.fontes_de(request.user)}
    slugs = [s for s in request.GET.getlist("fonte") if s in fontes]
    contexto = montar(request.user, inicio, fim, slugs=slugs,
                      so_meus=request.GET.get("meus") == "1", hoje=hoje)
    if request.GET.get("formato") == "html":
        preguicoso = get_nonce(request)
        return HttpResponse(html(contexto, nonce=str(preguicoso) if preguicoso else "",
                                 tela=True))
    resposta = HttpResponse(pdf(contexto), content_type="application/pdf")
    resposta["Content-Disposition"] = (
        f'attachment; filename="pauta_{inicio:%Y-%m-%d}_{fim:%Y-%m-%d}.pdf"')
    return resposta
