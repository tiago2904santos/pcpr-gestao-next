"""Registro do Coffee Break (ASCOM) na navegação do App Shell: solicitações e lotes para
quem tem o módulo; os cadastros contratuais para o administrador do módulo."""

from gestao.plataforma.navegacao import Grupo, Item, Modulo, registrar_modulo

registrar_modulo(
    Modulo(
        chave="coffee",
        rotulo="Coffee Break",
        icone="receipt",
        url_name="coffee:painel",
        descricao="Lotes contratados, ordens de serviço e o fluxo de pagamento do coffee break.",
        ordem=34,
        requer="coffee.acessar_coffee",
        grupos=(
            Grupo("Coffee Break", (
                Item("Painel", "coffee:painel", "layout-dashboard", requer="coffee.acessar_coffee"),
                Item("Solicitações", "coffee:solicitacoes", "receipt",
                     requer="coffee.acessar_coffee"),
                Item("Nova solicitação", "coffee:nova", "plus", requer="coffee.acessar_coffee"),
                Item("Lotes", "coffee:lotes", "layers", requer="coffee.acessar_coffee"),
                Item("Certidões", "coffee:certidoes", "shield-check",
                     requer="coffee.acessar_coffee"),
            )),
            Grupo("Cadastros", em_menu=True, itens=(
                Item("Fornecedores", "coffee:fornecedores", "building-2",
                     requer="coffee.change_fornecedor"),
                Item("Contratos", "coffee:contratos", "file-text", requer="coffee.change_contrato"),
                Item("Termos aditivos", "coffee:aditivos", "file-plus-2",
                     requer="coffee.change_termoaditivo"),
                Item("Lotes", "coffee:lotes_cadastro", "layers", requer="coffee.change_lote"),
                Item("Ofício e protocolo", "coffee:configuracao", "settings",
                     requer="coffee.change_configuracaooficio"),
            )),
        ),
    )
)
