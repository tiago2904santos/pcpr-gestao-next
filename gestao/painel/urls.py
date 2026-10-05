from django.urls import path

from . import views, views_agenda, views_notificacoes

app_name = "painel"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("notificacoes/", views_notificacoes.central, name="notificacoes"),
    path("notificacoes/marcar-lidas/", views_notificacoes.marcar_lidas,
         name="marcar_notificacoes_lidas"),
    path("notificacoes/<int:pk>/abrir/", views_notificacoes.abrir, name="abrir_notificacao"),
    path("busca/", views.busca, name="busca"),
    path("agenda/", views_agenda.agenda_view, name="agenda"),
]
