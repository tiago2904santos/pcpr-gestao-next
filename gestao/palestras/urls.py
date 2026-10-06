from django.urls import path

from . import views

app_name = "palestras"

urlpatterns = [
    path("", views.painel, name="painel"),
    path("pedidos/", views.lista, name="lista"),
    path("pedidos/exportar/", views.exportar, name="exportar"),
    path("pedidos/nova/", views.nova, name="nova"),
    path("pedidos/<int:pk>/", views.palestra, name="palestra"),
    path("pedidos/<int:pk>/autosave/", views.autosave, name="autosave"),
    path("pedidos/<int:pk>/andamento/", views.andamento, name="andamento"),
    path("pedidos/<int:pk>/responder/", views.responder, name="responder"),
    path("pedidos/<int:pk>/encaminhar-dg/", views.encaminhar_dg, name="encaminhar_dg"),
    path("pedidos/<int:pk>/duplicar/", views.duplicar, name="duplicar"),
    path("api/palestrantes/", views.buscar_palestrantes, name="buscar_palestrantes"),
    path("cadastros/palestrantes/", views.palestrantes, name="palestrantes"),
    path("cadastros/temas/", views.temas, name="temas"),
    path("cadastros/respostas/", views.respostas, name="respostas"),
]
