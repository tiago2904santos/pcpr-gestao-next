"""Registro de Palestras e eventos (ASCOM) na navegação do App Shell."""

from gestao.plataforma.navegacao import Grupo, Item, Modulo, registrar_modulo

registrar_modulo(
    Modulo(
        chave="palestras",
        rotulo="Palestras",
        icone="presentation",
        url_name="palestras:painel",
        descricao="Pedidos de palestras e eventos à ASCOM: data, local, palestrante e resposta.",
        ordem=32,
        requer="palestras.view_palestra",
        grupos=(
            Grupo("Palestras", (
                Item("Painel", "palestras:painel", "layout-dashboard",
                     requer="palestras.view_palestra"),
                Item("Palestras e eventos", "palestras:lista", "presentation",
                     requer="palestras.view_palestra"),
            )),
            Grupo("Cadastros", em_menu=True, itens=(
                Item("Palestrantes", "palestras:palestrantes", "users",
                     requer="palestras.change_palestrante"),
                Item("Temas", "palestras:temas", "list-checks", requer="palestras.change_tema"),
                Item("Respostas padrão", "palestras:respostas", "mail",
                     requer="palestras.change_respostapadrao"),
            )),
        ),
    )
)
