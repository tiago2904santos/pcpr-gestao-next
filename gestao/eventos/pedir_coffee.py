"""Integração com o Coffee Break (CB7b): o "Pedir coffee break" da solicitação de evento
abre a OS já preenchida — município, data, "<tipo> – <local> – <município>", local, quem
recebe (solicitante e contato) e endereço. Só vale para quem enxerga a solicitação."""

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
from .models import Solicitacao

NOME = "Solicitação de evento"


def _obter(usuario, pk: int) -> DadosDaOrigem | None:
    s = (policies.solicitacoes_visiveis(usuario).select_related("municipio", "tipo_evento")
         .filter(pk=pk).first())
    if s is None:
        return None
    cidade = s.municipio.nome if s.municipio else ""
    tipo = s.tipo_evento.nome if s.tipo_evento else "Evento"
    return DadosDaOrigem(f"{NOME} #{s.pk}", reverse("eventos:solicitacao", args=[s.pk]), {
        "municipio": f"{s.municipio.nome}/{s.municipio.uf}" if s.municipio else "",
        "data_evento": s.data_inicio_evento,
        "descricao": juntar(tipo, s.local_evento, cidade),
        "local_entrega": s.local_evento,
        "responsavel": juntar(s.solicitante_nome, s.contato, separador=" "),
        "endereco": s.endereco, "bairro": s.bairro, "cep": s.cep})


def _data(pk: int) -> date | None:
    return Solicitacao.objects.filter(pk=pk).values_list("data_inicio_evento", flat=True).first()


def registrar() -> None:
    registrar_origem(Origem("evento", NOME, _obter, _data))


def url(usuario, s: Solicitacao) -> str:
    return url_para_pedir(usuario, "evento", s.pk)
