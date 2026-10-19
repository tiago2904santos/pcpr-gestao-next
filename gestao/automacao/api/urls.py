from django.urls import path

from . import views

app_name = "api_automacao"

urlpatterns = [
    path("estado", views.estado, name="estado"),
    path("comunicacoes", views.por_mensagem, name="por_mensagem"),
    path("comunicacoes/devidas", views.devidas, name="devidas"),
    path("comunicacoes/<int:pk>", views.situacao, name="situacao"),
    path("comunicacoes/<int:pk>/reservar", views.reservar, name="reservar"),
    path("comunicacoes/<int:pk>/resultado", views.resultado, name="resultado"),
    path("comunicacoes/<int:pk>/entrega", views.entrega_status, name="entrega"),
    path("recebimentos", views.criar_recebimento, name="recebimentos"),
    path("recebimentos/sem-arquivo", views.recebimento_sem_arquivo, name="sem_arquivo"),
    path("recebimentos/<int:pk>", views.obter_recebimento, name="recebimento"),
    path("entradas", views.criar_entrada, name="entradas"),
    path("assistente/mensagens", views.mensagem_assistente, name="assistente"),
    path("excecoes", views.abrir_excecao, name="excecoes"),
    path("ferramentas", views.listar_ferramentas, name="ferramentas"),
    path("ferramentas/<str:nome>/executar", views.executar_ferramenta, name="executar"),
]
