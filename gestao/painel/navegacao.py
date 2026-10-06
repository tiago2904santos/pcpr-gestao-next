"""Registro da Agenda e dos Relatórios na navegação do App Shell (módulos próprios, como na
referência: juntam o que vem de todos os módulos, cada parte com a permissão dela)."""

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

registrar_modulo(
    Modulo(
        chave="relatorios",
        rotulo="Relatórios",
        icone="table",
        url_name="painel:relatorios",
        descricao="Os números de todos os módulos por mês: palestras, PCPR na Comunidade, "
                  "eventos, coffee break, publicações, imprensa e viagens.",
        ordem=90,
        grupos=(Grupo("Relatórios", (Item("Consolidado", "painel:relatorios", "table"),)),),
    )
)
