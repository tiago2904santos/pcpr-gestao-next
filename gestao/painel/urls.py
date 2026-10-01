from django.urls import path

from . import views

app_name = "painel"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("notificacoes/", views.notificacoes, name="notificacoes"),
    path("busca/", views.busca, name="busca"),
]
