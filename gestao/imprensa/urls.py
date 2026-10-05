from django.urls import path

from . import views

app_name = "imprensa"

urlpatterns = [
    path("", views.painel, name="painel"),
    path("atendimentos/", views.lista, name="lista"),
    path("atendimentos/exportar/", views.exportar, name="exportar"),
    path("atendimentos/novo/", views.novo, name="novo"),
    path("atendimentos/<int:pk>/", views.atendimento, name="atendimento"),
    path("atendimentos/<int:pk>/autosave/", views.autosave, name="autosave"),
    path("atendimentos/<int:pk>/andamento/", views.andamento, name="andamento"),
    path("cadastros/equipe/", views.equipe, name="equipe"),
    path("cadastros/veiculos/", views.veiculos, name="veiculos"),
]
