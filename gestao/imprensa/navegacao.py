"""Registro do Atendimento à Imprensa (ASCOM) na navegação do App Shell."""

from gestao.plataforma.navegacao import Grupo, Item, Modulo, registrar_modulo

registrar_modulo(
    Modulo(
        chave="imprensa",
        rotulo="Imprensa",
        icone="megaphone",
        url_name="imprensa:painel",
        descricao="Atendimento à imprensa da ASCOM: pedidos dos jornalistas, fontes e respostas.",
        ordem=30,
        requer="imprensa.view_atendimento",
        grupos=(
            Grupo("Atendimento", (
                Item("Painel", "imprensa:painel", "layout-dashboard",
                     requer="imprensa.view_atendimento"),
                Item("Atendimentos", "imprensa:lista", "messages-square",
                     requer="imprensa.view_atendimento"),
            )),
            Grupo("Cadastros", em_menu=True, itens=(
                Item("Equipe", "imprensa:equipe", "users", requer="imprensa.change_integrante"),
                Item("Veículos de imprensa", "imprensa:veiculos", "radio",
                     requer="imprensa.change_veiculo"),
            )),
        ),
    )
)
