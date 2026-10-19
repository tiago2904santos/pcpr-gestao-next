"""As solicitações de evento que esperam alguém, na aba Pendências da Agenda
(`plataforma.pendencias`): os rascunhos e as devolvidas de quem as criou, as que aguardam
o despacho da DG (para quem despacha) e as deferidas já realizadas que pedem a confirmação
do atendimento. Os recortes são as filas da lista (`queries.aplicar_fila`); a visibilidade é
a das policies."""

from __future__ import annotations

from datetime import date

from django.urls import reverse

from gestao.plataforma.pendencias import Grupo, Item, Secao, carregar, por_urgencia, registrar_secao

from . import dominio, policies, queries

# (fila, título, ajuda, botão, só as de quem criou?)
FILAS = (
    ("despacho", "Aguardando o despacho da DG", "Decida: atender, não atender ou devolver "
     "para correção.", "Despachar", False),
    ("devolvidas", "Devolvidas para correção", "A DG pediu ajustes: corrija e envie de novo.",
     "Corrigir", True),
    ("rascunhos", "Rascunhos", "Complete e envie a solicitação para o despacho.",
     "Continuar", True),
    ("confirmar", "Confirmar o atendimento", "O evento já passou: confirme se foi atendido.",
     "Confirmar", True),
)


def _grupos(usuario, hoje: date) -> list[Grupo]:
    base = queries.base(usuario)
    lista = reverse("eventos:solicitacoes")
    grupos = []
    for fila, titulo, ajuda, botao, so_minhas in FILAS:
        if fila == "despacho" and not policies.pode_despachar(usuario):
            continue
        qs = queries.aplicar_fila(base, fila, usuario, hoje)
        if so_minhas:  # quem age é quem criou (policies.pode_editar_dados / pode_concluir)
            qs = qs.filter(criado_por=usuario)
        linhas, total = carregar(por_urgencia(qs, "data_inicio_evento", hoje))
        itens = []
        for s in linhas:
            selo = dominio.selo_de_tempo(s.data_inicio_evento, s.data_fim_evento, s.status,
                                         hoje)
            itens.append(Item(
                chave=f"evento-{s.pk}", titulo=queries.titulo(s),
                url=reverse("eventos:solicitacao", args=[s.pk]), acao=botao,
                rotulo="Evento", numero=f"#{s.pk}",
                fatos=(("calendar", queries.periodo(s) or "Sem período"),
                       ("clock", f"Solicitada em {s.data_solicitacao:%d/%m/%Y}")),
                selo=selo.texto if selo else "", tom=selo.tom if selo else "neutro"))
        grupos.append(Grupo(fila, titulo, total, itens, ajuda=ajuda,
                            ver_todos=f"{lista}?fila={fila}"))
    return grupos


def registrar() -> None:
    registrar_secao(Secao(
        "eventos", "Solicitações de evento", "calendar-days",
        "Rascunhos, devolvidas, despacho da DG e atendimentos a confirmar.",
        policies.pode_criar, _grupos,
        vazio="Nenhuma solicitação de evento esperando por você.", ordem=40))
