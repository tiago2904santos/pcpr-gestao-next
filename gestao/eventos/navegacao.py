"""Registro de Eventos Sociais na navegação do App Shell. Como na referência, todo usuário
autenticado entra (pedir um evento é de todos); os cadastros ficam com quem administra."""

from gestao.plataforma.navegacao import Grupo, Item, Modulo, registrar_modulo

registrar_modulo(
    Modulo(
        chave="eventos",
        rotulo="Eventos Sociais",
        icone="calendar-days",
        url_name="eventos:painel",
        descricao="Solicitações de eventos sociais e despacho da Diretoria-Geral.",
        ordem=15,
        grupos=(
            Grupo("Eventos", (
                Item("Painel", "eventos:painel", "layout-dashboard"),
                Item("Solicitações", "eventos:solicitacoes", "file-text"),
                Item("Nova solicitação", "eventos:nova", "plus"),
            )),
            Grupo("Cadastros", em_menu=True, itens=(
                Item("Todos os cadastros", "eventos:cadastros", "layers",
                     requer="eventos.change_textodespacho"),
                Item("Tipos de evento", "eventos:tipos-evento", "calendar-days",
                     requer="eventos.change_tipoevento"),
                Item("Serviços", "eventos:servicos", "list-checks",
                     requer="eventos.change_servico"),
                Item("Equipes", "eventos:equipes", "users", requer="eventos.change_equipe"),
                Item("Órgãos responsáveis", "eventos:orgaos", "landmark",
                     requer="eventos.change_orgaoresponsavel"),
                Item("Unidades móveis", "eventos:unidades-moveis", "bus",
                     requer="eventos.change_unidademovel"),
                Item("Textos prontos do despacho", "eventos:textos-despacho", "text-quote",
                     requer="eventos.change_textodespacho"),
            )),
        ),
    )
)
