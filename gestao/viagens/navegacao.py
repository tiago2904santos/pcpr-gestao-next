"""Registro do módulo Viagens na navegação do App Shell."""

from gestao.plataforma.navegacao import Grupo, Item, Modulo, registrar_modulo

registrar_modulo(
    Modulo(
        chave="viagens",
        rotulo="Viagens",
        icone="route",
        url_name="viagens:painel",
        descricao="Ofícios de viagem com cálculo de diárias, documentos e cadastros de apoio.",
        ordem=10,
        grupos=(
            Grupo("Operação", (
                Item("Painel", "viagens:painel", "layout-dashboard"),
                Item("Ofícios", "viagens:oficios", "file-text", requer="viagens.view_oficio"),
                Item("Roteiros", "viagens:roteiros", "route", requer="viagens.view_roteiro"),
                Item("Justificativas", "viagens:justificativas", "file-pen-line",
                     requer="viagens.view_oficio"),
            )),
            Grupo("Cadastros", em_menu=True, itens=(
                Item("Todos os cadastros", "cadastros:indice", "layers",
                     requer="cadastros.view_servidor"),
                Item("Servidores", "cadastros:servidores", "users",
                     requer="cadastros.view_servidor"),
                Item("Viaturas", "cadastros:viaturas", "car", requer="cadastros.view_viatura"),
                Item("Unidades", "cadastros:unidades", "building-2",
                     requer="cadastros.view_unidade"),
                Item("Cargos", "cadastros:cargos", "id-card", requer="cadastros.view_cargo"),
                Item("Combustíveis", "cadastros:combustiveis", "fuel",
                     requer="cadastros.view_combustivel"),
                Item("Tabela de diárias", "cadastros:diarias", "banknote",
                     requer="cadastros.view_tabeladiaria"),
                Item("Configuração da unidade", "cadastros:configuracao", "landmark",
                     requer="cadastros.view_configuracaoinstitucional"),
                Item("Textos prontos", "cadastros:textos", "text-quote",
                     requer="cadastros.view_modelotexto"),
                Item("Numeração dos ofícios", "viagens:numeracao", "list-ordered",
                     requer="viagens.gerir_numeracao"),
            )),
        ),
    )
)
