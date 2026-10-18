from django.urls import path

from . import views, views_admin

app_name = "automacao"

urlpatterns = [
    path("", views.painel, name="painel"),
    path("canal/", views.canal, name="canal"),
    path("canal/chave/", views.alterar_chave, name="alterar_chave"),
    path("canal/desligar/", views.desligar_tudo, name="desligar_tudo"),
    path("simulador/processar/", views.processar_agora, name="processar_agora"),
    path("simulador/mensagem/", views.simular_mensagem, name="simular_mensagem"),
    path("comunicacoes/", views.comunicacoes_lista, name="comunicacoes"),
    path("comunicacoes/aprovar/", views.aprovar_comunicacoes, name="aprovar_comunicacoes"),
    path("comunicacoes/<int:pk>/", views.comunicacao, name="comunicacao"),
    path("comunicacoes/<int:pk>/<str:acao>/", views.acao_comunicacao, name="acao_comunicacao"),
    path("recebidos/", views.recebimentos_lista, name="recebimentos"),
    path("recebidos/<int:pk>/", views.recebimento, name="recebimento"),
    path("recebidos/<int:pk>/arquivo/", views.arquivo_recebido, name="arquivo_recebido"),
    path("recebidos/<int:pk>/<str:acao>/", views.acao_recebimento, name="acao_recebimento"),
    path("excecoes/", views.excecoes_lista, name="excecoes"),
    path("excecoes/<int:pk>/", views.excecao, name="excecao"),
    path("excecoes/<int:pk>/<str:acao>/", views.acao_excecao, name="acao_excecao"),
    path("contatos/", views.contatos_lista, name="contatos"),
    path("contatos/novo/", views.novo_contato, name="novo_contato"),
    path("contatos/<int:pk>/", views.contato, name="contato"),
    path("contatos/<int:pk>/<str:acao>/", views.acao_contato, name="acao_contato"),
    path("testadores/", views.testadores, name="testadores"),
    path("testadores/<int:pk>/remover/", views.remover_testador, name="remover_testador"),
    path("credenciais/", views_admin.credenciais_lista, name="credenciais"),
    path("credenciais/<int:pk>/<str:acao>/", views_admin.acao_credencial,
         name="acao_credencial"),
    path("aprovacoes/", views_admin.aprovacoes, name="aprovacoes"),
    path("aprovacoes/<int:pk>/<str:acao>/", views_admin.decidir_aprovacao,
         name="decidir_aprovacao"),
    path("historico/", views_admin.execucoes, name="execucoes"),
    path("delegar/", views_admin.delegar, name="delegar"),
    path("links/", views_admin.links_lista, name="links"),
    path("links/<int:pk>/revogar/", views_admin.revogar_link, name="revogar_link"),
    path("links/revogar-em-massa/", views_admin.revogar_links_em_massa,
         name="revogar_links_em_massa"),
]
