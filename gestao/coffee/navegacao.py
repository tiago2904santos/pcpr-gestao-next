"""Registro do Coffee Break (ASCOM) na navegação do App Shell. Na CB1 só os cadastros
contratuais existem (do administrador do módulo); lotes, solicitações e painel entram nas
fatias seguintes."""

from gestao.plataforma.navegacao import Grupo, Item, Modulo, registrar_modulo

registrar_modulo(
    Modulo(
        chave="coffee",
        rotulo="Coffee Break",
        icone="receipt",
        url_name="coffee:fornecedores",
        descricao="Lotes contratados, ordens de serviço e o fluxo de pagamento do coffee break.",
        ordem=34,
        requer="coffee.change_fornecedor",
        grupos=(
            Grupo("Cadastros", (
                Item("Fornecedores", "coffee:fornecedores", "building-2",
                     requer="coffee.change_fornecedor"),
                Item("Contratos", "coffee:contratos", "file-text", requer="coffee.change_contrato"),
                Item("Termos aditivos", "coffee:aditivos", "file-plus-2",
                     requer="coffee.change_termoaditivo"),
                Item("Lotes", "coffee:lotes", "layers", requer="coffee.change_lote"),
                Item("Ofício e protocolo", "coffee:configuracao", "settings",
                     requer="coffee.change_configuracaooficio"),
            )),
        ),
    )
)
