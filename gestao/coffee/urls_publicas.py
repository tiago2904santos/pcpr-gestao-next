from django.urls import path

from . import views_publicas

app_name = "fornecedor"

urlpatterns = [path("<str:token>/", views_publicas.envio, name="envio")]
