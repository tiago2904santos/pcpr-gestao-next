from django.urls import path

from . import views

app_name = "ui_lab"

urlpatterns = [
    path("", views.indice, name="indice"),
    path("busca-exemplo/", views.busca_exemplo, name="busca_exemplo"),
]
