"""Agenda (paridade com `agenda/views.py` da referência, por enquanto com as fontes de
Viagens): o mês em grade (ou em lista), com filtro por fonte e os encerrados escondidos por
padrão. As fontes e as permissões vêm de `plataforma.agenda` (cada contexto registra as
suas); a grade é montada no servidor."""

from __future__ import annotations

import re
from datetime import date, timedelta

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from gestao.plataforma import agenda

MES = re.compile(r"^(\d{4})-(\d{2})$")
NOMES_DOS_MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                   "agosto", "setembro", "outubro", "novembro", "dezembro")
DIAS_DA_SEMANA = ("Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb")


def _mes(texto: str | None, hoje: date) -> tuple[int, int]:
    if texto and (m := MES.match(texto)) and 1 <= int(m.group(2)) <= 12:
        return int(m.group(1)), int(m.group(2))
    return hoje.year, hoje.month


@require_GET
def agenda_view(request: HttpRequest) -> HttpResponse:
    hoje = timezone.localdate()
    ano, mes = _mes(request.GET.get("mes"), hoje)
    fontes = agenda.fontes_de(request.user)
    escolhidas = [s for s in request.GET.getlist("fonte") if any(f.slug == s for f in fontes)]
    mostrar_encerrados = request.GET.get("encerrados") == "1"
    vista = "lista" if request.GET.get("vista") == "lista" else "mes"
    if vista == "lista":
        inicio = date(ano, mes, 1)
        fim = date(*agenda.mes_vizinho(ano, mes, 1), 1) - timedelta(days=1)
    else:
        inicio, fim = agenda.periodo_da_grade(ano, mes)
    todos = agenda.compromissos_de(request.user, inicio, fim, escolhidas or None)
    encerrados = sum(1 for c in todos if c.encerrado)
    visiveis = [c for c in todos if mostrar_encerrados or not c.encerrado]
    anterior, seguinte = agenda.mes_vizinho(ano, mes, -1), agenda.mes_vizinho(ano, mes, 1)
    base = request.GET.copy()
    base.pop("mes", None)
    filtros = base.urlencode()

    def url_mes(a: int, m: int) -> str:
        return f"?mes={a}-{m:02d}" + (f"&{filtros}" if filtros else "")

    por_dia: list[tuple[date, list[agenda.Compromisso]]] = []
    if vista == "lista":
        for c in visiveis:
            dia = max(c.inicio, inicio)
            if por_dia and por_dia[-1][0] == dia:
                por_dia[-1][1].append(c)
            else:
                por_dia.append((dia, [c]))
    return render(request, "painel/agenda.html", {
        "ano": ano, "mes": mes, "titulo_mes": f"{NOMES_DOS_MESES[mes - 1]} de {ano}",
        "vista": vista, "dias_da_semana": DIAS_DA_SEMANA,
        "semanas": agenda.semanas_do_mes(ano, mes, visiveis, hoje) if vista == "mes" else [],
        "por_dia": por_dia, "fontes": fontes, "escolhidas": escolhidas,
        "mostrar_encerrados": mostrar_encerrados, "encerrados": encerrados,
        "total": sum(1 for c in visiveis if not c.faixa),
        "url_anterior": url_mes(*anterior), "url_seguinte": url_mes(*seguinte),
        "url_hoje": url_mes(hoje.year, hoje.month),
        "e_mes_atual": (ano, mes) == (hoje.year, hoje.month),
        "mes_param": f"{ano}-{mes:02d}",
        "migalhas": [("Início", reverse("painel:inicio")), ("Agenda", "")]})
