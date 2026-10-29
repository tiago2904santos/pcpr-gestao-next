from django.urls import path

from . import views

app_name = "assistencia"

urlpatterns = [
    path("", views.painel, name="painel"),
    path("usos/", views.usos, name="usos"),
    path("usos/orcamento/", views.definir_teto, name="definir_teto"),
    path("usos/<str:chave>/", views.alterar_uso, name="alterar_uso"),
    path("simulador/processar/", views.processar_agora, name="processar_agora"),
    path("sugestoes/", views.sugestoes, name="sugestoes"),
    path("sugestoes/<int:pk>/", views.sugestao, name="sugestao"),
    path("sugestoes/<int:pk>/aceitar/", views.aceitar, name="aceitar"),
    path("sugestoes/<int:pk>/descartar/", views.descartar, name="descartar"),
    path("pedir/<str:chave>/<str:recurso_id>/", views.pedir, name="pedir"),
    path("pedidos/<int:pk>/", views.pedido, name="pedido"),
]
