from django.urls import path

from . import views

app_name = "publicacoes"

urlpatterns = [
    path("", views.painel, name="painel"),
    path("pautas/", views.lista, name="lista"),
    path("pautas/exportar/", views.exportar, name="exportar"),
    path("pautas/nova/", views.nova, name="nova"),
    path("pautas/nova/email/", views.preencher, name="preencher"),
    path("pautas/<int:pk>/", views.pauta, name="pauta"),
    path("pautas/<int:pk>/autosave/", views.autosave, name="autosave"),
    path("pautas/<int:pk>/andamento/", views.andamento, name="andamento"),
    path("cadastros/equipe/", views.equipe, name="equipe"),
    path("cadastros/unidades/", views.unidades, name="unidades"),
]
