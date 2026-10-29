"""Registro da Automação (WhatsApp, comunicações e exceções) na navegação do App Shell."""

from gestao.plataforma.navegacao import Grupo, Item, Modulo, registrar_modulo

registrar_modulo(
    Modulo(
        chave="automacao",
        rotulo="Automação",
        icone="send",
        url_name="automacao:painel",
        descricao="WhatsApp do sistema de testes: avisos enviados, respostas recebidas, "
                  "contatos com opt-in e a fila do que precisa de uma pessoa.",
        ordem=80,
        requer="automacao.view_comunicacao",
        grupos=(
            Grupo("Operação", (
                Item("Painel", "automacao:painel", "layout-dashboard",
                     requer="automacao.view_comunicacao"),
                Item("Comunicações", "automacao:comunicacoes", "send",
                     requer="automacao.view_comunicacao", ativo_em=("/automacao/comunicacoes/",)),
                Item("Recebidos", "automacao:recebimentos", "inbox",
                     requer="automacao.view_comunicacao", ativo_em=("/automacao/recebidos/",)),
                Item("Exceções", "automacao:excecoes", "alert-triangle",
                     requer="automacao.view_comunicacao", ativo_em=("/automacao/excecoes/",)),
            )),
            Grupo("Governança", em_menu=True, itens=(
                Item("Aprovações", "automacao:aprovacoes", "badge-check",
                     requer="automacao.operar_automacao"),
                Item("Links pessoais", "automacao:links", "lock",
                     requer="automacao.operar_automacao"),
                Item("Credenciais", "automacao:credenciais", "shield-alert",
                     requer="automacao.view_comunicacao"),
                Item("Delegar a uma automação", "automacao:delegar", "send",
                     requer="automacao.view_comunicacao"),
                Item("Histórico da automação", "automacao:execucoes", "history",
                     requer="automacao.administrar_automacao"),
            )),
            Grupo("Configuração", em_menu=True, itens=(
                Item("Contatos e opt-in", "automacao:contatos", "phone",
                     requer="automacao.operar_automacao"),
                Item("Testadores autorizados", "automacao:testadores", "shield-check",
                     requer="automacao.administrar_automacao"),
                Item("Canal e chaves", "automacao:canal", "sliders-horizontal",
                     requer="automacao.administrar_automacao"),
            )),
        ),
    )
)
