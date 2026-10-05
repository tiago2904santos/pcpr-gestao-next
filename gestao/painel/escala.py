"""A escala: uma linha por pessoa, uma coluna por dia (paridade com `agenda/escala.py` da
referência). Responde "quem está fora na quinta?" sem abrir registro por registro. É uma
tabela montada dos mesmos compromissos da agenda (`Compromisso.pessoas`), com as mesmas
permissões: quem não vê Viagens não vê a escala das viagens. Cancelados aparecem riscados
e não contam como dia fora."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from gestao.plataforma import agenda

DIAS_PADRAO = 7
DIAS_MAXIMO = 62
OPCOES_DIAS = (7, 14, 31)
DIAS_DA_SEMANA = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")


@dataclass
class Coluna:
    data: date
    semana: str
    fim_de_semana: bool
    hoje: bool


@dataclass
class Linha:
    nome: str
    celulas: list[list[agenda.Compromisso]]
    total: int = 0
    dias_fora: int = 0
    rotulos: dict[str, str] = field(default_factory=dict)


def montar(usuario, inicio: date, dias: int, *, slugs: list[str] | None = None,
           pessoa: str = "", hoje: date | None = None) -> dict:
    hoje = hoje or timezone.localdate()
    fim = inicio + timedelta(days=dias - 1)
    colunas = [Coluna(d, DIAS_DA_SEMANA[d.weekday()], d.weekday() >= 5, d == hoje)
               for d in (inicio + timedelta(days=i) for i in range(dias))]
    filtro = pessoa.strip().casefold()
    linhas: dict[str, Linha] = {}
    for c in agenda.compromissos_de(usuario, inicio, fim, slugs or None):
        if not c.pessoas or c.faixa:
            continue
        primeiro, ultimo = max(c.inicio, inicio), min(c.ultimo_dia, fim)
        for nome in c.pessoas:
            if filtro and filtro not in nome.casefold():
                continue
            linha = linhas.setdefault(nome, Linha(nome, [[] for _ in range(dias)]))
            linha.total += 1
            d = primeiro
            while d <= ultimo:
                linha.celulas[(d - inicio).days].append(c)
                d += timedelta(days=1)
    ordenadas = sorted(linhas.values(), key=lambda x: x.nome.casefold())
    for linha in ordenadas:
        linha.dias_fora = sum(1 for cel in linha.celulas if any(not c.encerrado for c in cel))
    return {"colunas": colunas, "linhas": ordenadas, "inicio": inicio, "fim": fim,
            "dias": dias}


def _data(texto: str | None, padrao: date) -> date:
    try:
        return date.fromisoformat((texto or "")[:10]) if texto else padrao
    except ValueError:
        return padrao


def _dias(texto: str | None) -> int:
    try:
        return max(1, min(int(texto or DIAS_PADRAO), DIAS_MAXIMO))
    except ValueError:
        return DIAS_PADRAO


@require_GET
def escala(request: HttpRequest) -> HttpResponse:
    hoje = timezone.localdate()
    inicio = _data(request.GET.get("inicio"), hoje - timedelta(days=hoje.weekday()))
    dias = _dias(request.GET.get("dias"))
    pessoa = " ".join((request.GET.get("pessoa") or "").split())[:120]
    fontes = agenda.fontes_de(request.user)
    escolhidas = [s for s in request.GET.getlist("fonte") if any(f.slug == s for f in fontes)]
    quadro = montar(request.user, inicio, dias, slugs=escolhidas, pessoa=pessoa, hoje=hoje)

    def url(novo_inicio: date, novos_dias: int = dias) -> str:
        extra = "".join(f"&fonte={s}" for s in escolhidas) + (f"&pessoa={pessoa}" if pessoa
                                                              else "")
        return f"?inicio={novo_inicio.isoformat()}&dias={novos_dias}{extra}"

    return render(request, "painel/escala.html", {
        **quadro, "pessoa": pessoa, "fontes": fontes, "escolhidas": escolhidas,
        "opcoes_dias": OPCOES_DIAS,
        "url_anterior": url(inicio - timedelta(days=dias)),
        "url_seguinte": url(inicio + timedelta(days=dias)),
        "url_hoje": url(hoje - timedelta(days=hoje.weekday())),
        "urls_dias": [(n, url(inicio, n)) for n in OPCOES_DIAS],
        "migalhas": [("Início", reverse("painel:inicio")), ("Agenda", reverse("painel:agenda")),
                     ("Escala", "")],
    })
