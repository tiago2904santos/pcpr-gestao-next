"""O "O que fazer hoje" do painel do Coffee Break (`painel.o_que_fazer`) na aba Pendências
da Agenda (`plataforma.pendencias`): as OS que dependem da equipe — entregas da semana e
os pagamentos parados —, cada uma com o botão que o painel já mostra."""

from __future__ import annotations

from datetime import date

from django.urls import reverse

from gestao.plataforma.pendencias import LIMITE, Grupo, Item, Secao, registrar_secao

from . import dominio_painel, painel, policies


def _grupos(usuario, hoje: date) -> list[Grupo]:
    destino = reverse("coffee:painel") + "#t-fazer"
    grupos = []
    for g in painel.o_que_fazer(hoje):
        itens = []
        for s, dias, rotulo, secao, url in g.itens[:LIMITE]:
            parada = g.chave != "entregas" and dias >= dominio_painel.DIAS_PARADA
            fatos = [("calendar", f"Evento {s.data_evento:%d/%m/%Y}" if s.data_evento
                      else "Sem data do evento")]
            if s.lote_id:
                fatos.append(("building-2", str(s.lote.contrato.fornecedor)))
            itens.append(Item(
                chave=f"coffee-{s.pk}", titulo=(s.descricao or str(s))[:80],
                url=url or painel.url_da_secao(s, secao), acao=rotulo,
                rotulo="OS", numero=s.numero or "—", fatos=tuple(fatos),
                selo=dominio_painel.texto_parada(dias) if parada else "",
                tom="aviso" if parada else "neutro"))
        grupos.append(Grupo(g.chave, g.titulo, len(g.itens), itens, ajuda=g.ajuda,
                            ver_todos=destino))
    return grupos


def registrar() -> None:
    registrar_secao(Secao(
        "coffee", "Coffee break", "receipt",
        "Entregas desta semana e pagamentos parados com a equipe.",
        policies.pode_acessar, _grupos, vazio=dominio_painel.MSG_NADA_PENDENTE, ordem=50))
