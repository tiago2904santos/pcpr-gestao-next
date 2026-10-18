"""Registro da Assistência (IA) e da Central de ajuda na navegação do App Shell."""

from gestao.plataforma.navegacao import Grupo, Item, Modulo, registrar_modulo

registrar_modulo(
    Modulo(
        chave="ajuda",
        rotulo="Ajuda",
        icone="book-open-text",
        url_name="ajuda:central",
        descricao="Central de ajuda com procedimentos aprovados e o assistente de dúvidas "
                  "(responde com os dados do sistema e diz o que não sabe).",
        ordem=95,
        grupos=(Grupo("Ajuda", (
            Item("Central de ajuda", "ajuda:central", "book-open-text",
                 ativo_em=("/ajuda/",)),
        )),),
    )
)

registrar_modulo(
    Modulo(
        chave="assistencia",
        rotulo="Assistência",
        icone="text-quote",
        url_name="assistencia:painel",
        descricao="Sugestões de texto e de leitura (com ou sem IA), sempre revisadas por uma "
                  "pessoa: usos, limites, orçamento e custo estimado.",
        ordem=85,
        requer="assistencia.ver_painel_ia",
        grupos=(
            Grupo("Assistência", (
                Item("Painel", "assistencia:painel", "layout-dashboard",
                     requer="assistencia.ver_painel_ia"),
                Item("Sugestões", "assistencia:sugestoes", "text-quote",
                     requer="assistencia.ver_painel_ia",
                     ativo_em=("/assistencia/sugestoes/",)),
            )),
            Grupo("Configuração", em_menu=True, itens=(
                Item("Usos, limites e orçamento", "assistencia:usos", "sliders-horizontal",
                     requer="assistencia.administrar_ia"),
            )),
        ),
    )
)
