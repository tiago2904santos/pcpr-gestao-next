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
                Item("Viagens", "viagens:viagens", "map", requer="viagens.view_viagem",
                     ativo_em=("/viagens/viagens/",)),
                Item("Ofícios", "viagens:oficios", "file-text", requer="viagens.view_oficio"),
                Item("Roteiros", "viagens:roteiros", "route", requer="viagens.view_roteiro"),
            )),
            # Os documentos que saem dos ofícios (menu, para a barra caber no tablet).
            Grupo("Documentos", em_menu=True, itens=(
                Item("Justificativas", "viagens:justificativas", "file-pen-line",
                     requer="viagens.view_oficio"),
                Item("Termos de autorização", "viagens:termos", "file-signature",
                     requer="viagens.view_termoautorizacao"),
                Item("Ordens de serviço", "viagens:ordens", "clipboard-list",
                     requer="viagens.view_ordemservico"),
                Item("Planos de trabalho", "viagens:planos", "list-checks",
                     requer="viagens.view_planotrabalho"),
                # Nasce do ofício emitido; no menu porque a barra não cabe no tablet (768px)
                # com mais um item solto.
                Item("Prestação de contas", "viagens:prestacoes", "receipt",
                     requer="viagens.view_prestacaoservidor"),
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
                Item("Tipos de viagem", "cadastros:tipos", "route",
                     requer="cadastros.view_tipoviagem"),
                Item("Configuração da unidade", "cadastros:configuracao", "landmark",
                     requer="cadastros.view_configuracaoinstitucional"),
                Item("Textos prontos", "cadastros:textos", "text-quote",
                     requer="cadastros.view_modelotexto"),
                Item("Numeração dos ofícios", "viagens:numeracao", "list-ordered",
                     requer="viagens.gerir_numeracao"),
                Item("Usuários e perfis", "cadastros:usuarios", "user-round",
                     requer="identidade.view_usuario"),
            )),
        ),
    )
)
