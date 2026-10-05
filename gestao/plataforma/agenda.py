"""As fontes da agenda (paridade com `agenda/fontes.py` da referência): de onde vem cada
compromisso e quem pode vê-lo. A plataforma não conhece os módulos — cada contexto registra
as suas fontes (`registrar_fonte`, no `ready` do app), com a permissão dele: quem não vê o
módulo pelas telas não vê nada dele aqui, nem o filtro.

Um compromisso tem início e fim (fim em branco = um dia só; o fim é inclusivo aqui — a
grade é montada no servidor, sem a convenção de fim exclusivo do FullCalendar). Prazos
(o dia em que algo vence) e faixas (feriados) são compromissos de um dia com marcação
própria.
"""

from __future__ import annotations

import calendar
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass(frozen=True)
class Compromisso:
    fonte: str
    chave: str
    titulo: str
    inicio: date
    fim: date | None = None
    url: str = ""
    situacao: str = ""
    tom: str = "neutro"  # neutro | info | sucesso | aviso | perigo
    hora: str = ""
    detalhes: tuple[tuple[str, str], ...] = ()
    encerrado: bool = False  # cancelado/finalizado: escondido por padrão
    prazo: bool = False
    faixa: bool = False  # feriado: fundo do dia, não um compromisso

    @property
    def ultimo_dia(self) -> date:
        return self.fim or self.inicio

    def toca(self, dia: date) -> bool:
        return self.inicio <= dia <= self.ultimo_dia


@dataclass(frozen=True)
class Fonte:
    slug: str
    rotulo: str
    pode: Callable[[object], bool]
    compromissos: Callable[[object, date, date], list[Compromisso]]  # fim inclusivo
    ordem: int = 100


_FONTES: list[Fonte] = []


def registrar_fonte(fonte: Fonte) -> None:
    if all(f.slug != fonte.slug for f in _FONTES):
        _FONTES.append(fonte)
        _FONTES.sort(key=lambda f: (f.ordem, f.rotulo))


def fontes_de(usuario) -> list[Fonte]:
    """As fontes que esta pessoa pode ver — o que a tela lista como filtro."""
    return [f for f in _FONTES if f.pode(usuario)]


def compromissos_de(usuario, inicio: date, fim: date,
                    slugs: Iterable[str] | None = None) -> list[Compromisso]:
    """Todos os compromissos que tocam [inicio, fim], só das fontes visíveis; uma fonte
    pedida fora do acesso é ignorada em silêncio (pedir pelo nome não abre a porta)."""
    pedidas = set(slugs or ())
    saida: list[Compromisso] = []
    for fonte in fontes_de(usuario):
        if pedidas and fonte.slug not in pedidas:
            continue
        saida.extend(fonte.compromissos(usuario, inicio, fim))
    return sorted(saida, key=lambda c: (c.inicio, not c.faixa, c.hora or "99", c.titulo))


# ---------------------------------------------------------------- grade do mês
@dataclass
class Dia:
    data: date
    do_mes: bool
    hoje: bool
    compromissos: list[Compromisso] = field(default_factory=list)
    faixas: list[Compromisso] = field(default_factory=list)


def semanas_do_mes(ano: int, mes: int, compromissos: list[Compromisso],
                   hoje: date) -> list[list[Dia]]:
    """As semanas da grade (domingo a sábado, como o calendário da referência em pt-BR),
    com os compromissos de cada dia."""
    grade = calendar.Calendar(firstweekday=calendar.SUNDAY).monthdatescalendar(ano, mes)
    semanas = []
    for semana in grade:
        dias = []
        for d in semana:
            dia = Dia(d, d.month == mes, d == hoje)
            for c in compromissos:
                if c.toca(d):
                    (dia.faixas if c.faixa else dia.compromissos).append(c)
            dias.append(dia)
        semanas.append(dias)
    return semanas


def semana_de(dia: date) -> tuple[date, date]:
    """Domingo e sábado da semana do dia (a semana da grade, como na referência)."""
    domingo = dia - timedelta(days=(dia.weekday() + 1) % 7)
    return domingo, domingo + timedelta(days=6)


def dias_entre(inicio: date, fim: date, compromissos: list[Compromisso],
               hoje: date) -> list[Dia]:
    """Os dias de [inicio, fim] (visões de semana e de dia), cada um com os seus
    compromissos na ordem recebida (por hora) e as faixas (feriados)."""
    dias = []
    d = inicio
    while d <= fim:
        dia = Dia(d, True, d == hoje)
        for c in compromissos:
            if c.toca(d):
                (dia.faixas if c.faixa else dia.compromissos).append(c)
        dias.append(dia)
        d += timedelta(days=1)
    return dias


def periodo_da_grade(ano: int, mes: int) -> tuple[date, date]:
    grade = calendar.Calendar(firstweekday=calendar.SUNDAY).monthdatescalendar(ano, mes)
    return grade[0][0], grade[-1][-1]


def mes_vizinho(ano: int, mes: int, passo: int) -> tuple[int, int]:
    primeiro = date(ano, mes, 1)
    alvo = (primeiro + timedelta(days=32 * passo)) if passo > 0 else (primeiro - timedelta(days=1))
    return alvo.year, alvo.month
