"""Registro de Publicações (ASCOM) na navegação do App Shell."""

from gestao.plataforma.navegacao import Grupo, Item, Modulo, registrar_modulo

registrar_modulo(
    Modulo(
        chave="publicacoes",
        rotulo="Publicações",
        icone="newspaper",
        url_name="publicacoes:painel",
        descricao="Pautas da ASCOM, da entrada até a publicação no site e na AEN.",
        ordem=31,
        requer="publicacoes.view_publicacao",
        grupos=(
            Grupo("Pautas", (
                Item("Painel", "publicacoes:painel", "layout-dashboard",
                     requer="publicacoes.view_publicacao"),
                Item("Pautas", "publicacoes:lista", "newspaper",
                     requer="publicacoes.view_publicacao"),
            )),
            Grupo("Cadastros", em_menu=True, itens=(
                Item("Equipe", "publicacoes:equipe", "users",
                     requer="publicacoes.change_integrante"),
                Item("Unidades responsáveis", "publicacoes:unidades", "landmark",
                     requer="publicacoes.change_unidaderesponsavel"),
            )),
        ),
    )
)
