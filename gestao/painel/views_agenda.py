"""Agenda (paridade com `agenda/views.py` da referência): o mês em grade, a semana, o dia
ou a lista do mês, com filtro por fonte e os encerrados escondidos por padrão. As fontes e
as permissões vêm de `plataforma.agenda` (cada contexto registra as suas); tudo é montado
no servidor (a referência usa um calendário em JavaScript; aqui a navegação é por links,
que funcionam sem JavaScript e são lidos pelo leitor de tela)."""

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
NOMES_DOS_DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
                  "sexta-feira", "sábado", "domingo")
VISTAS = ("mes", "semana", "dia", "lista")


def _mes(texto: str | None, hoje: date) -> tuple[int, int] | None:
    if texto and (m := MES.match(texto)) and 1 <= int(m.group(2)) <= 12:
        return int(m.group(1)), int(m.group(2))
    return None


def _dia(texto: str | None) -> date | None:
    try:
        return date.fromisoformat(texto) if texto else None
    except ValueError:
        return None


def _titulo_semana(inicio: date, fim: date) -> str:
    if inicio.month == fim.month:
        return f"{inicio.day} a {fim.day} de {NOMES_DOS_MESES[fim.month - 1]} de {fim.year}"
    if inicio.year == fim.year:
        return (f"{inicio.day} de {NOMES_DOS_MESES[inicio.month - 1]} a {fim.day} de "
                f"{NOMES_DOS_MESES[fim.month - 1]} de {fim.year}")
    return (f"{inicio.day} de {NOMES_DOS_MESES[inicio.month - 1]} de {inicio.year} a "
            f"{fim.day} de {NOMES_DOS_MESES[fim.month - 1]} de {fim.year}")


def _titulo_dia(d: date) -> str:
    return f"{NOMES_DOS_DIAS[d.weekday()]}, {d.day} de {NOMES_DOS_MESES[d.month - 1]} de {d.year}"


@require_GET
def agenda_view(request: HttpRequest) -> HttpResponse:
    hoje = timezone.localdate()
    vista = request.GET.get("vista") or "mes"
    vista = vista if vista in VISTAS else "mes"
    pedido_mes = _mes(request.GET.get("mes"), hoje)
    # O dia de referência: o pedido; senão o 1º do mês pedido (ou hoje, no mês corrente).
    dia = _dia(request.GET.get("dia"))
    if dia is None:
        dia = (date(pedido_mes[0], pedido_mes[1], 1)
               if pedido_mes and pedido_mes != (hoje.year, hoje.month) else hoje)
    ano, mes = pedido_mes or (dia.year, dia.month)
    fontes = agenda.fontes_de(request.user)
    escolhidas = [s for s in request.GET.getlist("fonte") if any(f.slug == s for f in fontes)]
    mostrar_encerrados = request.GET.get("encerrados") == "1"

    if vista == "lista":
        inicio = date(ano, mes, 1)
        fim = date(*agenda.mes_vizinho(ano, mes, 1), 1) - timedelta(days=1)
    elif vista == "semana":
        inicio, fim = agenda.semana_de(dia)
    elif vista == "dia":
        inicio = fim = dia
    else:
        inicio, fim = agenda.periodo_da_grade(ano, mes)
    todos = agenda.compromissos_de(request.user, inicio, fim, escolhidas or None)
    encerrados = sum(1 for c in todos if c.encerrado)
    visiveis = [c for c in todos if mostrar_encerrados or not c.encerrado]

    filtros = "".join(f"&fonte={s}" for s in escolhidas) + ("&encerrados=1"
                                                             if mostrar_encerrados else "")

    def url(vista_: str, d: date | None = None, mes_: tuple[int, int] | None = None) -> str:
        if vista_ in ("mes", "lista"):
            a, m = mes_ or (ano, mes)
            return f"?vista={vista_}&mes={a}-{m:02d}{filtros}"
        return f"?vista={vista_}&dia={(d or dia).isoformat()}{filtros}"

    if vista in ("mes", "lista"):
        titulo = f"{NOMES_DOS_MESES[mes - 1]} de {ano}"
        anterior = url(vista, mes_=agenda.mes_vizinho(ano, mes, -1))
        seguinte = url(vista, mes_=agenda.mes_vizinho(ano, mes, 1))
        no_atual = (ano, mes) == (hoje.year, hoje.month)
        rotulos = ("Mês anterior", "Próximo mês")
    elif vista == "semana":
        titulo = _titulo_semana(inicio, fim)
        anterior = url("semana", dia - timedelta(days=7))
        seguinte = url("semana", dia + timedelta(days=7))
        no_atual = inicio <= hoje <= fim
        rotulos = ("Semana anterior", "Próxima semana")
    else:
        titulo = _titulo_dia(dia)
        anterior = url("dia", dia - timedelta(days=1))
        seguinte = url("dia", dia + timedelta(days=1))
        no_atual = dia == hoje
        rotulos = ("Dia anterior", "Próximo dia")

    por_dia: list[tuple[date, list[agenda.Compromisso]]] = []
    if vista in ("lista", "dia"):
        for c in visiveis:
            d = max(c.inicio, inicio)
            if por_dia and por_dia[-1][0] == d:
                por_dia[-1][1].append(c)
            else:
                por_dia.append((d, [c]))
    return render(request, "painel/agenda.html", {
        "ano": ano, "mes": mes, "titulo_mes": titulo, "vista": vista,
        "dias_da_semana": DIAS_DA_SEMANA,
        "semanas": agenda.semanas_do_mes(ano, mes, visiveis, hoje) if vista == "mes" else [],
        "dias": agenda.dias_entre(inicio, fim, visiveis, hoje) if vista == "semana" else [],
        "por_dia": por_dia, "fontes": fontes, "escolhidas": escolhidas,
        "mostrar_encerrados": mostrar_encerrados, "encerrados": encerrados,
        "total": sum(1 for c in visiveis if not c.faixa),
        "url_anterior": anterior, "url_seguinte": seguinte,
        "rotulo_anterior": rotulos[0], "rotulo_seguinte": rotulos[1],
        "url_hoje": url(vista, hoje, (hoje.year, hoje.month)), "e_mes_atual": no_atual,
        "urls_vistas": {"mes": url("mes"), "semana": url("semana"), "dia": url("dia"),
                        "lista": url("lista")},
        "mes_param": f"{ano}-{mes:02d}", "dia_param": dia.isoformat(),
        "migalhas": [("Início", reverse("painel:inicio")), ("Agenda", "")]})
