"""Integração com o Coffee Break (CB7b): o "Pedir coffee break" da palestra abre a OS já
preenchida — município, data, horário, "<evento> – <temas> – <município>", local, quem
recebe (solicitante e telefone), o público e o endereço. Só para quem vê as palestras."""

from __future__ import annotations

from datetime import date

from django.urls import reverse

from gestao.coffee.ganchos import (
    DadosDaOrigem,
    Origem,
    juntar,
    registrar_origem,
    url_para_pedir,
)

from . import policies
from .models import Palestra

NOME = "Palestra"


def _obter(usuario, pk: int) -> DadosDaOrigem | None:
    if not policies.pode_acessar(usuario):
        return None
    p = (Palestra.objects.select_related("municipio").prefetch_related("temas")
         .filter(pk=pk).first())
    if p is None:
        return None
    cidade = p.municipio.nome if p.municipio else ""
    temas = ", ".join(t.nome for t in p.temas.all())
    evento = p.get_evento_display() or NOME
    return DadosDaOrigem(f"{evento} #{p.pk}", reverse("palestras:palestra", args=[p.pk]), {
        "municipio": f"{p.municipio.nome}/{p.municipio.uf}" if p.municipio else "",
        "data_evento": p.data_inicio_evento, "horario": p.hora_inicio,
        "descricao": juntar(evento, temas, cidade),
        "local_entrega": p.local,
        "responsavel": juntar(p.solicitante[:100], p.telefone, separador=" "),
        "quantidade": p.quantidade_publico,
        "endereco": p.endereco, "bairro": p.bairro, "cep": p.cep})


def _data(pk: int) -> date | None:
    return Palestra.objects.filter(pk=pk).values_list("data_inicio_evento", flat=True).first()


def registrar() -> None:
    registrar_origem(Origem("palestra", NOME, _obter, _data))


def url(usuario, p: Palestra) -> str:
    return url_para_pedir(usuario, "palestra", p.pk)
