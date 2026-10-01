from django.urls import path

from . import views

app_name = "cadastros"

urlpatterns = [
    path("servidores/", views.servidores, name="servidores"),
    path("viaturas/", views.viaturas, name="viaturas"),
    path("diarias/", views.diarias, name="diarias"),
    path("api/municipios/", views.buscar_municipios, name="buscar_municipios"),
]
