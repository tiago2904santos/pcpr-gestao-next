"""O feed iCalendar da agenda (A2c; comportamento da referência, `agenda/ics.py`): o
calendário da pessoa no Outlook, no Google Agenda ou no celular, pelo link pessoal.

RFC 5545 montada à mão (linhas em CRLF dobradas a 75 octetos, texto escapado). Leva de
propósito menos do que a tela: o título externo da fonte (sem nomes nem texto livre; na
falta, o rótulo da fonte), o período, a situação e o link de volta — nunca o título da tela
nem os detalhes, porque o arquivo sai do sistema e fica no calendário de quem assinou (e de
quem ele compartilhar). O dossiê se abre pelo link, com senha."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from .agenda import Compromisso

DIAS_PARA_TRAS = 60
DIAS_PARA_FRENTE = 365
PRODID = "-//PCPR//Gestao de Eventos e Viagens//PT"
CONTROLE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def escapar(texto: str) -> str:
    barra = "\\"
    texto = re.sub(r"\r\n|\r|\n", "\n", str(texto or ""))
    texto = CONTROLE.sub("", texto)  # a RFC proíbe controles em TEXT (e CR solto quebra linha)
    return (texto.replace(barra, barra * 2).replace(";", barra + ";").replace(",", barra + ",")
            .replace("\n", barra + "n"))


def dobrar(linha: str) -> list[str]:
    """Linhas de até 75 octetos (UTF-8); a continuação começa com um espaço."""
    partes: list[str] = []
    atual = ""
    for ch in linha:
        limite = 75 if not partes else 74
        if len((atual + ch).encode("utf-8")) > limite:
            partes.append(atual)
            atual = ch
        else:
            atual += ch
    partes.append(atual)
    return [partes[0], *(" " + p for p in partes[1:])]


def _data(d: date) -> str:
    return f"{d:%Y%m%d}"


def _evento(c: Compromisso, rotulo_da_fonte: str, base_url: str, dominio: str,
            carimbo: str) -> list[str]:
    linhas = ["BEGIN:VEVENT", f"UID:{escapar(c.chave)}@{dominio}", f"DTSTAMP:{carimbo}"]
    if c.hora and len(c.hora) == 5 and c.fim in (None, c.inicio):
        h, m = c.hora.split(":")
        linhas.append(f"DTSTART:{_data(c.inicio)}T{h}{m}00")  # hora local (flutuante)
        fim = (datetime.combine(c.inicio, datetime.min.time())
               + timedelta(hours=int(h), minutes=int(m)) + timedelta(hours=1))
        linhas.append(f"DTEND:{fim:%Y%m%dT%H%M%S}")
    else:
        linhas.append(f"DTSTART;VALUE=DATE:{_data(c.inicio)}")
        linhas.append(f"DTEND;VALUE=DATE:{_data(c.ultimo_dia + timedelta(days=1))}")
    linhas.append(f"SUMMARY:{escapar(c.titulo_externo or rotulo_da_fonte or 'Compromisso')}")
    if c.situacao:
        linhas.append(f"DESCRIPTION:{escapar(c.situacao)} — detalhes no sistema, com senha.")
    if rotulo_da_fonte:
        linhas.append(f"CATEGORIES:{escapar(rotulo_da_fonte)}")
    if c.url:
        linhas.append(f"URL:{base_url}{c.url}")
    if c.encerrado:
        linhas.append("STATUS:CANCELLED")
    linhas.append("TRANSP:TRANSPARENT" if c.prazo else "TRANSP:OPAQUE")
    linhas.append("END:VEVENT")
    return linhas


def montar(compromissos: Iterable[Compromisso], rotulos: dict[str, str], *, base_url: str,
           dominio: str, agora: datetime) -> str:
    carimbo = f"{agora:%Y%m%dT%H%M%SZ}"
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN",
              "METHOD:PUBLISH", "X-WR-CALNAME:Agenda PCPR", "X-WR-TIMEZONE:America/Sao_Paulo"]
    for c in compromissos:
        if c.faixa:  # feriado é fundo do dia na tela; no calendário externo não precisa
            continue
        linhas.extend(_evento(c, rotulos.get(c.fonte, ""), base_url, dominio, carimbo))
    linhas.append("END:VCALENDAR")
    return "\r\n".join(sub for linha in linhas for sub in dobrar(linha)) + "\r\n"
