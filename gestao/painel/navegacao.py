"""Registro da Agenda na navegação do App Shell (um módulo próprio, como na referência: a
agenda junta o que vem de todos os módulos)."""

from gestao.plataforma.navegacao import Grupo, Item, Modulo, registrar_modulo

registrar_modulo(
    Modulo(
        chave="agenda",
        rotulo="Agenda",
        icone="calendar-days",
        url_name="painel:agenda",
        descricao="O mês de todos os módulos: viagens, prazos de saque das diárias e feriados.",
        ordem=20,
        grupos=(Grupo("Agenda", (Item("Calendário", "painel:agenda", "calendar-days"),)),),
    )
)
